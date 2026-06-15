import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path("data")
REPORT_DIR = DATA_DIR / "reports"

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

ETHERSCAN_DIR = DATA_DIR / "etherscan"


def classify_contract(contract_name):

    name = contract_name.lower()

    if "erc20" in name:
        return "ERC20"

    if "erc721" in name:
        return "ERC721"

    if "erc1155" in name:
        return "ERC1155"

    if "proxy" in name:
        return "PROXY"

    if "vault" in name:
        return "DEFI"

    if "pool" in name:
        return "DEFI"

    if "swap" in name:
        return "DEFI"

    if "router" in name:
        return "DEFI"

    if "staking" in name:
        return "DEFI"

    return "OTHER"


def count_source_files(contract_dir):

    source_dir = contract_dir / "sources"

    if not source_dir.exists():
        return 0

    return len(
        list(
            source_dir.rglob("*.sol")
        )
    )


def detect_contract_type(contract_dir):

    settings_file = contract_dir / "settings.json"

    if not settings_file.exists():
        return {
            "category": "UNKNOWN",
            "source_count": 0
        }

    settings = json.loads(
        settings_file.read_text()
    )

    contract_name = settings.get(
        "contract_name",
        "UNKNOWN"
    )

    category = classify_contract(
        contract_name
    )

    source_count = count_source_files(
        contract_dir
    )

    libraries = settings.get(
        "libraries",
        {}
    )

    return {
        "category": category,
        "source_count": source_count,
        "libraries": bool(libraries),
        "compiler_version":
            settings.get(
                "compiler_version",
                "UNKNOWN"
            )
    }


def generate_distribution():

    distribution = Counter()

    multi_file = 0
    library_based = 0

    compiler_versions = Counter()

    rows = []

    for contract_dir in ETHERSCAN_DIR.iterdir():

        if not contract_dir.is_dir():
            continue

        info = detect_contract_type(
            contract_dir
        )

        distribution[
            info["category"]
        ] += 1

        compiler_versions[
            info["compiler_version"]
        ] += 1

        if info["source_count"] > 1:
            multi_file += 1

        if info["libraries"]:
            library_based += 1

        rows.append({

            "address":
                contract_dir.name,

            "category":
                info["category"],

            "compiler_version":
                info["compiler_version"],

            "source_files":
                info["source_count"],

            "libraries":
                info["libraries"]
        })

    report = {

        "total_contracts":
            len(rows),

        "category_distribution":
            dict(distribution),

        "multi_file_contracts":
            multi_file,

        "library_based_contracts":
            library_based,

        "compiler_distribution":
            dict(compiler_versions)
    }

    output_file = (
        REPORT_DIR /
        "dataset_distribution.json"
    )

    output_file.write_text(
        json.dumps(
            report,
            indent=2
        )
    )

    print(
        "\nDATASET DISTRIBUTION\n"
    )

    print(
        json.dumps(
            report,
            indent=2
        )
    )

    print(
        f"\nSaved -> {output_file}"
    )


if __name__ == "__main__":
    generate_distribution()