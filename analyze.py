import sys
import csv
import json
from collections import Counter, defaultdict
from utils import DATA_DIR, CONTRACTS

REPORTS = DATA_DIR / "reports"
FIG = REPORTS / "figures"
CSV_PATH = REPORTS / "comparison.csv"
SOURCIFY_SUMMARY = DATA_DIR / "sourcify" / "_summary.json"
ONCHAIN = DATA_DIR / "onchain"

def load_rows():
    if not CSV_PATH.exists():
        sys.exit(f"No {CSV_PATH}. Run compare.py first.")
    with open(CSV_PATH) as f:
        return list(csv.DictReader(f))


def pct(n, d):
    return f"{(100.0 * n / d):.1f}%" if d else "-"


def table_md(title, counter, total):
    lines = [f"### {title}", "", "| Status | Count | Share |", "|---|---|---|"]
    for status, n in counter.most_common():
        lines.append(f"| {status} | {n} | {pct(n, total)} |")
    lines.append(f"| **Total** | **{total}** | **100%** |")
    lines.append("")
    return "\n".join(lines)

EXPLAINED_STATUSES = {
    "FULL_MATCH",                # bit-for-bit - no canonicalization needed
    "PARTIAL_MATCH",             # only the metadata trailer differs
    "IMMUTABLE_VAR_ONLY",        
    "EMBEDDED_METADATA_ONLY",    # embedded CBOR trailer (creation)
    "TRAILING_DATA_ONLY",        # constructor args
    "UNLINKED_LIBRARY",         
}
UNEXPLAINED_STATUSES = {
    "PARTIAL_KNOWN",             # some regions known, some NOT_YET_DISTINGUISHED
    "NOT_YET_DISTINGUISHED",
    "MIXED_KNOWN",               
}
EXCLUDED_FROM_DENOMINATOR = {
    "MISSING_DATA", "MISSING_ONCHAIN", "COMPARE_ERROR", "BADHEX_LOCAL",
}


def canonicalization_rate(rows):
    counted = [r for r in rows if r["status"] not in EXCLUDED_FROM_DENOMINATOR]
    full_n = sum(1 for r in counted if r["status"] == "FULL_MATCH")
    not_full = [r for r in counted if r["status"] != "FULL_MATCH"]
    explained = sum(1 for r in not_full if r["status"] in EXPLAINED_STATUSES)
    return explained, len(not_full), full_n


def run_tables():
    rows = load_rows()
    out = ["# Reproducibility analysis", "",
           f"Generated from `{CSV_PATH.name}`. "
           f"{len(rows)} (contract, kind, source) comparisons.", ""]

    for kind in ("runtime", "creation"):
        sub = [r for r in rows if r["kind"] == kind]
        out.append(table_md(f"RQ1 - {kind} bytecode: status distribution",
                            Counter(r["status"] for r in sub), len(sub)))

    runtime_es = [r for r in rows
                  if r["kind"] == "runtime" and r["source"] == "etherscan"]
    n = len(runtime_es)
    full = sum(1 for r in runtime_es if r["status"] == "FULL_MATCH")
    partial = sum(1 for r in runtime_es if r["status"] == "PARTIAL_MATCH")
    out += [
        "### RQ1 - headline (runtime, per contract)", "",
        f"- Bit-for-bit FULL match: **{full}/{n}** ({pct(full, n)})",
        f"- Code-identical (FULL or PARTIAL): **{full + partial}/{n}** "
        f"({pct(full + partial, n)})",
        f"- PARTIAL only (metadata trailer differs): **{partial}/{n}** "
        f"({pct(partial, n)})",
        "",
        "Interpretation: verified contracts are almost always functionally "
        "reproducible (identical executable code) but rarely bit-for-bit "
        "reproducible; the metadata trailer is the usual reason.", "",
    ]


    explained, denom, full_total = canonicalization_rate(rows)
    out += [
        "### RQ1", "",
        f"Of comparisons that are NOT already a FULL match "
        f"({denom} of {denom + full_total} analyzable), "
        f"**{explained}** are fully explained by documented causes "
        f"(metadata trailer, immutables, embedded metadata, constructor args, "
        f"unlinked libraries) = **{pct(explained, denom)}**.", "",
    ]

    # RQ2: Etherscan vs Sourcify agreement
    by_key = defaultdict(dict)
    for r in rows:
        by_key[(r["address"], r["kind"])][r["source"]] = r["status"]
    agree = disagree = 0
    disagreements = []
    for (addr, kind), d in by_key.items():
        if "etherscan" in d and "sourcify" in d:
            if d["etherscan"] == d["sourcify"]:
                agree += 1
            else:
                disagree += 1
                disagreements.append((addr, kind, d["etherscan"], d["sourcify"]))
    tot = agree + disagree
    out += ["### RQ2 - Etherscan vs Sourcify agreement", "",
            f"- Same status from both sources: **{agree}/{tot}** ({pct(agree, tot)})",
            f"- Different status: **{disagree}/{tot}** ({pct(disagree, tot)})", ""]
    if disagreements:
        out += ["| Address | Kind | Etherscan | Sourcify |", "|---|---|---|---|"]
        for a, k, e, s in disagreements:
            out.append(f"| {a} | {k} | {e} | {s} |")
        out.append("")

    # Taxonomy of real differences
    real_diff = [r for r in rows if r["status"] not in
                 ("FULL_MATCH", "PARTIAL_MATCH",
                  "MISSING_DATA", "MISSING_ONCHAIN")]
    out.append(table_md("Taxonomy - causes of real (post-metadata) differences",
                        Counter(r["status"] for r in real_diff), len(real_diff)))

    # Coverage
    missing = Counter(r["status"] for r in rows
                      if r["status"] in ("MISSING_DATA", "MISSING_ONCHAIN"))
    if missing:
        out.append(table_md("Coverage - missing data", missing, sum(missing.values())))

    text = "\n".join(out)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "analysis.md").write_text(text)
    print(text)
    print(f"\nSaved: {REPORTS / 'analysis.md'}")


