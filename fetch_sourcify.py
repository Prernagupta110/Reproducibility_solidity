import json
import time
import requests
from utils import CONTRACTS, DATA_DIR, CHAIN_ID, log_failure, require_secrets

API = "https://sourcify.dev/server"
REPO = "https://repo.sourcify.dev/contracts"
OUT = DATA_DIR / "sourcify"
OUT.mkdir(parents=True, exist_ok=True)

def _get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  retry {i+1}: {e}")
            time.sleep(2 ** i)
            continue
        if r.ok or r.status_code == 404:
            return r
        if r.status_code in (429, 502, 503, 504):
            time.sleep(2 ** i)
            continue
        return r
    return None


def _settings(meta, addr, extra):
    cv = meta.get("compiler", {}).get("version", "")
    mset = meta.get("settings", {})
    opt = mset.get("optimizer", {})
    ctarget = mset.get("compilationTarget", {})
    
    path, name = next(iter(ctarget.items())) if ctarget else ("", "")
    return {
        "address": addr,
        "contract_name": name,
        "contract_path": path,
        "compiler_version_full": cv,
        "compiler_version": cv.split("+", 1)[0],  # "0.8.7+commit.." to "0.8.7"
        "optimization_used": opt.get("enabled", False),
        "runs": opt.get("runs", 200),
        "evm_version": mset.get("evmVersion", "Default"),
        "via_ir": mset.get("viaIR", False),
        "bytecode_hash": mset.get("metadata", {}).get("bytecodeHash", "ipfs"),
        "libraries": mset.get("libraries", {}),
        **extra,
    }


def _save(cdir, sources, meta_text, std_json, settings):
    sdir = cdir / "sources"
    sdir.mkdir(exist_ok=True)
    for p, c in sources.items():
        f = sdir / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c)
    (cdir / "metadata.json").write_text(meta_text)
    if std_json:
        (cdir / "standard_input.json").write_text(json.dumps(std_json, indent=2))
    (cdir / "settings.json").write_text(json.dumps(settings, indent=2))


def try_v2(addr):
    r = _get(f"{API}/v2/contract/{CHAIN_ID}/{addr}", {"fields": "all"})
    if not r or r.status_code == 404 or not r.ok:
        return None
    p = r.json()
    std = p.get("stdJsonInput") or {}
    src = {k: v.get("content", "") for k, v in std.get("sources", {}).items()}
    if not src and isinstance(p.get("sources"), list):
        src = {e["path"]: e["content"] for e in p["sources"]}
    meta_obj = p.get("metadata")
    mtext = json.dumps(meta_obj) if isinstance(meta_obj, dict) else meta_obj
    if not src or not mtext:
        return None  
    s = _settings(json.loads(mtext), addr, {
        "sourcify_match": p.get("match"),
        "sourcify_creation_match": p.get("creationMatch"),
        "sourcify_runtime_match": p.get("runtimeMatch"),
        "sourcify_source": "apiv2",
    })
    return src, mtext, std, s


def try_legacy(addr):
    r = _get(f"{API}/files/any/{CHAIN_ID}/{addr}")
    if not r or r.status_code == 404 or not r.ok:
        return None
    p = r.json()
    src, mtext = {}, None
    for f in p.get("files", []):
        name, path, content = f["name"], f.get("path", f["name"]), f["content"]
        if name == "metadata.json":
            mtext = content
        else:
            rel = path.split("sources/", 1)[1] if "sources/" in path else name
            src[rel] = content
    if not src or not mtext:
        return None
    s = _settings(json.loads(mtext), addr, {
        "sourcify_match": "exact_match" if p.get("status") == "full" else "match",
        "sourcify_source": "legacy_files",
    })
    return src, mtext, None, s


def try_repo(addr):
    for kind, dn in [("exact_match", "full_match"), ("match", "partial_match")]:
        r = _get(f"{REPO}/{dn}/{CHAIN_ID}/{addr}/metadata.json")
        if not r or not r.ok:
            continue
        try:
            meta = json.loads(r.text)
        except Exception:
            continue
        src = {}
        for path in meta.get("sources", {}):
            sr = _get(f"{REPO}/{dn}/{CHAIN_ID}/{addr}/sources/{path}")
            if sr and sr.ok:
                src[path] = sr.text
        if not src:
            continue
        s = _settings(meta, addr, {"sourcify_match": kind, "sourcify_source": "static_repo"})
        return src, r.text, None, s
    return None


if __name__ == "__main__":
    require_secrets()
    require_secrets()
    summary = []
    for addr in CONTRACTS:
        cdir = OUT / addr.lower()
        cdir.mkdir(exist_ok=True)
        print(f"\n[sourcify] {addr}")
        result = None
        for name, fn in [("apiv2", try_v2), ("legacy", try_legacy), ("repo", try_repo)]:
            try:
                result = fn(addr)
            except Exception as e:
                log_failure("fetch_sourcify", addr, f"{name}: {e}")
                result = None
            if result:
                src, mtext, std, settings = result
                _save(cdir, src, mtext, std, settings)
                print(f"  [{name} OK] match={settings['sourcify_match']} "
                      f"solc={settings['compiler_version']} files={len(src)}")
                summary.append({"address": addr, "via": name,
                                "match": settings["sourcify_match"]})
                break
            print(f"  [{name}] no data, trying next tier")
        if not result:
            (cdir / "NOT_ON_SOURCIFY.txt").write_text(
                f"{addr} not verified on Sourcify (tried v2, legacy, repo).\n")
            summary.append({"address": addr, "via": "none", "match": "absent"})
            print("  ABSENT")
    (OUT / "_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSummary -> {OUT / '_summary.json'}")