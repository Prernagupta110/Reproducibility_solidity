"""
compare.py  --  The main classifier. Three-way comparison:
    on-chain bytecode   vs   Etherscan-recompiled   vs   Sourcify-recompiled

STATUS VALUES (per contract, per kind, per source):
    FULL_MATCH             bit-identical, including the metadata trailer
    PARTIAL_MATCH          identical after stripping the CBOR trailer
    <CAUSE>_ONLY           body differs only by a documented cause (e.g.
                           IMMUTABLE_VAR_ONLY, UNLINKED_LIBRARY_ONLY)
    MIXED_KNOWN            multiple known causes, all explained
    PARTIAL_KNOWN          some known causes + some unexplained regions
    NOT_YET_DISTINGUISHED  body differs for reasons we have not classified yet
    MISSING_DATA           that source did not provide bytecode
    MISSING_ONCHAIN        we have no on-chain bytecode to compare against

"""
import csv
import json
from utils import CONTRACTS, DATA_DIR
from causes import classify_regions

ONCHAIN = DATA_DIR / "onchain"
COMPILED = DATA_DIR / "compiled"
ETHERSCAN_SRC = DATA_DIR / "etherscan"
REPORTS = DATA_DIR / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


import re as _re

# Solidity unlinked-library placeholder patterns 
#   new format: __$<34 hex chars>$__   (keccak prefix of fq library name)
#   old format: __LibFile.sol:LibName___  (padded with underscores to 40 chars)
# Their presence means solc compiled WITHOUT the library address -> the bytecode
# is UNLINKED. We must NOT strip these (that corrupts the bytecode); 
_PLACEHOLDER_RE = _re.compile(r"__\$[0-9a-fA-F]{34}\$__|__[^_]{1,36}_+")


def has_library_placeholder(txt: str) -> bool:
    #True if the bytecode text contains an unlinked-library placeholder
    return "__$" in txt or _re.search(r"__[a-zA-Z]", txt) is not None


def read(p):
    """Read a hex file, lowercase, strip 0x. Return None if missing/empty.
    If the file contains UNLINKED LIBRARY placeholders (__$...$__ or
    __Lib.sol:Name___), return the sentinel ('UNLINKED', original_text) so the
    caller can classify it as UNLINKED_LIBRARY instead of crashing or, worse,
    silently corrupting the bytecode by stripping the placeholder characters."""
    if not p.exists():
        return None
    txt = p.read_text().strip().lower().removeprefix("0x")
    if not txt:
        return None
    if has_library_placeholder(txt):
   
        return ("UNLINKED", txt)

    if any(c not in "0123456789abcdef" for c in txt):
        bad = [c for c in set(txt) if c not in "0123456789abcdef"]
        print(f"  [WARN] {p.name}: unexpected non-hex chars {bad} "
              f"(NOT a library placeholder) -- investigate, not auto-stripped")
        return ("BADHEX", txt)
    return txt


def strip_metadata_inline(hex_str: str) -> str:
    """Drop the CBOR trailer using the last-2-bytes length encoding."""
    try:
        b = bytes.fromhex(hex_str)
    except ValueError:
        
        clean = _re.sub(r"[^0-9a-f]", "", hex_str.lower())
        if len(clean) % 2:
            clean = clean[:-1]
        b = bytes.fromhex(clean)
    if len(b) < 4:
        return hex_str
    cbor_len = int.from_bytes(b[-2:], "big")
    if cbor_len + 2 > len(b) or cbor_len == 0:
        return hex_str
    return b[:-(cbor_len + 2)].hex()


def strip_constructor_args(creation_hex: str, ctor_args_hex: str) -> str:
    """
    Constructor args are ABI-encoded and appended to the END of on-chain creation
    bytecode. Local recompilation does not include them, so I strip them from
    on-chain to compare 
    """
    if not ctor_args_hex:
        return creation_hex
    ctor_args_hex = ctor_args_hex.lower().removeprefix("0x")
    if creation_hex.endswith(ctor_args_hex):
        return creation_hex[:-len(ctor_args_hex)]
    return creation_hex   