# verifiers
def _bucket_own(status):
    if status == "FULL_MATCH": return "FULL"
    if status == "PARTIAL_MATCH": return "PARTIAL"
    if status in ("MISSING_ONCHAIN", "MISSING_DATA", "COMPARE_ERROR", "BADHEX_LOCAL", ""):
        return "NO_DATA"
    return "DIFF"


def run_verifiers():
    if not CSV_PATH.exists():
        sys.exit("Run compare.py first.")
    rows = list(csv.DictReader(open(CSV_PATH)))
    own = {(r["address"].lower(), r["kind"], r["source"]): r["status"] for r in rows}

    sourcify_label = {}
    if SOURCIFY_SUMMARY.exists():
        data = json.loads(SOURCIFY_SUMMARY.read_text())
        items = data if isinstance(data, list) else data.get("results", [])
        for row in items:
            a = (row.get("address") or "").lower()
            if a:
                sourcify_label[a] = row.get("match", row.get("status", ""))

    out_rows = []
    for addr in CONTRACTS:
        a = addr.lower()
        own_es = own.get((a, "runtime", "etherscan"), "")
        own_sf = own.get((a, "runtime", "sourcify"), "")

        b_es, b_sf = _bucket_own(own_es), _bucket_own(own_sf)
        buckets = [b for b in (b_es, b_sf) if b != "NO_DATA"]
        if len(buckets) < 2:
            agreement = ""
        elif len(set(buckets)) == 1:
            agreement = "AGREE"
        else:
         
            has_repro = any(b in ("FULL", "PARTIAL") for b in buckets)
            has_diff = "DIFF" in buckets
            agreement = "HARD_DISAGREE" if (has_repro and has_diff) else "SOFT_DISAGREE"

        cause = own_es if own_es not in ("FULL_MATCH", "PARTIAL_MATCH") else ""
        out_rows.append({"address": addr, "own_etherscan": own_es,
                         "own_sourcify": own_sf,
                         "sourcify_label": sourcify_label.get(a, ""),
                         "agreement": agreement, "our_cause_if_diff": cause})

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "verifier_comparison.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)

    decided = [r for r in out_rows if r["agreement"]]
    a_count = sum(1 for r in decided if r["agreement"] == "AGREE")
    soft = sum(1 for r in decided if r["agreement"] == "SOFT_DISAGREE")
    hard = sum(1 for r in decided if r["agreement"] == "HARD_DISAGREE")
    print("Etherscan-source vs Sourcify-source agreement (runtime):")
    print(f"  identical verdicts (AGREE):                {a_count}/{len(decided)}")
    print(f"  soft disagree (FULL vs PARTIAL only):      {soft}/{len(decided)}")
    print(f"    ^ both agree CODE is identical; differ only on metadata trailer")
    print(f"  HARD disagree (reproducible vs real diff): {hard}/{len(decided)}")
    print(f"    ^ the SUBSTANTIVE conflicts worth investigating")
    print(f"\nSaved: {out_path}")


# figures
def _bar(counter, title, fname, rotate=20):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if not counter:
        return
    labels = [k for k, _ in counter.most_common()]
    values = [v for _, v in counter.most_common()]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, values)
    ax.set_title(title); ax.set_ylabel("count")
    ax.tick_params(axis="x", rotation=rotate)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, str(v),
                ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    fig.savefig(FIG / fname, dpi=150); plt.close(fig)
    print(f"  wrote {fname}")


def run_figures():
    rows = load_rows()
    FIG.mkdir(parents=True, exist_ok=True)

    _bar(Counter(r["status"] for r in rows if r["kind"] == "runtime"),
         "Runtime bytecode: reproducibility status", "fig_runtime_status.png")
    _bar(Counter(r["status"] for r in rows if r["kind"] == "creation"),
         "Creation bytecode: reproducibility status", "fig_creation_status.png")
    _bar(Counter(r["status"] for r in rows if r["status"] not in
                 ("FULL_MATCH", "PARTIAL_MATCH", "MISSING_DATA", "MISSING_ONCHAIN")),
         "Causes of real (post-metadata) differences", "fig_taxonomy.png")

    mk = Counter()
    for f in ONCHAIN.glob("*.meta.json"):
        try:
            kind = json.loads(f.read_text()).get("_metadata_kind", "unknown")
        except Exception:
            kind = "unknown"
        mk[kind] += 1
    _bar(mk, "On-chain metadata trailer formats", "fig_metadata_kinds.png", rotate=0)
    print(f"\nFigures in: {FIG}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("all", "tables"):  run_tables()
    if cmd in ("all", "verifiers"): run_verifiers()
    if cmd in ("all", "figures"):
        try:
            run_figures()
        except ImportError:
            print("(matplotlib not installed; skipping figures. "
                  "Run: pip install matplotlib)")
    if cmd not in ("all", "tables", "verifiers", "figures"):
        sys.exit(f"unknown subcommand: {cmd!r}; use all/tables/verifiers/figures")