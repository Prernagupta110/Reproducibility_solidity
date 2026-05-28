import os
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

RPC_URL = os.getenv("RPC_URL", "").strip() # .strip() aids for invisible trailing newlines
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()

# CHAIN_ID 1 = Ethereum mainnet.
CHAIN_ID = int(os.getenv("CHAIN_ID", "1").strip())

def require_secrets():
    if not RPC_URL or not ETHERSCAN_API_KEY:
        raise RuntimeError("Missing RPC_URL or ETHERSCAN_API_KEY in .env file")

_PILOT_CONTRACTS = [
    "0x418C24191aE947A78C99fDc0e45a1f96Afb254BE",   # Token (simple ERC20)
    "0xc1ABb8c93be6811aFfC70675b0432926c4BFBb5D",   # UERII 
    "0xdAC17F958D2ee523a2206206994597C13D831ec7",   # USDT 
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",   # DAI
    "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",   # UNI
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",   # WETH
    "0x514910771AF9Ca656af840dff83E8264EcF986CA",   # LINK
    "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE",   # SHIB
    "0x7645DdfEecedA57e41f92679c4aCd83c56A81D14",   # FLUX 
    "0xc3d688B66703497DAA19211EEdff47f25384cdc3",   # Compound USDCv3 
    "0x00000000006c3852cbEf3e08E8dF289169EdE581",   # Seaport 1.1 (multi-file)
    "0xA7AeFeaD2F25972D80516628417ac46b3F2604Af",   # ERC1967Proxy
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",   # USDC proxy
]

_CONTRACTS_FILE = Path(__file__).parent / "contracts.txt"
if _CONTRACTS_FILE.exists():
    CONTRACTS = [
        line.strip() for line in _CONTRACTS_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    print(f"[utils] Loaded {len(CONTRACTS)} contracts from contracts.txt")
else:
    CONTRACTS = _PILOT_CONTRACTS

# pipeline output will be under data folder 
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Block-number pin. fetch_runtime.py writes it on the first run, every other
# script that reads chain state uses the SAME block, so a run is reproducible
# even if a proxy changes its implementation a week later.
BLOCK_FILE = DATA_DIR / "_pinned_block.txt"


def get_with_retry(url, params=None, tries=5, base_sleep=1.0):
    last_exc = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code in (429, 502, 503, 504):
                time.sleep(base_sleep * (2 ** i))  
                continue
            return r
        except requests.RequestException as e:
            last_exc = e
            time.sleep(base_sleep * (2 ** i))
    if last_exc:
        raise last_exc
    return None

def post_rpc(method, params, request_id=1, tries=4, base_sleep=1.0):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}
    last_exc = None
    for i in range(tries):
        try:
            r = requests.post(RPC_URL, json=payload, timeout=30)
            r.raise_for_status()             # raises on HTTP 4xx/5xx
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"RPC error for {method}: {data['error']}")
            return data["result"]
        except (requests.RequestException, RuntimeError) as e:
            last_exc = e
            time.sleep(base_sleep * (2 ** i))
    raise last_exc

# Etherscan rate limiter. Free tier allows ~5 req/sec; we use 4 to be safe.

_last_etherscan_call = [0.0]            # list so the closure can mutate it
ETHERSCAN_MIN_INTERVAL = 0.25           # seconds between Etherscan calls


def etherscan_rate_limit():
    elapsed = time.time() - _last_etherscan_call[0]
    if elapsed < ETHERSCAN_MIN_INTERVAL:
        time.sleep(ETHERSCAN_MIN_INTERVAL - elapsed)
    _last_etherscan_call[0] = time.time()

# One bad contract should never kill a whole run;

def log_failure(script: str, address: str, error):
    log_file = DATA_DIR / "_failures.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps({
            "script": script,
            "address": address,
            "error": str(error)[:500],
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }) + "\n")