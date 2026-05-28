import sys
import json
from pathlib import Path
from utils import (ETHERSCAN_API_KEY, CHAIN_ID, get_with_retry, post_rpc,
                   etherscan_rate_limit, require_secrets, DATA_DIR)

ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"
ONCHAIN = DATA_DIR / "onchain"
COMPILED = DATA_DIR / "compiled"
HEXSET = set("0123456789abcdef")

def debug_creation(addr: str):
    
    require_secrets()
    etherscan_rate_limit()
    params = {"chainid": CHAIN_ID, "module": "contract",
              "action": "getcontractcreation",
              "contractaddresses": addr, "apikey": ETHERSCAN_API_KEY}
    es = get_with_retry(ETHERSCAN_V2, params=params).json()

    print("=== Raw getcontractcreation response ===")
    print(json.dumps(es, indent=2)[:2000])

    if es.get("status") == "1" and es.get("result"):
        info = es["result"][0]
        print("\n Field check")
        print("keys present:", list(info.keys()))
        raw = info.get("creationBytecode", "")
        # Treat "0x"/empty as ABSENT, consistent with fetch_creation.
        real = raw.strip().lower().removeprefix("0x") not in ("", "0", "00")
        print(f"creationBytecode raw value: {raw[:40]!r}")
        print("has real bytecode? ->", real,
              "(note: '0x' means Etherscan has NONE)")
        print("contractFactory:", info.get("contractFactory", "(none)"))
        print("txHash:", info.get("txHash", "(none)"))
        if info.get("txHash"):
            tx = post_rpc("eth_getTransactionByHash", [info["txHash"]])
            to = tx.get("to")
            print("\n Deployment tx ")
            print("tx.to:", to,
                  "->", "DIRECT deploy (to=null)" if to is None
                  else "deployed via a contract (factory)")
            inp = tx.get("input", "")
            print("tx.input length (bytes):",
                  (len(inp) - 2)//2 if inp.startswith("0x") else 0)


#  badhex diag
def scan_for_badhex(p: Path):
    """Find non-hex content in a .hex file without modifying it.
    Returns a report dict or None if the file is clean."""
    raw = p.read_text()
    txt = raw.strip().lower()
    body = txt[2:] if txt.startswith("0x") else txt

    bad_positions = [i for i, c in enumerate(body) if c not in HEXSET]
    if not bad_positions:
        return None

    bad_chars = [body[i] for i in bad_positions]
    char_counts = {}
    for c in bad_chars:
        key = repr(c)
        char_counts[key] = char_counts.get(key, 0) + 1

    first = bad_positions[0]
    ctx = body[max(0, first - 30): first + 30]
    hex_frac = 1 - (len(bad_positions) / len(body)) if body else 0

    return {
        "file": str(p.relative_to(DATA_DIR)),
        "total_len": len(body),
        "bad_count": len(bad_positions),
        "bad_chars": char_counts,
        "first_bad_char_offset": first,
        "context_around_first": ctx,
        "hex_fraction": round(hex_frac, 4),
        "looks_like": ("ERROR_STRING / not bytecode" if hex_frac < 0.5
                       else "mostly hex with embedded junk "
                            "(likely UNLINKED_LIBRARY placeholder)"),
    }


def debug_badhex():
    """Scan every .hex file and report any non-hex content found."""
    files = list(ONCHAIN.glob("*.hex")) + list(COMPILED.glob("*/*/*.hex"))
    print(f"Scanning {len(files)} .hex files for non-hex content...\n")
    problems = [r for p in sorted(files) if (r := scan_for_badhex(p))]

    if not problems:
        print("No non-hex content found in any file.")
        return

    print(f"Found {len(problems)} file(s) with non-hex content:\n")
    for r in problems:
        print("=" * 70)
        print(f"FILE: {r['file']}")
        print(f"  length: {r['total_len']} hex chars  |  bad: {r['bad_count']}  "
              f"|  hex fraction: {r['hex_fraction']}")
        print(f"  offending characters: {r['bad_chars']}")
        print(f"  first bad char at offset {r['first_bad_char_offset']} "
              f"(byte {r['first_bad_char_offset']//2})")
        print(f"  context: ...{r['context_around_first']!r}...")
        print(f"  VERDICT: {r['looks_like']}")
    print("=" * 70)
    print("\nINTERPRETATION GUIDE:")
    print("  - 'mostly hex with embedded junk' = unlinked-library placeholder")
    print("    (__$...$__ or __Lib.sol:Name___). Handled by link_libraries_all.")
    print("  - 'ERROR_STRING / not bytecode' = fetch saved an error response")
    print("    into a .hex file. That contract must be refetched.")


# driver
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "creation":
        if len(sys.argv) != 3:
            sys.exit("usage: python debug_tools.py creation <address>")
        debug_creation(sys.argv[2])
    elif cmd == "badhex":
        debug_badhex()
    else:
        sys.exit(f"unknown subcommand: {cmd!r}; use 'creation' or 'badhex'")