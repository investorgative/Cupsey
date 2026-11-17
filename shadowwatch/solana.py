"""Minimal Solana JSON-RPC client + swap parser (no SDK needed)."""
import requests, time, threading, itertools
from config import RPC_URLS

WSOL = "So11111111111111111111111111111111111111112"
STABLES = {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT"}

_s = requests.Session()
_rr = itertools.cycle(range(len(RPC_URLS)))
_lock = threading.Lock()
_backoff_until = {}

def rpc(method, params, tries=5):
    last = None
    for t in range(tries):
        with _lock:
            i = next(_rr)
        url = RPC_URLS[i]
        if _backoff_until.get(url, 0) > time.time() and len(RPC_URLS) > 1:
            continue
        try:
            r = _s.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20)
            if r.status_code == 429:
                _backoff_until[url] = time.time() + 2 + t
                time.sleep(0.3 + 0.5 * t)
                continue
            j = r.json()
            if "result" in j:
                return j["result"]
            last = j.get("error")
            if "429" in str(last) or "rate" in str(last).lower():
                _backoff_until[url] = time.time() + 2 + t
                time.sleep(0.3 + 0.5 * t)
                continue
            return None
        except Exception as e:
            last = e
            time.sleep(0.5 + t)
    return None

def signatures(addr, until=None, limit=1000, before=None):
    p = {"limit": limit, "commitment": "confirmed"}
    if until: p["until"] = until
    if before: p["before"] = before
    return rpc("getSignaturesForAddress", [addr, p]) or []

def get_tx(sig):
    for i in range(4):  # a just-confirmed tx can briefly return null on a lagging node
        t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}])
        if t:
            return t
        time.sleep(0.6 * (i + 1))
    return None

def parse_swap(tx, wallet):
    """Return dict(side, mint, sol, tokens) for a swap done by `wallet` in tx, else None.
    Works from balance deltas so it is DEX/aggregator agnostic (pump.fun, PumpSwap, Raydium, Meteora, Jupiter, Axiom...)."""
    if not tx or not tx.get("meta") or tx["meta"].get("err"):
        return None
    meta = tx["meta"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
    sol_delta = 0.0
    if wallet in keys:
        i = keys.index(wallet)
        sol_delta = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9
        if i == 0:  # fee payer: add back the fee so tiny sells aren't misread
            sol_delta += meta.get("fee", 0) / 1e9
    deltas = {}
    def acc(bals, sign):
        for b in bals or []:
            if b.get("owner") != wallet:
                continue
            amt = float(b["uiTokenAmount"].get("uiAmountString") or b["uiTokenAmount"].get("uiAmount") or 0)
            deltas[b["mint"]] = deltas.get(b["mint"], 0.0) + sign * amt
    acc(meta.get("postTokenBalances"), 1)
    acc(meta.get("preTokenBalances"), -1)
    sol_delta += deltas.pop(WSOL, 0.0)
    quote = sol_delta
    for m in list(deltas):
        if m in STABLES:  # treat stables as quote too (rough: USD -> SOL not converted)
            deltas.pop(m)
    deltas = {m: d for m, d in deltas.items() if abs(d) > 0}
    if not deltas:
        return None
    mint, d = max(deltas.items(), key=lambda kv: abs(kv[1]))
    if d > 0 and quote < -0.0005:
        return {"side": "BUY", "mint": mint, "sol": -quote, "tokens": d}
    if d < 0 and quote > 0.0005:
        return {"side": "SELL", "mint": mint, "sol": quote, "tokens": -d}
    return None
