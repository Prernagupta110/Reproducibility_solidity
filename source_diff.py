import hashlib
import difflib
import json
from pathlib import Path

DATA_DIR = Path("data")

ETHERSCAN_DIR = DATA_DIR / "etherscan"
SOURCIFY_DIR = DATA_DIR / "sourcify"

REPORT_DIR = DATA_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_text(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def load_solidity_sources(folder):

    files = []

    if not folder.exists():
        return ""

    for f in sorted(folder.rglob("*.sol")):
        try:
            files.append(
                f.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )
            )
        except Exception:
            pass

    return "\n".join(files)


def similarity(a, b):

    return round(
        difflib.SequenceMatcher(
            None,
            a,
            b
        ).ratio() * 100,
        2
    )


def compare_contract(address):

    address = address.lower()

    etherscan_folder = (
        ETHERSCAN_DIR /
        address
    )

    sourcify_folder = (
        SOURCIFY_DIR /
        address /
        "sources"
    )

    etherscan_source = load_solidity_sources(
        etherscan_folder
    )

    sourcify_source = load_solidity_sources(
        sourcify_folder
    )

    if not etherscan_source:
        return {
            "address": address,
            "status": "NO_ETHERSCAN_SOURCE"
        }

    if not sourcify_source:
        return {
            "address": address,
            "status": "NO_SOURCIFY_SOURCE"
        }

    sim = similarity(
        etherscan_source,
        sourcify_source
    )

    identical = (
        etherscan_source ==
        sourcify_source
    )

    diff_lines = list(
        difflib.unified_diff(
            etherscan_source.splitlines(),
            sourcify_source.splitlines(),
            fromfile="etherscan",
            tofile="sourcify",
            lineterm=""
        )
    )

    diff_file = (
        REPORT_DIR /
        f"{address}_source.diff"
    )

    diff_file.write_text(
        "\n".join(diff_lines),
        encoding="utf-8"
    )

    result = {

        "address": address,

        "identical": identical,

        "similarity_percent": sim,

        "etherscan_hash":
            sha256_text(
                etherscan_source
            ),

        "sourcify_hash":
            sha256_text(
                sourcify_source
            ),

        "diff_file":
            str(diff_file)
    }

    return result


def main():

    contracts_file = Path(
        "contracts.txt"
    )

    if not contracts_file.exists():
        print(
            "contracts.txt not found"
        )
        return

    contracts = [

        line.strip()

        for line in contracts_file.read_text().splitlines()

        if line.strip()
    ]

    results = []

    print(
        "\nSOURCE CODE COMPARISON\n"
    )

    for address in contracts:

        result = compare_contract(
            address
        )

        results.append(
            result
        )

        print(
            f"{address} "
            f"-> "
            f"{result.get('similarity_percent','N/A')}%"
        )

    report = (
        REPORT_DIR /
        "source_comparison.json"
    )

    report.write_text(
        json.dumps(
            results,
            indent=2
        )
    )

    print(
        f"\nSaved: {report}"
    )


if __name__ == "__main__":
    main()