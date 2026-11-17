import requests, time, json, os, sys
RPCS = ["https://api.mainnet-beta.solana.com"]
_i = 0
S = requests.Session()
def rpc(method, params, tries=8):
    global _i
    for t in range(tries):
        url = RPCS[_i % len(RPCS)]; _i += 1
        try:
            r = S.post(url, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=30)
            if r.status_code == 429:
                time.sleep(1.5*(t+1)); continue
            j = r.json()
            if "result" in j: return j["result"]
            if "error" in j:
                msg = str(j["error"])
                if "429" in msg or "rate" in msg.lower() or "Too many" in msg:
                    time.sleep(1.5*(t+1)); continue
                return None
        except Exception as e:
            time.sleep(1+t)
    return None

def sigs(addr, before=None, limit=1000, until=None):
    p = {"limit": limit}
    if before: p["before"] = before
    if until: p["until"] = until
    return rpc("getSignaturesForAddress", [addr, p]) or []

def tx(sig):
    return rpc("getTransaction", [sig, {"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
