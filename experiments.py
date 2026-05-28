import sys
import json
import csv
import subprocess
import argparse
from pathlib import Path
from utils import DATA_DIR
from recompile import build_standard_input, ensure_solc

REPORTS = DATA_DIR / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
ONCHAIN = DATA_DIR / "onchain"
SRC_ROOT = DATA_DIR / "etherscan"


# build-environment 
BASE_SOURCE = (
    "// SPDX-License-Identifier: MIT\n"
    "pragma solidity ^0.8.20;\n"
    "\n"
    "contract EnvTest {\n"
    "    uint256 public value;\n"
    "    function set(uint256 v) external { value = v; }\n"
    "}\n"
)
FIXED_SETTINGS = {
    "optimizer": {"enabled": True, "runs": 200},
    "outputSelection": {"*": {"*": ["evm.deployedBytecode.object"]}},
}
VARIANTS = [
    ("baseline",          "Contract.sol",     BASE_SOURCE),
    ("crlf_line_endings", "Contract.sol",     BASE_SOURCE.replace("\n", "\r\n")),
    ("no_final_newline",  "Contract.sol",     BASE_SOURCE.rstrip("\n")),
    ("trailing_spaces",   "Contract.sol",     BASE_SOURCE.replace(";\n", ";   \n")),
    ("nested_path",       "src/Contract.sol", BASE_SOURCE),
]


def _compile_variant(filename, source):
    std_in = {"language": "Solidity",
              "sources": {filename: {"content": source}},
              "settings": FIXED_SETTINGS}
    proc = subprocess.run(["solc", "--standard-json"], input=json.dumps(std_in),
                          capture_output=True, text=True)
    out = json.loads(proc.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise RuntimeError(errs[0].get("formattedMessage", errs[0].get("message")))
    for _, contracts in out["contracts"].items():
        for _, c in contracts.items():
            return c["evm"]["deployedBytecode"]["object"]
    raise RuntimeError("no contract in output")


def _strip_trailer(hex_str):
    b = bytes.fromhex(hex_str)
    if len(b) < 4:
        return hex_str, ""
    n = int.from_bytes(b[-2:], "big")
    if n + 2 > len(b):
        return hex_str, ""
    return b[:-(n + 2)].hex(), b[-(n + 2):].hex()


def run_build_env():
   
    subprocess.run(["solc-select", "install", "0.8.20"], capture_output=True, text=True)
    subprocess.run(["solc-select", "use", "0.8.20"], capture_output=True, text=True)
    v = subprocess.run(["solc", "--version"], capture_output=True, text=True)
    print("solc:", v.stdout.strip().splitlines()[-1] if v.stdout else "unknown")
    print()

    results = {}
    for label, fname, src in VARIANTS:
        try:
            full = _compile_variant(fname, src)
            code, meta = _strip_trailer(full)
            results[label] = {"full": full, "code": code, "meta": meta}
        except Exception as e:
            results[label] = {"error": str(e)[:200]}
            print(f"[{label}] FAILED: {e}")

    base = results.get("baseline", {})
    rows = []
    print(f"{'variant':<20}{'code_same?':<12}{'meta_same?':<12}{'verdict'}")
    print("-" * 70)
    for label, r in results.items():
        if "error" in r:
            rows.append({"variant": label, "code_identical": "ERROR",
                         "meta_identical": "ERROR", "verdict": r["error"]})
            continue
        code_same = (r["code"] == base.get("code"))
        meta_same = (r["meta"] == base.get("meta"))
        if label == "baseline":
            verdict = "(reference)"
        elif code_same and meta_same:
            verdict = "FULLY reproducible (no effect)"
        elif code_same and not meta_same:
            verdict = "code identical, metadata differs -> PARTIAL only"
        else:
            verdict = "CODE CHANGED -> real non-reproducibility"
        rows.append({"variant": label,
                     "code_identical": code_same, "meta_identical": meta_same,
                     "verdict": verdict})
        print(f"{label:<20}{str(code_same):<12}{str(meta_same):<12}{verdict}")

    out = REPORTS / "build_env_experiment.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["variant", "code_identical",
                                          "meta_identical", "verdict"])
        w.writeheader(); w.writerows(rows)
    print(f"\nSaved: {out}")

