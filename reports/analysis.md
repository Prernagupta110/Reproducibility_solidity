# Reproducibility analysis

Generated from `comparison.csv`. 132 (contract, kind, source) comparisons.

### RQ1 - runtime bytecode: status distribution

| Status | Count | Share |
|---|---|---|
| PARTIAL_MATCH | 33 | 50.0% |
| FULL_MATCH | 10 | 15.2% |
| UNLINKED_LIBRARY | 8 | 12.1% |
| MISSING_DATA | 8 | 12.1% |
| IMMUTABLE_VAR_ONLY | 7 | 10.6% |
| **Total** | **66** | **100%** |

### RQ1 - creation bytecode: status distribution

| Status | Count | Share |
|---|---|---|
| PARTIAL_MATCH | 26 | 39.4% |
| MISSING_ONCHAIN | 10 | 15.2% |
| UNLINKED_LIBRARY | 10 | 15.2% |
| FULL_MATCH | 8 | 12.1% |
| MISSING_DATA | 6 | 9.1% |
| PARTIAL_KNOWN | 4 | 6.1% |
| TRAILING_DATA_ONLY | 2 | 3.0% |
| **Total** | **66** | **100%** |

### RQ1 - headline (runtime, per contract)

- Bit-for-bit FULL match: **5/33** (15.2%)
- Code-identical (FULL or PARTIAL): **23/33** (69.7%)
- PARTIAL only (metadata trailer differs): **18/33** (54.5%)

Interpretation: verified contracts are almost always functionally reproducible (identical executable code) but rarely bit-for-bit reproducible; the metadata trailer is the usual reason.

### RQ1

Of comparisons that are NOT already a FULL match (90 of 108 analyzable), **86** are fully explained by documented causes (metadata trailer, immutables, embedded metadata, constructor args, unlinked libraries) = **95.6%**.

### RQ2 - Etherscan vs Sourcify agreement

- Same status from both sources: **58/66** (87.9%)
- Different status: **8/66** (12.1%)

| Address | Kind | Etherscan | Sourcify |
|---|---|---|---|
| 0x3eee7fe99640c47abf43cd2c2b6a80eb785e38cf | runtime | IMMUTABLE_VAR_ONLY | UNLINKED_LIBRARY |
| 0x3eee7fe99640c47abf43cd2c2b6a80eb785e38cf | creation | PARTIAL_MATCH | UNLINKED_LIBRARY |
| 0xb5de343139b0fb823dbc897a3ef171591cf704d3 | runtime | PARTIAL_MATCH | UNLINKED_LIBRARY |
| 0xb5de343139b0fb823dbc897a3ef171591cf704d3 | creation | PARTIAL_MATCH | UNLINKED_LIBRARY |
| 0x2b684e8905a850a91f5eea913a19dae3926a6703 | runtime | PARTIAL_MATCH | UNLINKED_LIBRARY |
| 0x2b684e8905a850a91f5eea913a19dae3926a6703 | creation | PARTIAL_MATCH | UNLINKED_LIBRARY |
| 0xc70be5b7c19529ef642d16c10dfe91c58b5c3bf0 | runtime | PARTIAL_MATCH | UNLINKED_LIBRARY |
| 0xc70be5b7c19529ef642d16c10dfe91c58b5c3bf0 | creation | PARTIAL_MATCH | UNLINKED_LIBRARY |

### Taxonomy - causes of real (post-metadata) differences

| Status | Count | Share |
|---|---|---|
| UNLINKED_LIBRARY | 18 | 58.1% |
| IMMUTABLE_VAR_ONLY | 7 | 22.6% |
| PARTIAL_KNOWN | 4 | 12.9% |
| TRAILING_DATA_ONLY | 2 | 6.5% |
| **Total** | **31** | **100%** |

### Coverage - missing data

| Status | Count | Share |
|---|---|---|
| MISSING_DATA | 14 | 58.3% |
| MISSING_ONCHAIN | 10 | 41.7% |
| **Total** | **24** | **100%** |
