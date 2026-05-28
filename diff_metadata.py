import json
from pathlib import Path
from utils import CONTRACTS, DATA_DIR

REPORTS = DATA_DIR / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


def load(path: Path):
    #Load a JSON file, or return None if missing/invalid
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def diff_dicts(a, b, path=""):
   
    diffs = []
    keys = set(a.keys() if isinstance(a, dict) else []) | \
           set(b.keys() if isinstance(b, dict) else [])
    for k in sorted(keys):
        new_path = f"{path}.{k}" if path else k
        va = a.get(k) if isinstance(a, dict) else None
        vb = b.get(k) if isinstance(b, dict) else None
        if isinstance(va, dict) and isinstance(vb, dict):
            diffs.extend(diff_dicts(va, vb, new_path))     
        elif va != vb:
            diffs.append((new_path, json.dumps(va)[:200], json.dumps(vb)[:200]))
    return diffs


machine_output = []   # for analyze.py 

for addr in CONTRACTS:
    print(f"\n{'='*72}\n{addr}\n{'='*72}")

    # the deployer's ORIGINAL metadata, as recorded by Sourcify.
    original = load(DATA_DIR / "sourcify" / addr.lower() / "metadata.json")
    # two locally-recompiled metadata files.
    local_es = load(DATA_DIR / "compiled" / addr.lower() / "etherscan" / "metadata.json")
    local_sf = load(DATA_DIR / "compiled" / addr.lower() / "sourcify" / "metadata.json")

    if original is None:
        print("  No Sourcify metadata to compare against (contract may be absent there).")
        machine_output.append({"address": addr, "comparison": "no_sourcify_original"})
        continue

    for label, local in [("local-from-etherscan-sources", local_es),
                         ("local-from-sourcify-sources", local_sf)]:
        if local is None:
            print(f"\n  [{label}] no local metadata file (recompile may have failed)")
            machine_output.append({"address": addr, "comparison": label,
                                   "result": "missing_local"})
            continue

        print(f"\n  -- {label}  vs  Sourcify original --")
        diffs = diff_dicts(original, local)
        if not diffs:
            print("    metadata.json IDENTICAL "
                  "(any hash mismatch is then only key-ordering/whitespace)")
            machine_output.append({"address": addr, "comparison": label,
                                   "result": "identical", "differing_fields": []})
            continue

       
        machine_output.append({
            "address": addr, "comparison": label, "result": "differs",
            "differing_fields": [p for p, _, _ in diffs],
        })
        for p, va, vb in diffs[:30]:
            print(f"    {p}")
            print(f"      original: {va}")
            print(f"      local   : {vb}")
        if len(diffs) > 30:
            print(f"    ... and {len(diffs) - 30} more differing fields")

(REPORTS / "metadata_diffs.json").write_text(json.dumps(machine_output, indent=2))
print(f"\nMachine-readable diffs -> {REPORTS / 'metadata_diffs.json'}")