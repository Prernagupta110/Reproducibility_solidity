import csv
import json
from pathlib import Path

REPORT_DIR = Path("data/reports")
REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

COMPARISON_FILE = (
    REPORT_DIR /
    "comparison.csv"
)

CPIMP_CONTRACTS = [

    "0x7093c3e904720e1fd031fd48aeb424bd2c5c6bfc",
    "0x2b684e8905a850a91f5eea913a19dae3926a6703",
    "0xc70be5b7c19529ef642d16c10dfe91c58b5c3bf0",
    "0xa4adf19196bc401a31e6e22e203c4a2fa0d1886a",
    "0xe428a6abd34f859325ee56d4596ab4c0c421bb34",

    "0x418C24191aE947A78C99fDc0e45a1f96Afb254BE",
    "0xc1ABb8c93be6811aFfC70675b0432926c4BFBb5D",
    "0xA7AeFeaD2F25972D80516628417ac46b3F2604Af",
    "0x2a4e3a514a0b8d6096f208de0cd645547fb73bea",
    "0xc40d57992f5b657a480b8ed6256128019d8b2139"

]


def load_comparison():

    if not COMPARISON_FILE.exists():

        raise FileNotFoundError(
            f"{COMPARISON_FILE} not found. "
            f"Run compare.py first."
        )

    with open(
        COMPARISON_FILE,
        newline="",
        encoding="utf-8"
    ) as f:

        return list(
            csv.DictReader(f)
        )


def collect_cpimp_rows():

    rows = load_comparison()

    selected = []

    targets = {
        x.lower()
        for x in CPIMP_CONTRACTS
    }

    for row in rows:

        address = row.get(
            "address",
            ""
        ).lower()

        if address in targets:

            selected.append(row)

    return selected


def summarize(rows):

    summary = {

        "contracts": 0,
        "full_match": 0,
        "partial_match": 0,
        "immutable_var_only": 0,
        "trailing_data_only": 0,
        "unlinked_library": 0,
        "missing_data": 0,
        "other": 0

    }

    unique_contracts = set()

    for row in rows:

        unique_contracts.add(
            row["address"]
        )

        status = row.get(
            "status",
            ""
        )

        if status == "FULL_MATCH":

            summary[
                "full_match"
            ] += 1

        elif status == "PARTIAL_MATCH":

            summary[
                "partial_match"
            ] += 1

        elif status == "IMMUTABLE_VAR_ONLY":

            summary[
                "immutable_var_only"
            ] += 1

        elif status == "TRAILING_DATA_ONLY":

            summary[
                "trailing_data_only"
            ] += 1

        elif status == "UNLINKED_LIBRARY":

            summary[
                "unlinked_library"
            ] += 1

        elif "MISSING" in status:

            summary[
                "missing_data"
            ] += 1

        else:

            summary[
                "other"
            ] += 1

    summary[
        "contracts"
    ] = len(
        unique_contracts
    )

    return summary


def save_results(
    rows,
    summary
):

    csv_file = (
        REPORT_DIR /
        "cpimp_results.csv"
    )

    if rows:

        with open(
            csv_file,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=rows[0].keys()
            )

            writer.writeheader()

            writer.writerows(
                rows
            )

    json_file = (
        REPORT_DIR /
        "cpimp_summary.json"
    )

    with open(
        json_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=4
        )

    print(
        f"\nSaved -> {csv_file}"
    )

    print(
        f"Saved -> {json_file}"
    )


def print_summary(
    summary
):

    print(
        "\n=============================="
    )

    print(
        " CPIMP CASE STUDY RESULTS"
    )

    print(
        "=============================="
    )

    print(
        f"Contracts analysed: "
        f"{summary['contracts']}"
    )

    print(
        f"FULL_MATCH: "
        f"{summary['full_match']}"
    )

    print(
        f"PARTIAL_MATCH: "
        f"{summary['partial_match']}"
    )

    print(
        f"IMMUTABLE_VAR_ONLY: "
        f"{summary['immutable_var_only']}"
    )

    print(
        f"TRAILING_DATA_ONLY: "
        f"{summary['trailing_data_only']}"
    )

    print(
        f"UNLINKED_LIBRARY: "
        f"{summary['unlinked_library']}"
    )

    print(
        f"MISSING_DATA: "
        f"{summary['missing_data']}"
    )

    print(
        f"OTHER: "
        f"{summary['other']}"
    )

    print(
        "\nCase study completed.\n"
    )


def main():

    rows = collect_cpimp_rows()

    summary = summarize(
        rows
    )

    save_results(
        rows,
        summary
    )

    print_summary(
        summary
    )


if __name__ == "__main__":
    main()