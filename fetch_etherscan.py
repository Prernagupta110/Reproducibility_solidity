import json
import re
from utils import (CONTRACTS, ETHERSCAN_API_KEY, DATA_DIR, CHAIN_ID,
                   get_with_retry, etherscan_rate_limit, log_failure, require_secrets)

ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"
out_dir = DATA_DIR / "etherscan"
out_dir.mkdir(parents=True, exist_ok=True)


def parse_sourcecode_field(raw: str):
    raw = raw.strip()
    if raw.startswith("{{") and raw.endswith("}}"):
        return "std-json", json.loads(raw[1:-1])
    if raw.startswith("{") and raw.endswith("}"):
        try:
            return "multi", json.loads(raw)
        except json.JSONDecodeError:
            pass   
    return "single", {"Contract.sol": raw}


def parse_library_field(library_str: str, contract_name: str):
    """
    Etherscan's flat Library field looks like 'LibA:5c69bee...;LibB:abc123...'.
    Note Etherscan OMITS the '0x' prefix on the address, but solc Standard JSON
    REQUIRES it, so we add it.
    solc wants {"File.sol": {"LibA": "0x5c69bee..."}}.
    """
    if not library_str:
        return {}
    libs = {}
    target_file = f"{contract_name}.sol"   
    for entry in library_str.split(";"):
        entry = entry.strip()
        if ":" not in entry:
            continue
        name, addr = entry.split(":", 1)
        addr = addr.strip()
        if addr and not addr.lower().startswith("0x"):
            addr = "0x" + addr            # solc requires the 0x prefix
        libs.setdefault(target_file, {})[name.strip()] = addr
    return libs


def _ensure_0x_prefixed_libraries(libs: dict) -> dict:
    fixed = {}
    for fname, mapping in (libs or {}).items():
        if not isinstance(mapping, dict):
            fixed[fname] = mapping
            continue
        fixed[fname] = {}
        for libname, addr in mapping.items():
            a = str(addr).strip()
            if a and not a.lower().startswith("0x"):
                a = "0x" + a
            fixed[fname][libname] = a
    return fixed


def extract_advanced(std_json: dict):
    s = std_json.get("settings", {})
    return {
        "via_ir": s.get("viaIR", False),
        "bytecode_hash": s.get("metadata", {}).get("bytecodeHash", "ipfs"),
        "libraries_stdjson": s.get("libraries", {}),
    }



if __name__ == "__main__":
    require_secrets()
    for addr in CONTRACTS:
        try:
            etherscan_rate_limit()
            params = {
                "chainid": CHAIN_ID, "module": "contract", "action": "getsourcecode",
                "address": addr, "apikey": ETHERSCAN_API_KEY,
            }
            data = get_with_retry(ETHERSCAN_V2, params=params).json()
            if data.get("status") != "1":
                print(f"[etherscan] {addr}: error {data}")
                log_failure("fetch_etherscan", addr, data)
                continue

            rec = data["result"][0]

            # An unverified contract returns status=1 but with an empty SourceCode
            if not rec.get("SourceCode", "").strip():
                print(f"[etherscan] {addr}: NOT VERIFIED on Etherscan (no source) - skipping")
                log_failure("fetch_etherscan", addr, "not verified on Etherscan (empty SourceCode)")
                continue

            kind, parsed = parse_sourcecode_field(rec["SourceCode"])

            # Etherscan gives "v0.8.19+commit.7dd6d404"; solc-select wants "0.8.19".
            compiler_full = rec["CompilerVersion"]
            m = re.match(r"v?(\d+\.\d+\.\d+)", compiler_full)
            if not m:
                print(f"[etherscan] {addr}: unparseable compiler '{compiler_full}' - skipping")
                log_failure("fetch_etherscan", addr, f"unparseable compiler version: {compiler_full}")
                continue
            compiler_short = m.group(1)

            advanced = (extract_advanced(parsed) if kind == "std-json"
                        else {"via_ir": False, "bytecode_hash": "ipfs",
                              "libraries_stdjson": {}})

            
            libs = (advanced["libraries_stdjson"]
                    or parse_library_field(rec.get("Library", ""), rec["ContractName"]))

            settings = {
                "address": addr,
                "contract_name": rec["ContractName"],
                "compiler_version_full": compiler_full,
                "compiler_version": compiler_short,
                "optimization_used": rec["OptimizationUsed"] == "1",
                "runs": int(rec["Runs"]) if rec["Runs"] else 200,
                "evm_version": rec["EVMVersion"],
                "constructor_arguments": rec["ConstructorArguments"],  
                "libraries": libs,
                "via_ir": advanced["via_ir"],
                "bytecode_hash": advanced["bytecode_hash"],
                "is_proxy": rec.get("Proxy") == "1",
                "implementation": rec.get("Implementation"),
                "source_kind": kind,
            }

            contract_dir = out_dir / addr.lower()
            contract_dir.mkdir(exist_ok=True)
            (contract_dir / "settings.json").write_text(json.dumps(settings, indent=2))

            if kind == "std-json":
                (contract_dir / "standard_input.json").write_text(json.dumps(parsed, indent=2))
            else:
                for fname, content in parsed.items():
                    text = content["content"] if isinstance(content, dict) else content
                    target = contract_dir / fname
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text)

            print(f"[etherscan] {addr}: {settings['contract_name']} "
                  f"solc={compiler_short} opt={settings['optimization_used']} "
                  f"viaIR={settings['via_ir']} hash={settings['bytecode_hash']} "
                  f"libs={len(libs)} kind={kind}")
        except Exception as e:
            print(f"[etherscan] {addr}: FAILED - {e}")
            log_failure("fetch_etherscan", addr, e)