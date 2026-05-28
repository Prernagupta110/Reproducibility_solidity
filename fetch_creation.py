import json
from utils import (CONTRACTS, ETHERSCAN_API_KEY, DATA_DIR, CHAIN_ID,
                   post_rpc, get_with_retry, etherscan_rate_limit, log_failure,
                   require_secrets)

ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"
out_dir = DATA_DIR / "onchain"
out_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    require_secrets()
    for addr in CONTRACTS:
        try:
            etherscan_rate_limit()
            params = {
                "chainid": CHAIN_ID,
                "module": "contract",
                "action": "getcontractcreation",
                "contractaddresses": addr,
                "apikey": ETHERSCAN_API_KEY,
            }
            es = get_with_retry(ETHERSCAN_V2, params=params).json()
            if es.get("status") != "1":
                print(f"[creation] {addr}: Etherscan error: {es.get('result')}")
                log_failure("fetch_creation", addr, es.get("result"))
                continue

            info = es["result"][0]

            
            creation_hex = info.get("creationBytecode", "").removeprefix("0x")
            if creation_hex:
                via = "etherscan_creationBytecode"
                is_factory = bool(info.get("contractFactory"))   
            else:
               
                tx = post_rpc("eth_getTransactionByHash", [info["txHash"]])
                if tx.get("to") is None:
                    creation_hex = tx["input"].removeprefix("0x")
                    via = "direct_tx"
                    is_factory = False
                else:
                    print(f"[creation] {addr}: factory deploy, creationBytecode absent")
                    log_failure("fetch_creation", addr,
                                "factory deploy, creationBytecode absent")
                    continue

            
            info["_obtained_via"] = via
            info["_is_factory_deployed"] = is_factory
            (out_dir / f"{addr.lower()}.creation.info.json").write_text(
                json.dumps(info, indent=2))

            # ctor args are still on the tail; compare.py strips them.
            (out_dir / f"{addr.lower()}.creation.hex").write_text(creation_hex)
            print(f"[creation] {addr}: {len(creation_hex)//2} bytes  "
                  f"via={via}  factory={is_factory}")
        except Exception as e:
            print(f"[creation] {addr}: FAILED - {e}")
            log_failure("fetch_creation", addr, e)