# Solidity Smart Contract Reproducibility Framework

## Overview

This project implements an automated framework for evaluating the reproducibility of Ethereum smart contracts. The framework collects verification artifacts, reconstructs compilation environments, recompiles contracts locally, compares generated artifacts against deployed blockchain artifacts, performs verification consistency analysis, identifies root causes of reproduction failures, and generates comprehensive reports.

## Project Structure

```text
SolidityThesis/
│
├── contracts.txt
├── .env
│
├── analyze.py
├── causes.py
├── compare.py
├── cpimp_case_study.py
├── dataset_distribution.py
├── fetch_creation.py
├── fetch_etherscan.py
├── fetch_runtime.py
├── fetch_sourcify.py
├── final_report_generator.py
├── recompile.py
├── recompile_sourcify.py
├── root_cause_analysis.py
├── solidity_reproducibility_pipeline.py
├── source_diff.py
├── utils.py
├── verification_matrix.py
│
└── data/
    ├── compiled/
    ├── etherscan/
    ├── onchain/
    └── reports/
```

## Requirements

- Python 3.10 or higher
- Etherscan API Key
- Ethereum RPC Endpoint

Install required packages:

```bash
pip install requests pandas matplotlib python-dotenv tqdm web3 py-solc-x
```

## Environment Configuration

Create a `.env` file in the project root:

```text
ETHERSCAN_API_KEY=YOUR_ETHERSCAN_API_KEY
RPC_URL=YOUR_ETHEREUM_RPC_URL
```

## Dataset Preparation

Store all verified smart contract addresses in:

```text
contracts.txt
```

Example:

```text
0x418C24191aE947A78C99fDc0e45a1f96Afb254BE
0xc1ABb8c93be6811aFfC70675b0432926c4BFBb5D
```

One contract address must be provided per line.

## Execution Workflow

### Step 1: Fetch Verification Artifacts

```bash
python fetch_etherscan.py
python fetch_sourcify.py
```

### Step 2: Fetch Blockchain Artifacts

```bash
python fetch_runtime.py
python fetch_creation.py
```

### Step 3: Recompile Contracts

```bash
python recompile.py
python recompile_sourcify.py
```

### Step 4: Compare Generated and Deployed Bytecode

```bash
python compare.py
```

### Step 5: Analyze Source Differences

```bash
python source_diff.py
```

### Step 6: Perform Root Cause Analysis

```bash
python root_cause_analysis.py
```

### Step 7: Verification Consistency Analysis

```bash
python verification_matrix.py
```

### Step 8: Generate Dataset Statistics

```bash
python dataset_distribution.py
```

### Step 9: Execute CPIMP Case Study

```bash
python cpimp_case_study.py
```

### Step 10: Generate Final Reports

```bash
python final_report_generator.py
```

## Alternative Execution

Run the complete framework:

```bash
python solidity_reproducibility_pipeline.py
```

## Output Files

Generated outputs are stored in:

```text
data/reports/
```

Outputs include:

- Reproducibility statistics
- Verification consistency metrics
- Root-cause analysis reports
- Dataset summaries
- CPIMP case study results

## Reproducibility Classifications

- FULL_MATCH
- PARTIAL_MATCH
- IMMUTABLE_VAR_ONLY
- TRAILING_DATA_ONLY
- UNLINKED_LIBRARY
- MISSING_DATA

## Expanding the Dataset

To analyze additional contracts:

1. Collect verified Ethereum contract addresses.
2. Add the addresses to `contracts.txt`.
3. Execute the framework workflow.
4. Generated reports will automatically include the new contracts.

## CPIMP Case Study

The CPIMP case study demonstrates the application of the reproducibility framework in a security-oriented analysis scenario. Selected contracts are analyzed to evaluate reproducibility, transparency, and potential indicators requiring further investigation.
