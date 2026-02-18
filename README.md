# Deterministic Bytecode Reproduction Experiment
---

## Objective

This experiment reproduces and compares Solidity runtime bytecode from three sources:

1. Local compilation using `solc`
2. Etherscan verified source
3. On-chain deployed runtime bytecode

The goal is to determine:

- Whether compilation is deterministic
- Whether runtime bytecode matches deployed bytecode
- Whether differences are logical or metadata-only
- What practical barriers affect reproducibility

---

## Target Contract

0x418C24191aE947A78C99fDc0e45a1f96Afb254BE

## Environment

- macOS
- `solc-select`
- `solc 0.8.7+commit.e28d00a7`
- `curl`
- `jq`
- `diff`
- Alchemy RPC
- Etherscan API

---

## Setup

### 1. Install Correct Compiler Version

```bash
solc-select install 0.8.7
solc-select use 0.8.7
solc --version

Expected output:

Version: 0.8.7+commit.e28d00a7
```
---

### 2. Set Environment Variables

```bash
export ETHERSCAN_API_KEY=your_api_key
export RPC_URL=https://eth-mainnet.g.alchemy.com/v2/your_key
```

---

## Step 1 — Retrieve Compiler Settings

```bash
curl -s "https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=0x418C24191aE947A78C99fDc0e45a1f96Afb254BE&apikey=$ETHERSCAN_API_KEY" \
| jq -r '.result[0] | {CompilerVersion, OptimizationUsed, Runs, EVMVersion}'
```

Expected result:

```
CompilerVersion: v0.8.7+commit.e28d00a7
OptimizationUsed: 0
Runs: 200
EVMVersion: Default
```

---

## Step 2 — Download Exact Verified Source

```bash
curl -s "https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=0x418C24191aE947A78C99fDc0e45a1f96Afb254BE&apikey=$ETHERSCAN_API_KEY" \
| jq -r '.result[0].SourceCode' > From_etherscan.sol
```

---

## Step 3 — Compile Runtime Bytecode

```bash
mkdir -p build
solc --bin-runtime From_etherscan.sol -o build
mv build/Token.bin-runtime build/local.runtime.hex
```

This produces runtime bytecode only.

---

## Step 4 — Retrieve On-Chain Runtime Bytecode

```bash
curl -s -X POST $RPC_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0x418C24191aE947A78C99fDc0e45a1f96Afb254BE","latest"],"id":1}' \
| jq -r '.result' > build/runtime.onchain.hex
```

Remove the `0x` prefix:

```bash
sed 's/^0x//' build/runtime.onchain.hex > build/onchain.runtime.hex
```

---

## Step 5 — Raw Bytecode Comparison

```bash
diff build/local.runtime.hex build/onchain.runtime.hex
```

Observed difference:

Only trailing metadata section differed:

```
...a26469706673582212XXXXXXXX...
```


---

## Step 6 — Strip Metadata

```bash
mkdir -p stripped
grep -o '^.*a26469706673582212' build/local.runtime.hex > stripped/local.hex
grep -o '^.*a26469706673582212' build/onchain.runtime.hex > stripped/onchain.hex
```

Compare again:

```bash
diff stripped/local.hex stripped/onchain.hex
```

Expected output:

```
(no output)
```

---


### Runtime logic is deterministically reproducible.

---

# What Was Verified?

| Component | Verified |
|------------|-----------|
| Compiler version | ✔ |
| Optimizer setting | ✔ |
| Runtime logic equivalence | ✔ |
| Metadata equality | ✖ |
| Creation bytecode | ✖ |

This experiment demonstrates deterministic reproduction of runtime logic, not full creation bytecode equivalence.

---

# Issues Encountered

During the experiment, the following reproducibility barriers were encountered:

- Wrong `solc` version
- Wrong optimizer settings
- Metadata confusion
- Etherscan API V1 vs V2 differences
- RPC connection errors
- Lack of strip-bytecode tooling
- Head/tail truncation errors
- `0x` formatting mismatch
- API key configuration outside virtual environment


---

Future work includes:

- Multi-file reproducibility analysis
- Sourcify full-match evaluation
- Reproducibility defect taxonomy
