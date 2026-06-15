from utils import CONTRACTS, DATA_DIR, BLOCK_FILE, post_rpc, log_failure, require_secrets

out_dir = DATA_DIR / "onchain"
out_dir.mkdir(parents=True, exist_ok=True)


def get_pinned_block() -> str:
    """
    Return the pinned block as a hex string. On the first ever run, pin the
    current latest block and remember it in BLOCK_FILE.
    """
    if BLOCK_FILE.exists():
        block_num = int(BLOCK_FILE.read_text().strip())
        print(f"[ok] Using pinned block: {block_num}")
        return hex(block_num)
    latest_hex = post_rpc("eth_blockNumber", [])   # returns e.g. "0x17f2c4f"
    latest_num = int(latest_hex, 16)               # hex string to int
    BLOCK_FILE.write_text(str(latest_num))
    print(f"[ok] Pinned block: {latest_num} (saved to {BLOCK_FILE.name})")
    return latest_hex


if __name__ == "__main__":
    require_secrets()
    block_tag = get_pinned_block()

    for addr in CONTRACTS:
        try:
            code_hex = post_rpc("eth_getCode", [addr, block_tag])
            clean = code_hex.removeprefix("0x")

            # an empty result ("0x") means there is NO contract here -- it's an EOA (a normal wallet).
            if not clean:
                print(f"[runtime] {addr}: EOA / no code at this block (skipped)")
                log_failure("fetch_runtime", addr, "EOA -- no code at address")
                continue

            out_file = out_dir / f"{addr.lower()}.runtime.hex"
            out_file.write_text(clean)
            print(f"[runtime] {addr}: {len(clean)//2} bytes -> {out_file.name}")
        except Exception as e:
            # one failure does not abort the batch.
            print(f"[runtime] {addr}: FAILED - {e}")
            log_failure("fetch_runtime", addr, e)