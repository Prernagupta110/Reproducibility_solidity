# Empirical Study of Solidity Smart Contract Compilation Reproducibility

A research pipeline that measures whether **verified** Solidity smart contracts
can be **recompiled to their on-chain bytecode**. For each contract it fetches
the verified source and exact compiler settings from Etherscan and Sourcify,
recompiles locally in a controlled environment, and compares the result against
the deployed bytecode — classifying each contract as fully reproducible,
partially reproducible (executable code identical, only metadata differs), or
genuinely mismatching, and identifying the technical cause of each difference.

Scope: Ethereum mainnet, comparing two source platforms (Etherscan vs Sourcify). Multi-chain (e.g. PulseChain, MOR),Blockscout, and a third external verifier (ReVerify) are planned future work.

---

## Research questions

- **RQ1** — To what extent are verified contracts reproducible, and what causes
  non-reproducibility? 
- **RQ2** — Do independent verification approaches agree? (Etherscan-source vs
  Sourcify-source recompilation)
- **RQ3** — How do controlled non-reproducible source changes affect
  verification? 
---

## Pilot results (initial 33-contract dataset)

These are from an initial 33-contract sample (13 reference contracts spanning
solc 0.2.1–0.8.17, plus 20 from the DISL dataset). They will be re-measured at
scale (200+), treat them as preliminary.

- **Reproducibility (runtime):** 15.2% bit-for-bit (FULL); 69.7% code-identical
  (FULL or PARTIAL). Most verified contracts are functionally reproducible but
  not bit-for-bit; the metadata trailer is the usual reason.
- **Verifier agreement (RQ2):** Etherscan-source and Sourcify-source agree on
  87.9% of comparisons; the disagreements are all library-using contracts that
  Sourcify stores differently — a real cross-platform inconsistency.
- **Cause taxonomy:** metadata trailer, immutable variables, embedded metadata,
  constructor arguments, unlinked/manually-linked libraries, and genuine codegen
  differences (cross-validated at the opcode level).

---

## Setup

```
python -m venv venv && source venv/bin/activate

```

Create a `.env` file in the project root:

```
RPC_URL=<an Ethereum mainnet JSON-RPC endpoint>
ETHERSCAN_API_KEY=<your Etherscan API key>
CHAIN_ID=1
```

`solc` versions are installed automatically per contract via `solc-select`.
(Note: on Apple Silicon, solc-select cannot run pre-0.3.6 / certain old binaries;
those contracts are logged as a documented hardware limitation.)

---

## How to run

**1. Build the dataset** (writes `contracts.txt`):
```
python load_disl.py --n 200       # 13 reference + 200 DISL contracts

```

**2. Run the core pipeline, in order:**
```
python fetch_runtime.py        # on-chain runtime bytecode
python fetch_creation.py       # on-chain creation bytecode
python fetch_etherscan.py      # verified source + settings (Etherscan)
python fetch_sourcify.py       # verified source + metadata (Sourcify)
python recompile.py            # recompile from Etherscan source
python recompile_sourcify.py   # recompile from Sourcify source
python extract_metadata.py     # decode the CBOR metadata trailer
python compare.py              # byte-level comparison -> comparison.csv
python diagnose.py             # human-readable per-contract 
```

**3. Analysis and experiments:**
```
python analyze.py              # reproducibility tables + canonicalization rate
python disasm.py               # opcode-level: embedded-constant vs real codegen
python diff_metadata.py        # field-by-field metadata.json comparison

python experiments.py rename_attack   # RQ3 demo
python experiments.py build_env       # build-environment factor
python experiments.py patch_sweep     # compiler patch-version drift (real-diff contracts)
```

---

## File-by-file purpose

**Configuration**
- `utils.py` — shared configuration: loads `.env`, defines the contract list
  (from `contracts.txt` if present, else a built-in reference set), RPC/Etherscan
  rate limiting and the failure log.

**Dataset construction**
- `load_disl.py` — draws a stratified sample (by compiler version, optimizer,
  proxy, library use) from the DISL dataset and merges it with the reference set.


**Fetching on-chain + verified data**
- `fetch_runtime.py` — fetches deployed runtime bytecode (block-pinned for
  determinism) via JSON-RPC `eth_getCode`.
- `fetch_creation.py` — fetches creation bytecode; handles factory deployments
  (Etherscan returns an empty placeholder for some, recorded as a coverage gap).
- `fetch_etherscan.py` — fetches verified source and exact compiler settings from
  Etherscan; handles single-file, multi-file, and standard-JSON formats.
- `fetch_sourcify.py` — fetches verified source and metadata from Sourcify via
  its tiered API.

**Recompilation**
- `recompile.py` — recompiles each contract from the Etherscan source using the
  recorded solc version and settings (standard-JSON, links libraries).
- `recompile_sourcify.py` — the same, from the Sourcify source, for the
  independent cross-platform comparison.

**Comparison + cause analysis**
- `extract_metadata.py` — splits and decodes the CBOR metadata trailer from the
  bytecode (detects ipfs / bzzr formats).
- `causes.py` — the cause registry: documented detectors for immutable variables,
  unlinked libraries, embedded metadata, and constructor (trailing) data, each
  with a citation to the Solidity docs.
- `compare.py` — the core comparison: classifies each (contract, kind, source)
  as FULL / PARTIAL / a named cause / missing, and writes `comparison.csv`.
- `diagnose.py` — per-contract, per-region human-readable explanation of exactly
  which bytes differ and why.
- `disasm.py` — opcode-level analysis distinguishing harmless embedded-constant
  differences (e.g. immutables) from genuine codegen differences.
- `diff_metadata.py` — compares the decoded metadata.json fields (compiler,
  settings, sources) between on-chain and local builds.

**Aggregate analysis**
- `analyze.py` — produces the summary tables, the cause taxonomy, the
  canonicalization rate (fraction of non-FULL contracts explained by documented
  causes), the Etherscan-vs-Sourcify agreement, and figures.

**Controlled experiments**
- `experiments.py` — three controlled experiments in one tool:
  `rename_attack` (RQ3: source appearance changes that preserve code but change
  the metadata hash), `build_env` (line-endings / paths / whitespace effects),
  and `patch_sweep` (recompiles genuine-codegen-difference contracts under
  multiple solc patch versions to test for patch-version drift).

**Diagnostics**
- `debug_tools.py` — investigative helpers (`creation` shows the raw Etherscan
  creation response; `badhex` locates non-hex content such as library
  placeholders in bytecode files).

---

## Outputs (written to `data/reports/`)

- `comparison.csv` — per-(contract, kind, source) reproducibility status
- `analysis.md` — summary tables, cause taxonomy, canonicalization rate
- `verifier_comparison.csv` — Etherscan-vs-Sourcify agreement
- `opcode_diagnosis.csv` — opcode-level verdicts
- `data/_failures.jsonl` — every skipped/failed contract with its reason
