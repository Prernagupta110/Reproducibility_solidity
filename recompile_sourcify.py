import json
import subprocess
from utils import CONTRACTS, DATA_DIR, log_failure

src_root = DATA_DIR / "sourcify"
out_root = DATA_DIR / "compiled"
out_root.mkdir(parents=True, exist_ok=True)

_installed = None

from recompile import ensure_solc, get_installed_solc_versions


def build_standard_input(contract_dir, settings):
    src_tree = contract_dir / "sources"
    if not src_tree.exists():
        raise FileNotFoundError(f"No sources/ folder in {contract_dir}")

    sources = {}
    for f in src_tree.rglob("*.sol"):
        rel = f.relative_to(src_tree).as_posix()   
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
    evm = settings.get("evm_version")
    if evm and evm != "Default":
        std_settings["evmVersion"] = evm.lower()
    if settings.get("via_ir"):
        std_settings["viaIR"] = True
    if settings.get("libraries"):
        std_settings["libraries"] = settings["libraries"]
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
                print(f"[recompile-sourcify] no Sourcify data for {addr}, skipping")
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
                print(f"[recompile-sourcify] {addr}: solc non-zero exit")
                log_failure("recompile_sourcify", addr, proc.stderr[:500])
                continue

            result = json.loads(proc.stdout)
            errors = [e for e in result.get("errors", []) if e.get("severity") == "error"]
            if errors:
                print(f"[recompile-sourcify] {addr}: COMPILE ERRORS")
                for e in errors[:3]:
                    print("   ", e.get("formattedMessage", e.get("message"))[:200])
                log_failure("recompile_sourcify", addr, errors[0].get("message"))
                continue

            target_name = settings["contract_name"]
            target_path = settings.get("contract_path", "")
            out_dir = out_root / addr.lower() / "sourcify"
            out_dir.mkdir(parents=True, exist_ok=True)

            contracts_map = result.get("contracts", {})
            found = False

            if target_path in contracts_map and target_name in contracts_map[target_path]:
                c = contracts_map[target_path][target_name]
                found = True
            else:
                for fname, contracts in contracts_map.items():
                    if target_name in contracts:
                        c = contracts[target_name]
                        found = True
                        break

            if found:
                (out_dir / "creation.hex").write_text(c["evm"]["bytecode"]["object"])
                (out_dir / "runtime.hex").write_text(c["evm"]["deployedBytecode"]["object"])
                (out_dir / "metadata.json").write_text(c["metadata"])
                print(f"[recompile-sourcify] {addr}: OK")
            else:
                print(f"[recompile-sourcify] {addr}: target '{target_name}' not found")
                log_failure("recompile_sourcify", addr, f"'{target_name}' not in output")
        except Exception as e:
            print(f"[recompile-sourcify] {addr}: FAILED - {e}")
            log_failure("recompile_sourcify", addr, e)