#patch-sweep
def _read_hex(p):
    if not p.exists():
        return None
    return p.read_text().strip().lower().removeprefix("0x") or None


def _strip_for_compare(hex_str):
    b = bytes.fromhex(hex_str)
    if len(b) < 4:
        return hex_str
    n = int.from_bytes(b[-2:], "big")
    if 0 < n + 2 <= len(b):
        return b[:-(n + 2)].hex()
    return hex_str


def _common_prefix_bytes(a, b):
    i, m = 0, min(len(a), len(b))
    while i < m and a[i] == b[i]:
        i += 1
    return i // 2


def _sweep_one(addr, kind, versions=None, quiet=False):
    addr = addr.lower()
    contract_dir = SRC_ROOT / addr
    settings_file = contract_dir / "settings.json"
    if not settings_file.exists():
        return None
    settings = json.loads(settings_file.read_text())
    recorded = settings["compiler_version"]
    target_name = settings["contract_name"]

    onchain_raw = _read_hex(ONCHAIN / f"{addr}.{kind}.hex")
    if not onchain_raw:
        return None
    onchain_code = _strip_for_compare(onchain_raw)

    if versions:
        candidates = versions
    else:
        base = recorded.lstrip("v").split("+")[0]
        major, minor, patch = (base.split(".") + ["0", "0", "0"])[:3]
        minor, patch = int(minor), int(patch)
        lo = max(0, patch - 1)
        candidates = [f"{major}.{minor}.{p}" for p in range(lo, patch + 5)]

    std_in_file = contract_dir / "standard_input.json"
    if std_in_file.exists():
        std_in = json.loads(std_in_file.read_text())
        std_in.setdefault("settings", {})["outputSelection"] = {
            "*": {"*": ["evm.bytecode.object", "evm.deployedBytecode.object"]}}
    else:
        std_in = build_standard_input(contract_dir, settings)

    field = "bytecode" if kind == "creation" else "deployedBytecode"
    rec = recorded.lstrip('v').split('+')[0]
    rows = []
    if not quiet:
        print(f"\nContract {addr}  ({target_name})  recorded={recorded}  kind={kind}")
        print(f"{'solc version':<16}{'compiles?':<11}{'CODE match?':<13}{'first diff @ byte'}")
        print("-" * 64)
    for ver in candidates:
        row = {"version": ver, "recorded": (ver == rec)}
        try:
            ensure_solc(ver)
        except Exception:
            row.update({"compiles": "INSTALL_FAIL", "match": "", "first_diff": ""})
            rows.append(row)
            if not quiet:
                print(f"{ver:<16}{'install fail':<11}")
            continue
        proc = subprocess.run(["solc", "--standard-json"], input=json.dumps(std_in),
                              capture_output=True, text=True)
        try:
            out = json.loads(proc.stdout)
        except Exception:
            row.update({"compiles": "NO", "match": "", "first_diff": ""})
            rows.append(row); continue
        errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
        if errs:
            row.update({"compiles": "NO", "match": "", "first_diff": ""})
            rows.append(row)
            if not quiet:
                print(f"{ver:<16}{'error':<11}")
            continue
        local_code = None
        for _, contracts in out.get("contracts", {}).items():
            if target_name in contracts:
                local_code = _strip_for_compare(
                    contracts[target_name]["evm"][field]["object"].lower())
                break
        if local_code is None:
            row.update({"compiles": "YES", "match": "TARGET_NOT_FOUND", "first_diff": ""})
            rows.append(row); continue
        match = (local_code == onchain_code)
        fd = "" if match else _common_prefix_bytes(onchain_code, local_code)
        row.update({"compiles": "YES", "match": str(match), "first_diff": fd})
        rows.append(row)
        if not quiet:
            mark = " <-- recorded version" if row["recorded"] else ""
            print(f"{ver:<16}{'yes':<11}{str(match):<13}{fd}{mark}")

    matches = [r["version"] for r in rows if r.get("match") == "True"]
    verdict = ("PATCH_DRIFT" if (matches and rec not in matches)
               else "RECORDED_MATCHES" if rec in matches
               else "NO_PATCH_MATCHED")
    return {"address": addr, "kind": kind, "contract_name": target_name,
            "recorded": rec, "matched_versions": matches, "verdict": verdict,
            "rows": rows}


