import json
import subprocess
from utils import CONTRACTS, DATA_DIR, log_failure

src_root = DATA_DIR / "etherscan"
out_root = DATA_DIR / "compiled"
out_root.mkdir(parents=True, exist_ok=True)

# Cache the set of installed solc versions so we don't re-install every loop.
_installed = None


def get_installed_solc_versions():
    global _installed
    if _installed is None:
        r = subprocess.run(["solc-select", "versions"], capture_output=True, text=True)
        _installed = set()
        for line in r.stdout.splitlines():
            line = line.strip().lstrip("*").strip()   
            if line and line[0].isdigit():
                _installed.add(line.split()[0])
    return _installed


def ensure_solc(version: str):
    #Install (only if missing) then select the requested solc version.
    clean = version.lstrip("v").split("-")[0].split("+")[0]
    installed = get_installed_solc_versions()
    if clean not in installed:
        r = subprocess.run(["solc-select", "install", clean],
                            capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"solc {clean} unavailable via solc-select "
                f"(pre-0.3.6 or unsupported): {r.stderr.strip()[:120]}")
        installed.add(clean)
    subprocess.run(["solc-select", "use", clean], check=True)


def build_standard_input(contract_dir, settings):
    #Reconstruct a Standard JSON Input from flat .sol files
    sources = {}
    for f in contract_dir.rglob("*.sol"):
        rel = f.relative_to(contract_dir).as_posix()   
        sources[rel] = {"content": f.read_text()}

    std_settings = {
        "optimizer": {
            "enabled": settings["optimization_used"],
            "runs": settings["runs"],
        },
        "outputSelection": {
            "*": {"*": ["evm.bytecode.object",
                        "evm.deployedBytecode.object", "metadata"]}
        },
    }
    # evmVersion: only set if non-default 
    evm = settings.get("evm_version")
    if evm and evm != "Default":
        std_settings["evmVersion"] = evm.lower()
    # viaIR: the Yul IR pipeline emits different bytecode than the legacy path.
    if settings.get("via_ir"):
        std_settings["viaIR"] = True
    # libraries: needed so unlinked placeholders get filled with real addresses.
    # solc requires every address be 0x-prefixed, Etherscan's flat field omits it.
    if settings.get("libraries"):
        libs = settings["libraries"]
        fixed = {}
        for fname, mapping in libs.items():
            if isinstance(mapping, dict):
                fixed[fname] = {
                    ln: (a if str(a).lower().startswith("0x") else "0x" + str(a))
                    for ln, a in mapping.items()
                }
            else:
                fixed[fname] = mapping
        std_settings["libraries"] = fixed
    # metadata.bytecodeHash: 'ipfs' (default), 'bzzr1' (Swarm), or 'none'.
    bh = settings.get("bytecode_hash", "ipfs")
    if bh != "ipfs":
        std_settings["metadata"] = {"bytecodeHash": bh}

    return {"language": "Solidity", "sources": sources, "settings": std_settings}



if __name__ == "__main__":
    for addr in CONTRACTS:
        try:
            contract_dir = src_root / addr.lower()
            settings_file = contract_dir / "settings.json"
            if not settings_file.exists():
                print(f"[recompile] no settings for {addr}, skipping")
                continue

            settings = json.loads(settings_file.read_text())
            ensure_solc(settings["compiler_version"])

            std_in_file = contract_dir / "standard_input.json"
            if std_in_file.exists():
                std_in = json.loads(std_in_file.read_text())
                std_in.setdefault("settings", {})["outputSelection"] = {
                    "*": {"*": ["evm.bytecode.object",
                                "evm.deployedBytecode.object", "metadata"]}
                }
            else:
                std_in = build_standard_input(contract_dir, settings)

            proc = subprocess.run(
                ["solc", "--standard-json"], input=json.dumps(std_in),
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                print(f"[recompile] {addr}: solc non-zero exit")
                log_failure("recompile", addr, proc.stderr[:500])
                continue

            result = json.loads(proc.stdout)
            errors = [e for e in result.get("errors", []) if e.get("severity") == "error"]
            if errors:
                print(f"[recompile] {addr}: COMPILE ERRORS")
                for e in errors[:3]:
                    print("   ", e.get("formattedMessage", e.get("message"))[:200])
                log_failure("recompile", addr, errors[0].get("message"))
                continue

            target = settings["contract_name"]
            out_dir = out_root / addr.lower() / "etherscan"
            out_dir.mkdir(parents=True, exist_ok=True)

            found = False
            for fname, contracts in result.get("contracts", {}).items():
                if target in contracts:
                    c = contracts[target]
                    (out_dir / "creation.hex").write_text(c["evm"]["bytecode"]["object"])
                    (out_dir / "runtime.hex").write_text(c["evm"]["deployedBytecode"]["object"])
                    (out_dir / "metadata.json").write_text(c["metadata"])
                    found = True
                    break
            print(f"[recompile] {addr}: {'OK' if found else 'TARGET NOT FOUND'}")
            if not found:
                log_failure("recompile", addr, f"contract '{target}' not in solc output")
        except Exception as e:
            print(f"[recompile] {addr}: FAILED - {e}")
            log_failure("recompile", addr, e)