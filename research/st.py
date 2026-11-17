import requests, time, json
B="https://data.solanatracker.io"
import os
S=requests.Session(); S.headers["x-api-key"]=os.environ.get("SOLANATRACKER_API_KEY","proxy-injected")
NCALLS=[0]
def get(path, params=None, tries=6):
    for t in range(tries):
        r=S.get(B+path, params=params, timeout=60); NCALLS[0]+=1
        if r.status_code==429: time.sleep(2*(t+1)); continue
        if r.status_code>=500: time.sleep(2); continue
        r.raise_for_status(); return r.json()
    raise RuntimeError(path)
def wallet_trades(w, since_ms=0, max_pages=20):
    out=[]; cur=None
    for _ in range(max_pages):
        j=get(f"/wallet/{w}/trades", {"cursor":cur} if cur else None)
        out+=j["trades"]
        if not j.get("hasNextPage") or not j["trades"] or j["trades"][-1]["time"]<since_ms: break
        cur=j["nextCursor"]
    return [t for t in out if t["time"]>=since_ms]
