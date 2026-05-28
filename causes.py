"""
    1. EMBEDDED_METADATA -- a CBOR metadata trailer sitting INSIDE creation
       bytecode (because creation = [init][runtime+trailer][ctor args], the
       trailer is in the middle, not the end). The on-chain side shows bytes
       that decode as a trailer; the local side is empty there.
       Signature (from the Solidity metadata spec):
         IPFS  trailer begins a2 64 69 70 66 73   (CBOR: {"ipfs": ...})
         bzzr1 trailer begins a2 65 62 7a 7a 72 31 ({"bzzr1": ...})
         bzzr0 trailer begins a1 65 62 7a 7a 72 30 ({"bzzr0": ...})
       (IPFS: 0xa2 0x64 'i''p''f''s' ...; Swarm0: 0xa1 0x65 'b''z''z''r''0' ...)

    2. TRAILING_DATA_ONCHAIN -- the on-chain side has a run of bytes that the
       local side simply does not have (local is empty for that region), and it
       is NOT a metadata trailer. On creation bytecode this is the ABI-encoded
       constructor arguments (often zero-padded addresses, e.g.
       0000..00<20-byte address>). This is deploy-time data, not a codegen
       difference. 

  These two are now first-class detectors below. Anything still unmatched stays
  NOT_YET_DISTINGUISHED, which is the honest state.
"""


def detect_immutable(region) -> bool:
    """
    IMMUTABLE VARIABLE signature.
    Solidity writes `immutable` values into the runtime bytecode at construction
    time, so the on-chain copy holds the real value where local recompilation
    holds a zero placeholder. Same length, EXACTLY ONE side all zeros.
    Source: Solidity docs, "Constant and Immutable State Variables".
    """
    a, b = region["onchain"], region["local"]
    if len(a) != len(b):
        return False
    a_zero = set(a) <= {"0"}
    b_zero = set(b) <= {"0"}
    return a_zero != b_zero


def detect_unlinked_library(region) -> bool:
    """
    UNLINKED EXTERNAL LIBRARY placeholder: '__$<34hex>$__' i.e. 5f5f24 / 245f5f.
    Source: Solidity docs, "Using the Compiler > Library Linking".
    """
    local = region["local"]
    return "5f5f24" in local or "245f5f" in local


_MAP_HEADERS = ("a1", "a2", "a3")
_KEY_MARKERS = (
    "6469706673",     # 'd' + "ipfs"  (0x64 = text string length 4)
    "65627a7a7230",   # 'e' + "bzzr0" (0x65 = text string length 5)
    "65627a7a7231",   # 'e' + "bzzr1"
)


def _looks_like_trailer(hex_str: str) -> bool:
    h = hex_str.lower()
    for hdr in _MAP_HEADERS:
        if h.startswith(hdr):
            rest = h[len(hdr):]
            if any(rest.startswith(k) for k in _KEY_MARKERS):
                return True
    return False


def detect_embedded_metadata(region) -> bool:
  
    if region["local"] != "":     
        return False
    return _looks_like_trailer(region["onchain"])


def detect_trailing_data(region) -> bool:

    a = region["onchain"].lower()
    b = region["local"]
    if b != "" or a == "":
        return False
    if _looks_like_trailer(a):
        return False        # that's EMBEDDED_METADATA, not ctor args
    return True

KNOWN_CAUSES = [
    ("IMMUTABLE_VAR", detect_immutable,
     "Solidity docs: Constant and Immutable State Variables"),
    ("UNLINKED_LIBRARY", detect_unlinked_library,
     "Solidity docs: Using the Compiler > Library Linking"),
    ("EMBEDDED_METADATA", detect_embedded_metadata,
     "Solidity docs: Encoding of the Metadata Hash in the Bytecode"),
    ("TRAILING_DATA", detect_trailing_data,
     "Solidity ABI spec: constructor arguments appended to creation bytecode"),
]


def classify_regions(regions):
    """
    Given a contract's diff regions, return (verdict, per_region_labels, detail).

    verdict (derived from THIS contract's regions):
      "<CAUSE>_ONLY"          every region is the same single known cause
      "MIXED_KNOWN"           >1 known cause, all explained
      "PARTIAL_KNOWN"         some regions known, some NOT_YET_DISTINGUISHED
      "NOT_YET_DISTINGUISHED" no region matches any known cause
    """
    per_region = []
    matched = set()
    unknown = 0

    for r in regions:
        labels = [name for name, fn, _ in KNOWN_CAUSES if fn(r)]
        if labels:
            matched.update(labels)
            per_region.append(labels)
        else:
            unknown += 1
            per_region.append(["NOT_YET_DISTINGUISHED"])

    if not matched and unknown:
        verdict = "NOT_YET_DISTINGUISHED"
    elif matched and unknown:
        verdict = "PARTIAL_KNOWN"
    elif len(matched) == 1:
        verdict = f"{next(iter(matched))}_ONLY"
    else:
        verdict = "MIXED_KNOWN"

    return verdict, per_region, {"known": sorted(matched), "unknown_regions": unknown}