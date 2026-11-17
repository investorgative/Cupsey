"""Polls the watched wallets, decodes their swaps and raises alerts."""
import time, threading, logging, requests
from concurrent.futures import ThreadPoolExecutor
import config, db, alerts
from solana import signatures, get_tx, parse_swap

log = logging.getLogger("watcher")
_meta_cache = {}
STATUS = {"started": time.time(), "last_cycle": None, "cycle_ms": None, "errors": 0, "wallets": 0}

def token_meta(mint):
    m = _meta_cache.get(mint)
    if m and time.time() - m["_t"] < 120:
        return m
    out = {"symbol": mint[:4] + "…", "name": "", "mcap": None, "_t": time.time()}
    try:
        r = requests.get(f"https://api.dexscreener.com/tokens/v1/solana/{mint}", timeout=6).json()
        if r:
            p = max(r, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
            out.update(symbol=p["baseToken"]["symbol"], name=p["baseToken"]["name"], mcap=p.get("marketCap") or p.get("fdv"))
    except Exception:
        pass
    _meta_cache[mint] = out
    return out

def fmt_mcap(v):
    if not v: return "?"
    return f"${v/1e6:.2f}M" if v >= 1e6 else f"${v/1e3:.1f}K"

CORE_MIN = lambda: config.MIN_SHADOW_SCORE_ALERT
_entry_alerted = {}   # mint -> ts of last entry alert
_exit_alerted = {}

def _is_core(w):
    return w["role"] == "cupsey" or w.get("manual") or (w.get("score") or 0) >= CORE_MIN()

def _fields(rows, meta):
    names = ", ".join(sorted({r["label"] for r in rows}))
    sol = sum(r["sol"] for r in rows)
    return [("Wallets", names[:1000]), ("Total size", f"{sol:.2f} SOL"), ("MCap", fmt_mcap(meta["mcap"]))]

def _entry_check(mint, meta):
    """Runs a few seconds after the first buy so the whole bundle has been seen."""
    now = time.time()
    if now - _entry_alerted.get(mint, 0) < 600:
        return
    rows = [r for r in db.q("SELECT * FROM events WHERE mint=? AND side='BUY' AND ts>=?", (mint, now - 90))]
    pub = [r for r in rows if r["role"] == "cupsey"]
    sh = [r for r in rows if r["role"] == "shadow" and r["label"] in _core_labels()]
    if not pub and not sh:
        return
    _entry_alerted[mint] = now
    sym = meta["symbol"]
    if pub and sh:
        kind, urgent = "setup", True
        title = f"✅ FULL-SIZE ENTRY: {sym}"
        body = (f"Cupsey's public wallets **and {len({r['wallet'] for r in sh})} shadow wallet(s)** bought together "
                f"(his real size ≈ {sum(r['sol'] for r in rows):.2f} SOL). Exit alert follows when the cluster sells.")
    elif sh:
        kind, urgent = "shadow_buy", True
        title = f"👀 SHADOW-ONLY BUY: {sym}"
        body = "A shadow wallet bought but Cupsey's public wallets did **not** (yet). This is unusual - possible pre-positioning."
    else:
        if not config.ALERT_CUPSEY_BUYS:
            return
        kind, urgent = "cupsey_buy", False
        title = f"🔵 Cupsey buy (public wallets only): {sym}"
        body = "No shadow wallet joined - likely a smaller / test position."
    alerts.send(kind, title, body, mint=mint, urgent=urgent, fields=_fields(rows, meta))
    for r in rows:
        db.x("UPDATE events SET alert=? WHERE sig=?", (kind, r["sig"]))

_core_cache = {"t": 0, "labels": set()}
def _core_labels():
    if time.time() - _core_cache["t"] > 30:
        _core_cache["labels"] = {w.get("label") or w["address"][:6] for w in db.wallets() if _is_core(w)}
        _core_cache["t"] = time.time()
    return _core_cache["labels"]

def handle(w, sig, ts, sw):
    meta = token_meta(sw["mint"])
    row = dict(ts=ts, sig=sig, wallet=w["address"], label=w.get("label") or w["address"][:6], role=w["role"], side=sw["side"],
               mint=sw["mint"], symbol=meta["symbol"], name=meta["name"], sol=round(sw["sol"], 4), tokens=sw["tokens"], mcap=meta["mcap"])
    try:
        db.x("INSERT INTO events(ts,sig,wallet,label,role,side,mint,symbol,name,sol,tokens,mcap) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
             tuple(row[k] for k in ("ts","sig","wallet","label","role","side","mint","symbol","name","sol","tokens","mcap")))
    except Exception:
        return  # duplicate signature
    if not _is_core(w):
        return  # low-conviction wallets are logged on the dashboard only
    mint = sw["mint"]
    if sw["side"] == "BUY":
        if time.time() - _entry_alerted.get(mint, 0) >= 600:
            threading.Timer(6.0, _entry_check, args=(mint, meta)).start()
        return
    # SELL by any core wallet
    now = time.time()
    if now - _exit_alerted.get(mint, 0) < 120:
        db.x("UPDATE events SET alert='exit' WHERE sig=?", (sig,))
        return
    _exit_alerted[mint] = now
    if w["role"] == "cupsey" and not config.ALERT_CUPSEY_SELLS:
        return
    opened = db.q("SELECT COUNT(*) n FROM events WHERE mint=? AND side='BUY' AND ts>=?", (mint, ts - 6 * 3600))[0]["n"]
    title = f"🚨 EXIT: {'shadow' if w['role']=='shadow' else 'Cupsey'} selling {meta['symbol']}"
    body = (f"**{row['label']}** sold {row['sol']:.2f} SOL of **{meta['symbol']}**. The cluster usually sells all 4 wallets in the same second - "
            "this is the exit signal." if opened else f"**{row['label']}** sold **{meta['symbol']}** (position opened before the watcher started).")
    alerts.send("shadow_sell", title, body, mint=mint, urgent=bool(opened),
                fields=[("Wallet", f"[{row['label']}](https://solscan.io/account/{w['address']})"), ("Size", f"{row['sol']:.3f} SOL"), ("MCap", fmt_mcap(meta['mcap']))])
    db.x("UPDATE events SET alert='exit' WHERE sig=?", (sig,))

def poll_wallet(w):
    addr = w["address"]
    key = "last_sig:" + addr
    last = db.kv_get(key)
    if last is None:
        s = signatures(addr, limit=1)
        if s:
            db.kv_set(key, s[0]["signature"])
        return
    got, before = [], None
    for _ in range(6):  # Cupsey's wallets get ~50 spam tx/s, so page if needed
        page = signatures(addr, until=last, before=before)
        got += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    if not got:
        return
    db.kv_set(key, got[0]["signature"])
    for s in reversed([s for s in got if not s.get("err")]):
        tx = get_tx(s["signature"])
        sw = parse_swap(tx, addr)
        if sw:
            handle(w, s["signature"], s.get("blockTime") or time.time(), sw)

def loop():
    pool = ThreadPoolExecutor(max_workers=4)
    while True:
        t0 = time.time()
        ws = [w for w in db.wallets() if w["enabled"]]
        STATUS["wallets"] = len(ws)
        for f in [pool.submit(poll_wallet, w) for w in ws]:
            try:
                f.result(timeout=60)
            except Exception as e:
                STATUS["errors"] += 1
                log.warning("poll error: %s", e)
        STATUS["last_cycle"] = time.time()
        STATUS["cycle_ms"] = int((time.time() - t0) * 1000)
        time.sleep(max(0.2, config.POLL_SECONDS - (time.time() - t0)))

def start():
    threading.Thread(target=loop, daemon=True, name="watcher").start()