def run_patch_sweep(args):
    r = _sweep_one(args.address, args.kind, args.versions, quiet=False)
    if r is None:
        sys.exit(f"No data for {args.address} ({args.kind}); "
                 "run fetch_etherscan + recompile first.")
    out_csv = REPORTS / f"patch_sweep_{r['address']}.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["version", "recorded", "compiles",
                                          "match", "first_diff"])
        w.writeheader(); w.writerows(r["rows"])
    print(f"\nSaved: {out_csv}")
    print("\nINTERPRETATION:")
    if r["verdict"] == "PATCH_DRIFT":
        print(f"  CODE reproduced by: {', '.join(r['matched_versions'])}")
        print("  The RECORDED version did NOT match but another patch DID")
        print("  -> patch-version drift is the cause of the codegen difference.")
    elif r["verdict"] == "RECORDED_MATCHES":
        print("  Recorded version matched; the difference is elsewhere.")
    else:
        print("  No tested patch reproduced the code. Try a wider --versions range,")
        print("  or another factor (optimizer/evmVersion/viaIR/source).")


def run_patch_sweep_all(kind="creation", versions=None):
    """Sweep patch versions for EVERY contract that shows a real code-level
    difference (per comparison.csv), since metadata-only PARTIAL matches and
    FULL matches have nothing for patch-drift to explain."""
    comp = REPORTS / "comparison.csv"
    # Decide which contracts are worth sweeping: those with a real (non-metadata,
    # non-missing) difference. If comparison.csv is absent, sweep all contracts.
    targets = []
    if comp.exists():
        #  - FULL/PARTIAL: code already matches (nothing for patch to explain)
        #  - MISSING: no data
        #  - UNLINKED_LIBRARY: differs because of an unprovided library address
        #  - IMMUTABLE_VAR_ONLY: immutables are runtime-injected; CANNOT be
        #    reproduced by recompiling under any patch version
        #  - TRAILING_DATA_ONLY: differs only by constructor args, not codegen
        # What remains are genuine codegen differences, where a different patch could plausibly reproduce the code.
        skip = {"FULL_MATCH", "PARTIAL_MATCH", "MISSING_DATA", "MISSING_ONCHAIN",
                "UNLINKED_LIBRARY", "BADHEX_LOCAL", "COMPARE_ERROR",
                "IMMUTABLE_VAR_ONLY", "TRAILING_DATA_ONLY", "EMBEDDED_METADATA_ONLY"}
        seen = set()
        for r in csv.DictReader(open(comp)):
            key = (r["address"].lower(), r["kind"])
            if r["status"] not in skip and key not in seen:
                seen.add(key)
                targets.append((r["address"], r["kind"]))
    else:
        targets = [(a, kind) for a in CONTRACTS]

    if not targets:
        print("No real-codegen-difference contracts to sweep ")
        return

    print(f"Patch-sweeping {len(targets)} contract/kind pair(s) with a real "
          f"code difference...\n")
    summary = []
    for addr, k in targets:
        r = _sweep_one(addr, k, versions, quiet=True)
        if r is None:
            continue
        summary.append({"address": r["address"], "kind": r["kind"],
                        "contract_name": r["contract_name"],
                        "recorded": r["recorded"],
                        "matched_versions": ";".join(r["matched_versions"]),
                        "verdict": r["verdict"]})
        print(f"  {r['address'][:12]} {r['kind']:<8} {r['verdict']:<18} "
              f"matched: {','.join(r['matched_versions']) or '(none)'}")

    out_csv = REPORTS / "patch_sweep_all.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["address", "kind", "contract_name",
                                          "recorded", "matched_versions", "verdict"])
        w.writeheader(); w.writerows(summary)

    from collections import Counter
    verdicts = Counter(s["verdict"] for s in summary)
    print("\nSummary across swept contracts:")
    for v, n in verdicts.most_common():
        print(f"  {v}: {n}")
    print(f"\nSaved: {out_csv}")
    print("\nPATCH_DRIFT = a different solc patch reproduced the code -> the recorded")
    print("  version is not what actually built it (compiler patch-version drift).")

