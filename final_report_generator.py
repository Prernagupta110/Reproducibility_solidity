import csv
import json
from pathlib import Path
from collections import Counter

REPORT_DIR = Path("data/reports")

COMPARISON_FILE = REPORT_DIR / "comparison.csv"
ROOT_CAUSE_FILE = REPORT_DIR / "root_cause_analysis.csv"
VERIFICATION_FILE = REPORT_DIR / "verification_matrix.csv"
DATASET_FILE = REPORT_DIR / "dataset_distribution.json"
CPIMP_FILE = REPORT_DIR / "cpimp_summary.json"

FINAL_JSON = REPORT_DIR / "final_report.json"
FINAL_TEXT = REPORT_DIR / "final_report.txt"


SUCCESS_STATUSES = {

    "FULL_MATCH",

    "PARTIAL_MATCH",

    "IMMUTABLE_VAR_ONLY",

    "UNLINKED_LIBRARY_ONLY",

    "EMBEDDED_METADATA_ONLY",

    "TRAILING_DATA_ONLY"
}


def load_csv(path):

    if not path.exists():
        return []

    with open(
        path,
        newline="",
        encoding="utf-8"
    ) as f:

        return list(csv.DictReader(f))


def load_json(path):

    if not path.exists():
        return {}

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return {}


def calculate_reproducibility_rate(rows):

    total = len(rows)

    if total == 0:
        return 0

    reproducible = 0

    for row in rows:

        status = row.get(
            "status",
            ""
        )

        if status in SUCCESS_STATUSES:

            reproducible += 1

    return round(
        reproducible / total * 100,
        2
    )


