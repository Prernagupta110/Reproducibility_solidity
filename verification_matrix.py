import csv
from pathlib import Path

REPORT_DIR = Path("data/reports")

COMPARISON_FILE = (
    REPORT_DIR /
    "comparison.csv"
)

OUTPUT_FILE = (
    REPORT_DIR /
    "verification_matrix.csv"
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


def build_matrix(rows):

    matrix = {}

    for row in rows:

        address = row["address"]

        source = row["source"]

        status = row["status"]

        kind = row.get(
            "kind",
            "runtime"
        )

        key = (
            address,
            kind
        )

        if key not in matrix:

            matrix[key] = {

                "address":
                    address,

                "kind":
                    kind,

                "etherscan":
                    "",

                "sourcify":
                    "",

                "local":
                    ""
            }

        source_lower = (
            source.lower()
        )

        if "etherscan" in source_lower:

            matrix[key][
                "etherscan"
            ] = status

        elif "sourcify" in source_lower:

            matrix[key][
                "sourcify"
            ] = status

        elif "local" in source_lower:

            matrix[key][
                "local"
            ] = status

    return matrix


def determine_consistency(row):

    values = [

        row["etherscan"],

        row["sourcify"],

        row["local"]
    ]

    values = [
        v
        for v in values
        if v
    ]

    if not values:

        return "NO_DATA"

    if len(set(values)) == 1:

        return "CONSISTENT"

    return "INCONSISTENT"


def save_matrix(matrix):

    fieldnames = [

        "address",

        "kind",

        "etherscan",

        "sourcify",

        "local",

        "consistency"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in matrix.values():

            row[
                "consistency"
            ] = determine_consistency(
                row
            )

            writer.writerow(row)

    print(
        f"\nSaved -> {OUTPUT_FILE}"
    )


def print_summary(matrix):

    total = len(matrix)

    consistent = 0

    inconsistent = 0

    for row in matrix.values():

        result = determine_consistency(
            row
        )

        if result == "CONSISTENT":

            consistent += 1

        elif result == "INCONSISTENT":

            inconsistent += 1

    print("\nVERIFICATION SUMMARY\n")

    print(
        f"Total Contracts: {total}"
    )

    print(
        f"Consistent: {consistent}"
    )

    print(
        f"Inconsistent: {inconsistent}"
    )


def main():

    rows = load_comparison()

    matrix = build_matrix(
        rows
    )

    save_matrix(
        matrix
    )

    print_summary(
        matrix
    )


if __name__ == "__main__":
    main()