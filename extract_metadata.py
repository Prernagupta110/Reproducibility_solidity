import json
import cbor2
from utils import CONTRACTS, DATA_DIR

in_dir = DATA_DIR / "onchain"


def split_metadata(bytecode_hex: str):
    
    b = bytes.fromhex(bytecode_hex)
    if len(b) < 4:
        return bytecode_hex, None, None, "none"

    cbor_len = int.from_bytes(b[-2:], "big")     # last 2 bytes = payload length
    # If the length is nonsense, this contract has no trailer (e.g. bytecodeHash
    # = "none", or a very old compiler).
    if cbor_len + 2 > len(b) or cbor_len == 0:
        return bytecode_hex, None, None, "none"

    cbor_payload = b[-(cbor_len + 2):-2]         # slice out just the CBOR bytes
    try:
        meta = cbor2.loads(cbor_payload)
    except Exception:
        return bytecode_hex, None, None, "unknown"

    if "ipfs" in meta:
        kind = "ipfs"
    elif "bzzr1" in meta:
        kind = "bzzr1"
    elif "bzzr0" in meta:
        kind = "bzzr0"
    else:
        kind = "unknown"

    stripped = b[:-(cbor_len + 2)]
    return stripped.hex(), meta, cbor_payload.hex(), kind


def decode_solc_version(meta):
    if not meta or "solc" not in meta:
        return None
    v = meta["solc"]
    if isinstance(v, (bytes, bytearray)) and len(v) == 3:
        return f"{v[0]}.{v[1]}.{v[2]}"
    return str(v)


def _normalize(v):
    #cbor2 returns bytes for hashes; convert to hex so JSON can serialize them
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    return v


for addr in CONTRACTS:
    for kind in ("runtime", "creation"):
        src = in_dir / f"{addr.lower()}.{kind}.hex"
        if not src.exists():
            continue

        code_hex = src.read_text().strip()
        try:
            stripped_hex, meta, cbor_hex, meta_kind = split_metadata(code_hex)

            (in_dir / f"{addr.lower()}.{kind}.stripped.hex").write_text(stripped_hex)

            # one bad contract doesn't crash the whole loop. 
            if isinstance(meta, dict):
                meta_clean = {k: _normalize(v) for k, v in meta.items()}
            else:
                meta_clean = {"_raw_decoded": _normalize(meta)} if meta is not None else {}

            meta_clean["_decoded_solc_version"] = (
                decode_solc_version(meta) if isinstance(meta, dict) else None)
            meta_clean["_cbor_raw_hex"] = cbor_hex
            meta_clean["_cbor_length_bytes"] = (len(code_hex) - len(stripped_hex)) // 2
            meta_clean["_has_metadata"] = meta is not None
            meta_clean["_metadata_kind"] = meta_kind

            (in_dir / f"{addr.lower()}.{kind}.meta.json").write_text(
                json.dumps(meta_clean, indent=2))
        except Exception as e:
            print(f"[meta] {addr} {kind}: SKIP (decode issue: {str(e)[:80]})")
            continue

        print(f"[meta] {addr} {kind}: kind={meta_kind} "
              f"solc={meta_clean.get('_decoded_solc_version')} "
              f"trailer={meta_clean['_cbor_length_bytes']}B")