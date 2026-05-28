import argparse
import random
from pathlib import Path

OUT = Path(__file__).parent / "contracts.txt"


def major_version(v: str) -> str:
    v = v.lstrip("v")
    parts = v.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="total sample size")
    ap.add_argument("--seed", type=int, default=42, help="random seed (reproducible)")
    ap.add_argument("--subset", default="raw", choices=["raw", "decomposed"],
                    help="DISL subset; 'raw' keeps multi-file contracts intact")
    ap.add_argument("--no-pilot", dest="include_pilot", action="store_false",
                    help="exclude the 13 curated pilot contracts (default: include them)")
    ap.set_defaults(include_pilot=True)
    args = ap.parse_args()

    from datasets import load_dataset

    print(f"Loading DISL ({args.subset}) from HuggingFace; this streams, "
          f"so it does not download all 270k rows at once...")

    ds = load_dataset("ASSERT-KTH/DISL", args.subset, split="train", streaming=True)

    random.seed(args.seed)
    buckets = {}      
    CAP_PER_BUCKET = max(50, args.n)   
    seen = 0
    for row in ds:
        seen += 1
        key = (
            major_version(row.get("compiler_version", "")),
            bool(row.get("optimization_used")),
            bool(row.get("proxy")),
            bool(row.get("library")),          
        )
        b = buckets.setdefault(key, [])
        if len(b) < CAP_PER_BUCKET:
            b.append({
                "address": row["contract_address"],
                "name": row.get("contract_name", ""),
                "compiler": row.get("compiler_version", ""),
                "optimizer": bool(row.get("optimization_used")),
                "proxy": bool(row.get("proxy")),
                "has_library": bool(row.get("library")),
            })
        if seen >= 60000 and all(len(v) >= 5 for v in buckets.values()):
            break
        if seen >= 200000:     
            break

    print(f"Scanned {seen} rows, found {len(buckets)} strata.")

    total_candidates = sum(len(v) for v in buckets.values())
    chosen = []
    for key, rows in buckets.items():
        share = max(1, round(args.n * len(rows) / total_candidates))
        chosen.extend(random.sample(rows, min(share, len(rows))))

 
    random.shuffle(chosen)
    chosen = chosen[:args.n]

    # De-duplicate addresses 
    seen_addr = set()
    unique = []
    for c in chosen:
        a = c["address"].lower()
        if a not in seen_addr:
            seen_addr.add(a)
            unique.append(c)

    # 13 contracts from utils._PILOT_CONTRACTS.   
    pilot_addrs = []
    if args.include_pilot:
        try:
            from utils import _PILOT_CONTRACTS
            for a in _PILOT_CONTRACTS:
                if a.lower() not in seen_addr:
                    seen_addr.add(a.lower())
                    pilot_addrs.append(a)
        except Exception as e:
            print(f"(could not import pilot contracts: {e})")

    all_addrs = pilot_addrs + [c["address"] for c in unique]
    OUT.write_text("\n".join(all_addrs) + "\n")

    print(f"\nWrote {len(all_addrs)} total addresses -> {OUT.name}")
    print(f"  - {len(pilot_addrs)} curated pilot contracts")
    print(f"  - {len(unique)} DISL-sampled contracts")
    print("\nDISL sample composition:")
    from collections import Counter
    by_ver = Counter(major_version(c["compiler"]) for c in unique)
    print("  by compiler major version:", dict(sorted(by_ver.items())))
    print("  optimizer on:", sum(c["optimizer"] for c in unique),
          "| off:", sum(not c["optimizer"] for c in unique))
    print("  proxy:", sum(c["proxy"] for c in unique),
          "| non-proxy:", sum(not c["proxy"] for c in unique))
    print("  has library:", sum(c["has_library"] for c in unique),
          "| none:", sum(not c["has_library"] for c in unique))


if __name__ == "__main__":
    main()