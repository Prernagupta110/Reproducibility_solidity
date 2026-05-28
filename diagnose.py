from utils import CONTRACTS, DATA_DIR
from causes import KNOWN_CAUSES, classify_regions

ONCHAIN = DATA_DIR / "onchain"
COMPILED = DATA_DIR / "compiled"


import re as _re


def read(p):
    if not p.exists():
        return None
    txt = p.read_text().strip().lower().removeprefix("0x")
    if not txt:
        return None
    # Unlinked-library placeholder (__$...$__ or __Lib.sol:Name___)
    if "__$" in txt or _re.search(r"__[a-z]", txt):
        return ("UNLINKED", txt)
    if any(c not in "0123456789abcdef" for c in txt):
        return ("BADHEX", txt)
    return txt


def strip_meta(hex_str):
    try:
        b = bytes.fromhex(hex_str)
    except ValueError:
        clean = _re.sub(r"[^0-9a-f]", "", hex_str.lower())
        if len(clean) % 2:
            clean = clean[:-1]
        b = bytes.fromhex(clean)
    if len(b) < 4:
        return hex_str, ""
    cbor_len = int.from_bytes(b[-2:], "big")
    if cbor_len + 2 > len(b) or cbor_len == 0:
        return hex_str, ""
    return b[:-(cbor_len + 2)].hex(), b[-(cbor_len + 2):].hex()


def find_regions(a, b, min_run_bytes=2):
    min_run = min_run_bytes * 2
    regions, i, n = [], 0, min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            start = i
            while i < n and a[i] != b[i]:
                i += 1
            if i - start >= min_run:
                regions.append({"start": start // 2, "end": i // 2,
                                "onchain": a[start:i], "local": b[start:i]})
        else:
            i += 1
    if len(a) != len(b):
        m = min(len(a), len(b))
        regions.append({"start": m // 2, "end": max(len(a), len(b)) // 2,
                        "onchain": a[m:], "local": b[m:]})
    return regions


def diagnose_pair(label, onchain_hex, local_hex):
    print(f"\n{'='*72}\n{label}\n{'='*72}")
    on_strip, on_meta = strip_meta(onchain_hex)
    lo_strip, lo_meta = strip_meta(local_hex)

    print(f"  on-chain {len(onchain_hex)//2}B  local {len(local_hex)//2}B  "
          f"metadata: {'IDENTICAL' if on_meta == lo_meta else 'DIFFERS'}")

    if on_strip == lo_strip:
        print("  body identical -> PARTIAL_MATCH (only the metadata trailer differs)")
        return

    regions = find_regions(on_strip, lo_strip)
    verdict, per_region, detail = classify_regions(regions)
    print(f"  body diff: {len(regions)} region(s) >= 2 bytes   verdict: {verdict}")

    for idx, (r, labels) in enumerate(zip(regions[:15], per_region[:15])):
        print(f"    region {idx}: bytes {r['start']}-{r['end']} "
              f"({r['end']-r['start']}B) -> {', '.join(labels)}")
        print(f"      on-chain: {r['onchain'][:60]}{'...' if len(r['onchain'])>60 else ''}")
        print(f"      local   : {r['local'][:60]}{'...' if len(r['local'])>60 else ''}")

    print("  documented causes detected:", detail["known"] or "none",
          f"| unexplained regions: {detail['unknown_regions']}")


if __name__ == "__main__":
    print("Known cause detectors:")
    for name, _, source in KNOWN_CAUSES:
        print(f"  - {name}  ({source})")

    for addr in CONTRACTS:
        for kind in ("runtime", "creation"):
            onchain = read(ONCHAIN / f"{addr.lower()}.{kind}.hex")
            if not onchain or isinstance(onchain, tuple):
                continue
            for src in ("etherscan", "sourcify"):
                local = read(COMPILED / addr.lower() / src / f"{kind}.hex")
                if not local:
                    continue
                if isinstance(local, tuple):
                    tag = local[0]
                    print("=" * 72)
                    print(f"{addr}  [{kind}]  source={src}")
                    print("=" * 72)
                    if tag == "UNLINKED":
                        print("  local build has UNLINKED LIBRARY placeholder(s)")
                        print("  (__$...$__ or __Lib.sol:Name___): the library address")
                        print("  was not provided to solc, so the bytecode cannot match")
                        print("  on-chain. Cause: UNLINKED_LIBRARY.")
                    else:
                        print("  local build contains unexpected non-hex content "
                              "(investigate; not auto-stripped).")
                    continue
                if onchain == local:
                    continue
                diagnose_pair(f"{addr}  [{kind}]  source={src}", onchain, local)