# RQ3 demo: source files differing only in NAME / COMMENTS / WHITESPACE compile
# to IDENTICAL executable bytecode but a DIFFERENT metadata trailer -> PARTIAL
# match, never FULL. 
_RA_BASE = ("// SPDX-License-Identifier: MIT\npragma solidity ^0.8.20;\n\n"
            "contract {name} {{\n    uint256 public value;        {comment}\n"
            "    function set(uint256 v) external {{ value = v; }}\n}}\n")
_RA_SCENARIOS = {
    "baseline":         ("Original.sol", "Original", "",                ""),
    "file_renamed":     ("Renamed.sol",  "Original", "",                ""),
    "contract_renamed": ("Original.sol", "RenamedC", "",                ""),
    "comment_changed":  ("Original.sol", "Original", "// totally safe", ""),
    "whitespace_added": ("Original.sol", "Original", "",                "   "),
}


def _ra_compile(filename, name, comment, ws):
    src = _RA_BASE.format(name=name, comment=comment) + ws
    std_in = {"language": "Solidity", "sources": {filename: {"content": src}},
              "settings": {"optimizer": {"enabled": True, "runs": 200},
                           "outputSelection": {"*": {"*": ["evm.deployedBytecode.object"]}}}}
    out = json.loads(subprocess.run(["solc", "--standard-json"], input=json.dumps(std_in),
                                    capture_output=True, text=True, check=True).stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise RuntimeError(errs[0].get("formattedMessage", errs[0].get("message")))
    return out["contracts"][filename][name]["evm"]["deployedBytecode"]["object"]


def _ra_split(hex_str):
    b = bytes.fromhex(hex_str)
    if len(b) < 4:
        return hex_str, ""
    n = int.from_bytes(b[-2:], "big")
    if 0 < n + 2 <= len(b):
        return b[:-(n + 2)].hex(), b[-(n + 2):].hex()
    return hex_str, ""


def run_rename_attack():
    import hashlib
    subprocess.run(["solc-select", "install", "0.8.20"], capture_output=True, text=True)
    subprocess.run(["solc-select", "use", "0.8.20"], capture_output=True, text=True)
    sha = lambda s: hashlib.sha256(bytes.fromhex(s)).hexdigest()[:12] if s else "(empty)"
    results = {}
    print(f"{'scenario':<18}{'code_sha':<14}{'meta_sha':<14}")
    print("-" * 46)
    for label, (fn, nm, cm, ws) in _RA_SCENARIOS.items():
        code, meta = _ra_split(_ra_compile(fn, nm, cm, ws))
        results[label] = (code, meta)
        print(f"{label:<18}{sha(code):<14}{sha(meta):<14}")
    base_code = results["baseline"][0]
    all_code_identical = all(c == base_code for c, _ in results.values())
    print("\nVERDICT:")
    if all_code_identical:
        print("  All scenarios produce IDENTICAL executable code; only the metadata")
        print("  trailer changes (name/comment/whitespace feed the source keccak256")
        print("  -> IPFS hash in the trailer). Each is PARTIAL, never FULL. RQ3 confirmed.")
    else:
        print("  Unexpected: a scenario changed the code section. Investigate.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "build_env":
        run_build_env()
    elif cmd == "patch_sweep":
        # No address -> sweep ALL contracts with a real code difference.
        # With an address -> sweep just that one (detailed table).
        ap = argparse.ArgumentParser()
        ap.add_argument("address", nargs="?", default=None)
        ap.add_argument("--versions", nargs="*", default=None)
        ap.add_argument("--kind", default="creation", choices=["creation", "runtime"])
        args = ap.parse_args(sys.argv[2:])
        if args.address:
            run_patch_sweep(args)
        else:
            run_patch_sweep_all(kind=args.kind, versions=args.versions)
    elif cmd == "rename_attack":
        run_rename_attack()
    else:
        sys.exit(f"unknown subcommand: {cmd!r}; "
                 "use 'build_env', 'patch_sweep', or 'rename_attack'")