def build_status_statistics(rows):

    counter = Counter()

    for row in rows:

        counter[
            row.get(
                "status",
                "UNKNOWN"
            )
        ] += 1

    total = sum(counter.values())

    result = []

    for status, count in sorted(
        counter.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        percentage = round(
            count / total * 100,
            2
        ) if total else 0

        result.append({

            "status":
                status,

            "count":
                count,

            "percentage":
                percentage
        })

    return result


def build_root_cause_statistics(rows):

    counter = Counter()

    for row in rows:

        counter[
            row.get(
                "root_cause",
                "UNKNOWN"
            )
        ] += 1

    total = sum(counter.values())

    result = []

    for cause, count in sorted(
        counter.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        percentage = round(
            count / total * 100,
            2
        ) if total else 0

        result.append({

            "cause":
                cause,

            "count":
                count,

            "percentage":
                percentage
        })

    return result


def build_verification_statistics(rows):

    counter = Counter()

    for row in rows:

        counter[
            row.get(
                "consistency",
                "UNKNOWN"
            )
        ] += 1

    total = sum(counter.values())

    result = []

    for status, count in sorted(
        counter.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        percentage = round(
            count / total * 100,
            2
        ) if total else 0

        result.append({

            "consistency":
                status,

            "count":
                count,

            "percentage":
                percentage
        })

    return result


def build_thesis_summary(rows):

    status_counter = Counter()

    for row in rows:

        status_counter[
            row.get(
                "status",
                "UNKNOWN"
            )
        ] += 1

    return {

        "FULL_MATCH":
            status_counter[
                "FULL_MATCH"
            ],

        "PARTIAL_MATCH":
            status_counter[
                "PARTIAL_MATCH"
            ],

        "IMMUTABLE_VAR_ONLY":
            status_counter[
                "IMMUTABLE_VAR_ONLY"
            ],

        "UNLINKED_LIBRARY_ONLY":
            status_counter[
                "UNLINKED_LIBRARY_ONLY"
            ],

        "EMBEDDED_METADATA_ONLY":
            status_counter[
                "EMBEDDED_METADATA_ONLY"
            ],

        "TRAILING_DATA_ONLY":
            status_counter[
                "TRAILING_DATA_ONLY"
            ],

        "PARTIAL_KNOWN":
            status_counter[
                "PARTIAL_KNOWN"
            ],

        "MIXED_KNOWN":
            status_counter[
                "MIXED_KNOWN"
            ],

        "NOT_YET_DISTINGUISHED":
            status_counter[
                "NOT_YET_DISTINGUISHED"
            ],

        "MISSING_DATA":
            status_counter[
                "MISSING_DATA"
            ],

        "MISSING_ONCHAIN":
            status_counter[
                "MISSING_ONCHAIN"
            ]
    }


def build_report():

    comparison = load_csv(
        COMPARISON_FILE
    )

    root_causes = load_csv(
        ROOT_CAUSE_FILE
    )

    verification = load_csv(
        VERIFICATION_FILE
    )

    dataset = load_json(
        DATASET_FILE
    )

    cpimp = load_json(
        CPIMP_FILE
    )

    report = {

        "total_contracts":
            len(comparison),

        "reproducibility_rate":
            calculate_reproducibility_rate(
                comparison
            ),

        "thesis_summary":
            build_thesis_summary(
                comparison
            ),

        "status_statistics":
            build_status_statistics(
                comparison
            ),

        "root_cause_statistics":
            build_root_cause_statistics(
                root_causes
            ),

        "verification_statistics":
            build_verification_statistics(
                verification
            ),

        "dataset_distribution":
            dataset,

        "cpimp_summary":
            cpimp
    }

    return report


def save_json(report):

    FINAL_JSON.write_text(

        json.dumps(
            report,
            indent=2
        )
    )


def save_text(report):

    lines = []

    lines.append(
        "=" * 70
    )

    lines.append(
        "SOLIDITY REPRODUCIBILITY ANALYSIS REPORT"
    )

    lines.append(
        "=" * 70
    )

    lines.append("")

    lines.append(
        f"Total Contracts Analysed: {report['total_contracts']}"
    )

    lines.append(
        f"Reproducibility Rate: {report['reproducibility_rate']}%"
    )

    lines.append("")

    lines.append(
        "THESIS SUMMARY"
    )

    lines.append(
        "-" * 70
    )

    for k, v in report[
        "thesis_summary"
    ].items():

        lines.append(
            f"{k}: {v}"
        )

    lines.append("")
    lines.append(
        "STATUS DISTRIBUTION"
    )

    lines.append(
        "-" * 70
    )

    for row in report[
        "status_statistics"
    ]:

        lines.append(

            f"{row['status']} : "

            f"{row['count']} "

            f"({row['percentage']}%)"
        )

    lines.append("")
    lines.append(
        "ROOT CAUSE ANALYSIS"
    )

    lines.append(
        "-" * 70
    )

    for row in report[
        "root_cause_statistics"
    ]:

        lines.append(

            f"{row['cause']} : "

            f"{row['count']} "

            f"({row['percentage']}%)"
        )

    lines.append("")
    lines.append(
        "VERIFICATION CONSISTENCY"
    )

    lines.append(
        "-" * 70
    )

    for row in report[
        "verification_statistics"
    ]:

        lines.append(

            f"{row['consistency']} : "

            f"{row['count']} "

            f"({row['percentage']}%)"
        )

    lines.append("")
    lines.append(
        "INTERPRETATION"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        "FULL_MATCH = Exact bytecode reproducibility."
    )

    lines.append(
        "PARTIAL_MATCH = Logic identical but metadata differs."
    )

    lines.append(
        "EMBEDDED_METADATA_ONLY = Metadata-only difference."
    )

    lines.append(
        "TRAILING_DATA_ONLY = Constructor argument difference."
    )

    lines.append(
        "UNLINKED_LIBRARY_ONLY = Library linking issue."
    )

    lines.append(
        "IMMUTABLE_VAR_ONLY = Immutable value difference."
    )

    lines.append(
        "PARTIAL_KNOWN = Partially explained mismatch."
    )

    lines.append(
        "MIXED_KNOWN = Multiple identified causes."
    )

    lines.append(
        "NOT_YET_DISTINGUISHED = Cause not identified."
    )

    lines.append(
        "MISSING_DATA = Missing verification data."
    )

    lines.append(
        "MISSING_ONCHAIN = Runtime bytecode unavailable."
    )

    FINAL_TEXT.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


def main():

    report = build_report()

    save_json(
        report
    )

    save_text(
        report
    )

    print()

    print(
        "FINAL REPORT GENERATED"
    )

    print()

    print(
        f"Contracts Analysed : "
        f"{report['total_contracts']}"
    )

    print(
        f"Reproducibility Rate : "
        f"{report['reproducibility_rate']}%"
    )

    print()

    print(
        f"Saved: {FINAL_JSON}"
    )

    print(
        f"Saved: {FINAL_TEXT}"
    )


if __name__ == "__main__":
    main()