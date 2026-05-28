import sys
import csv
from utils import CONTRACTS, DATA_DIR

ONCHAIN = DATA_DIR / "onchain"
COMPILED = DATA_DIR / "compiled"
REPORTS = DATA_DIR / "reports"


WORTH_ANALYSING = {
    "IMMUTABLE_VAR_ONLY", "UNLINKED_LIBRARY_ONLY", "EMBEDDED_METADATA_ONLY",
    "TRAILING_DATA_ONLY", "MIXED_KNOWN", "PARTIAL_KNOWN", "NOT_YET_DISTINGUISHED",
}

# Minimal opcode-name table for readability.
_NAME = {
    0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV",
    0x10: "LT", 0x11: "GT", 0x14: "EQ", 0x15: "ISZERO", 0x16: "AND",
    0x17: "OR", 0x19: "NOT", 0x1b: "SHL", 0x1c: "SHR",
    0x33: "CALLER", 0x34: "CALLVALUE", 0x35: "CALLDATALOAD",
    0x36: "CALLDATASIZE", 0x39: "CODECOPY", 0x3d: "RETURNDATASIZE",
    0x50: "POP", 0x51: "MLOAD", 0x52: "MSTORE", 0x54: "SLOAD", 0x55: "SSTORE",
    0x56: "JUMP", 0x57: "JUMPI", 0x5b: "JUMPDEST",
    0x80: "DUP1", 0x90: "SWAP1", 0xa1: "LOG1",
    0xf0: "CREATE", 0xf3: "RETURN", 0xf5: "CREATE2", 0xfd: "REVERT", 0xfe: "INVALID",
    0x73: "PUSH20",
}


def read(p):
    if not p.exists():
        return None
    return p.read_text().strip().lower().removeprefix("0x") or None


def strip_metadata(hex_str):
    try:
        b = bytes.fromhex(hex_str)
    except ValueError:
        return hex_str
    if len(b) < 4:
        return hex_str
    n = int.from_bytes(b[-2:], "big")
    if n + 2 > len(b) or n == 0:
        return hex_str
    return b[:-(n + 2)].hex()


def disassemble(code: bytes):
    """Walk bytecode into (pc, opcode, name, operand_bytes). PUSH1..PUSH32
    consume 1..32 operand bytes; everything else is a single-byte op."""
    instrs, pc, n = [], 0, len(code)
    while pc < n:
        op = code[pc]
        if 0x60 <= op <= 0x7f:               # PUSH1..PUSH32
            size = op - 0x5f
            operand = code[pc + 1: pc + 1 + size]
            instrs.append((pc, op, f"PUSH{size}", operand))
            pc += 1 + size
        else:
            instrs.append((pc, op, _NAME.get(op, f"0x{op:02x}"), b""))
            pc += 1
    return instrs


def classify_byte(pc, instrs):
    #Return 'OPERAND' if pc falls inside a PUSH operand, else 'OPCODE'
    for (start, op, name, operand) in instrs:
        if name.startswith("PUSH"):
            opnd_start = start + 1
            opnd_end = opnd_start + len(operand)
            if opnd_start <= pc < opnd_end:
                return "OPERAND", name
            if pc == start:
                return "OPCODE", name
        else:
            if pc == start:
                return "OPCODE", name
    return "UNKNOWN", "?"


def analyse(addr, kind, src):
    #Return (operand_bytes, opcode_bytes, verdict) or None if files missing.
    onchain = read(ONCHAIN / f"{addr}.{kind}.hex")
    local = read(COMPILED / addr / src / f"{kind}.hex")
    if not onchain or not local:
        return None

    on = bytes.fromhex(strip_metadata(onchain))
    lo = bytes.fromhex(strip_metadata(local))
    on_disasm = disassemble(on)

    m = min(len(on), len(lo))
    diffs = [i for i in range(m) if on[i] != lo[i]]
    diffs += list(range(m, len(on)))

    operand = opcode = 0
    examples = []
    for pc in diffs:
        if pc >= len(on):
            continue
        what, name = classify_byte(pc, on_disasm)
        if what == "OPERAND":
            operand += 1
        elif what == "OPCODE":
            opcode += 1
            if len(examples) < 8:
                lo_name = classify_byte(pc, disassemble(lo))[1] if pc < len(lo) else "?"
                examples.append((pc, name, lo_name))

    total = operand + opcode
    if total == 0:
        verdict = "TRAILING_DATA_ONLY"
    elif opcode == 0:
        verdict = "EMBEDDED_CONSTANT_ONLY"
    else:
        verdict = "REAL_CODEGEN_DIFFERENCE"
    return operand, opcode, verdict, examples


#  single-contract
def run_one(addr, kind, src):
    res = analyse(addr.lower(), kind, src)
    if res is None:
        sys.exit("Missing bytecode files for that address/kind/source.")
    operand, opcode, verdict, examples = res
    total = operand + opcode
    print(f"{addr} [{kind}] source={src}")
    print(f"  differing body bytes: {total}")
    print(f"  fall inside PUSH operands : {operand}")
    print(f"  fall on opcodes :  {opcode}\n")
    if verdict == "EMBEDDED_CONSTANT_ONLY":
        print("  VERDICT: EMBEDDED_CONSTANT_ONLY")
        print("    Every differing byte is a PUSH operand. The instructions are")
        print("    identical")
    elif verdict == "REAL_CODEGEN_DIFFERENCE":
        print("  VERDICT: REAL_CODEGEN_DIFFERENCE")
        print("    Some differing bytes are opcodes -> genuine non-reproducibility.")
        print("    First differing opcodes (pc: on-chain vs local):")
        for pc, on_name, lo_name in examples:
            print(f"      pc {pc}: {on_name}  vs  {lo_name}")
    else:
        print(f"  VERDICT: {verdict}")


# whole dataset
def run_all():
    REPORTS.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS / "comparison.csv"
    if not csv_path.exists():
        sys.exit("Run compare.py first to produce comparison.csv")

    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            if r["status"] not in WORTH_ANALYSING:
                continue
            res = analyse(r["address"].lower(), r["kind"], r["source"])
            if res is None:
                continue
            operand, opcode, verdict, _ = res
            rows.append({
                "address": r["address"], "kind": r["kind"], "source": r["source"],
                "compare_status": r["status"],
                "operand_diff_bytes": operand, "opcode_diff_bytes": opcode,
                "opcode_verdict": verdict,
            })

    if not rows:
        print("Nothing to analyse ")
        return

    out_path = REPORTS / "opcode_diagnosis.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print(f"{'address':<44}{'kind':<10}{'src':<10}{'compare':<22}{'opcode_verdict'}")
    print("-" * 110)
    for r in rows:
        print(f"{r['address']:<44}{r['kind']:<10}{r['source']:<10}"
              f"{r['compare_status']:<22}{r['opcode_verdict']}")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) == 4:
        run_one(sys.argv[1], sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 1:
        run_all()
    else:
        print(__doc__); sys.exit(1)