def find_regions(a: str, b: str, min_run_bytes=2):
 
    min_run = min_run_bytes * 2   # in hex chars
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
    if len(a) != len(b):           # length mismatch -> record the tail
        m = min(len(a), len(b))
        regions.append({"start": m // 2, "end": max(len(a), len(b)) // 2,
                        "onchain": a[m:], "local": b[m:]})
    return regions


def first_diff_byte(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i // 2
    if len(a) != len(b):
        return min(len(a), len(b)) // 2
    return None


def get_ctor_args(addr: str) -> str:
    f = ETHERSCAN_SRC / addr.lower() / "settings.json"
    if not f.exists():
        return ""
    return json.loads(f.read_text()).get("constructor_arguments", "")


def classify(onchain_hex, local_hex, kind, ctor_args):
  
    if local_hex is None:
        return "MISSING_DATA", None

    # For creation bytecode, remove the appended constructor args first.
    if kind == "creation" and ctor_args:
        onchain_hex = strip_constructor_args(onchain_hex, ctor_args)

    if onchain_hex == local_hex:
        return "FULL_MATCH", None

    on_strip = strip_metadata_inline(onchain_hex)
    lo_strip = strip_metadata_inline(local_hex)
    if on_strip == lo_strip:
        return "PARTIAL_MATCH", len(on_strip) // 2

    # Body differs -> derive the cause PER CONTRACT from its own regions.
    regions = find_regions(on_strip, lo_strip)
    verdict, _, _ = classify_regions(regions)
    return verdict, first_diff_byte(on_strip, lo_strip)


SOURCES = {"etherscan": "etherscan", "sourcify": "sourcify"}

rows = []

if __name__ == "__main__":
    for addr in CONTRACTS:
        ctor_args = get_ctor_args(addr)
        for kind in ("runtime", "creation"):
            onchain_hex = read(ONCHAIN / f"{addr.lower()}.{kind}.hex")
            if onchain_hex is None:
                for src in SOURCES:
                    rows.append({"address": addr, "kind": kind, "source": src,
                                 "status": "MISSING_ONCHAIN", "onchain_size": None,
                                 "local_size": None, "first_diff_byte": None})
                continue
           
            if isinstance(onchain_hex, tuple):
                tag = onchain_hex[0]
                for src in SOURCES:
                    rows.append({"address": addr, "kind": kind, "source": src,
                                 "status": f"ONCHAIN_{tag}", "onchain_size": None,
                                 "local_size": None, "first_diff_byte": None})
                continue
            for src_label, folder in SOURCES.items():
                local_hex = read(COMPILED / addr.lower() / folder / f"{kind}.hex")
                # If LOCAL recompile contains unlinked-library placeholders, the
                # library address was not provided to solc -> classified as
                # UNLINKED_LIBRARY rather than comparing corrupted bytecode.
                if isinstance(local_hex, tuple):
                    tag = local_hex[0]   # "UNLINKED" or "BADHEX"
                    status = "UNLINKED_LIBRARY" if tag == "UNLINKED" else "BADHEX_LOCAL"
                    rows.append({
                        "address": addr, "kind": kind, "source": src_label,
                        "status": status,
                        "onchain_size": len(onchain_hex) // 2,
                        "local_size": None, "first_diff_byte": None,
                    })
                    continue
                try:
                    status, diff_at = classify(onchain_hex, local_hex, kind, ctor_args)
                except Exception as e:
                    # One bad contract must not halt the whole loop.
                    print(f"  [error] {addr} {kind}/{src_label}: {str(e)[:80]}")
                    status, diff_at = "COMPARE_ERROR", None
                rows.append({
                    "address": addr, "kind": kind, "source": src_label,
                    "status": status,
                    "onchain_size": len(onchain_hex) // 2,
                    "local_size": len(local_hex) // 2 if local_hex else None,
                    "first_diff_byte": diff_at,
                })

    csv_path = REPORTS / "comparison.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{'address':<44}{'kind':<10}{'source':<10}{'status':<22}{'diff@'}")
    print("-" * 100)
    for r in rows:
        print(f"{r['address']:<44}{r['kind']:<10}{r['source']:<10}"
              f"{r['status']:<22}{r['first_diff_byte']}")
    print(f"\nReport saved: {csv_path}")