import csv
import json
from pathlib import Path
from collections import Counter

REPORT_DIR = Path("data/reports")

COMPARISON_FILE = (
    REPORT_DIR /
    "comparison.csv"
)

OUTPUT_FILE = (
    REPORT_DIR /
    "root_cause_analysis.csv"
)

SUMMARY_FILE = (
    REPORT_DIR /
    "root_cause_summary.json"
)


ROOT_CAUSES = {

    "FULL_MATCH":
        "NONE",

    "PARTIAL_MATCH":
        "METADATA_DIFFERENCE",

    "EMBEDDED_METADATA_ONLY":
        "METADATA_DIFFERENCE",

    "TRAILING_DATA_ONLY":
        "CONSTRUCTOR_ARGUMENTS",

    "UNLINKED_LIBRARY_ONLY":
        "LIBRARY_LINKING",

    "IMMUTABLE_VAR_ONLY":
        "IMMUTABLE_VARIABLE",

    "PARTIAL_KNOWN":
        "PARTIALLY_EXPLAINED",

    "MIXED_KNOWN":
        "MULTIPLE_CAUSES",

    "NOT_YET_DISTINGUISHED":
        "UNKNOWN",

    "MISSING_DATA":
        "API_FETCH_ERROR",

    "MISSING_ONCHAIN":
        "RPC_FETCH_ERROR",

    "MISMATCH":
        "BYTECODE_MISMATCH"
}


def determine_cause(status):

    return ROOT_CAUSES.get(
        status,
        "UNKNOWN"
    )


def load_comparison():

    if not COMPARISON_FILE.exists():

        raise FileNotFoundError(
            f"{COMPARISON_FILE} not found"
        )

    with open(
        COMPARISON_FILE,
        newline="",
        encoding="utf-8"
    ) as f:

        return list(
            csv.DictReader(f)
        )


def analyse(rows):

    results = []

    summary = Counter()

    for row in rows:

        status = row.get(
            "status",
            ""
        )

        cause = determine_cause(
            status
        )

        summary[cause] += 1

        results.append({

            "address":
                row.get(
                    "address",
                    ""
                ),

            "kind":
                row.get(
                    "kind",
                    ""
                ),

            "source":
                row.get(
                    "source",
                    ""
                ),

            "status":
                status,

            "root_cause":
                cause
        })

    return results, summary


def save_results(results):

    if not results:
        return

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=results[0].keys()
        )

        writer.writeheader()

        writer.writerows(results)

    print(
        f"Saved -> {OUTPUT_FILE}"
    )


def save_summary(summary):

    total = sum(
        summary.values()
    )

    report = {

        "total_records":
            total,

        "root_causes":
            dict(summary)
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            report,
            indent=2
        )
    )

    print(
        f"Saved -> {SUMMARY_FILE}"
    )


def print_summary(summary):

    print(
        "\nROOT CAUSE SUMMARY\n"
    )

    for cause, count in sorted(
        summary.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"{cause:<30} {count}"
        )


def main():

    rows = load_comparison()

    results, summary = analyse(
        rows
    )

    save_results(
        results
    )

    save_summary(
        summary
    )

    print_summary(
        summary
    )

    print(
        "\nAnalysis Complete\n"
    )


if __name__ == "__main__":
    main()