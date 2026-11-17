"""Self-learning shadow tracker.

1. LEARN   - for every Cupsey entry, download the token's trades (60 min before his first buy -> his exit) and record
             every wallet that bought BEFORE him and sold >=50% WHILE he was holding ("hit").
2. LINK    - for profitable hit wallets, find who funded them (first SOL / USDC sender or first foreign signer)
             and where the profit went (outgoing SOL >= 1). Addresses shared by several hit wallets = OPERATORS.
3. CATCH   - operators are watched by the watcher; when one funds a new wallet, that wallet is auto-added as a
             suspect before its first trade. Suspect buys/sells raise alerts.
"""
import json, time, threading, logging, statistics, math
import requests
import config, db, alerts
from solana import rpc_history, WSOL

log = logging.getLogger("tracker")
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ST = "https://data.solanatracker.io"
_s = requests.Session()
STATUS = {"entries_processed": 0, "last_error": None, "queue": 0, "credits_used": 0}

# Addresses that fund everyone (exchanges, pools, services). Learned automatically too (see is_hub).
KNOWN_HUBS = set()

def init_db():
    db.conn().executescript("""
    CREATE TABLE IF NOT EXISTS t_entries(mint TEXT PRIMARY KEY, symbol TEXT, cb REAL, cs REAL, cupsey_sol REAL,
        status TEXT, processed_ts REAL, n_pre INTEGER, n_hits INTEGER, source TEXT);
    CREATE TABLE IF NOT EXISTS t_obs(wallet TEXT, mint TEXT, cb REAL, hit INTEGER, lead_s REAL, sol_in REAL, sol_out REAL,
        first_sell_s REAL, exit_before_s REAL, program TEXT, round_frac REAL, PRIMARY KEY(wallet, mint));
    CREATE INDEX IF NOT EXISTS t_obs_w ON t_obs(wallet);
    CREATE TABLE IF NOT EXISTS t_links(wallet TEXT, other TEXT, kind TEXT, amount REAL, ts REAL, PRIMARY KEY(wallet, other, kind));
    CREATE INDEX IF NOT EXISTS t_links_o ON t_links(other);
    CREATE TABLE IF NOT EXISTS t_traced(wallet TEXT PRIMARY KEY, ts REAL, n_sigs INTEGER, first_ts REAL, hub INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS t_prec(wallet TEXT PRIMARY KEY, tokens INTEGER, followed INTEGER, prec REAL, ts REAL);
    CREATE TABLE IF NOT EXISTS t_operators(address TEXT PRIMARY KEY, label TEXT, manual INTEGER DEFAULT 0, note TEXT, added_ts REAL);
    """)

# ---------------- data fetch ----------------
def st_get(path, params=None):
    if not config.SOLANATRACKER_API_KEY:
        raise RuntimeError("SOLANATRACKER_API_KEY not set")
    for t in range(6):
        r = _s.get(ST + path, params=params, headers={"x-api-key": config.SOLANATRACKER_API_KEY}, timeout=60)
        STATUS["credits_used"] += 1
        if r.status_code == 429:
            time.sleep(2 * (t + 1)); continue
        if r.status_code >= 500:
            time.sleep(2); continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("SolanaTracker unavailable")

def fetch_window(mint, cb, cs):
    pre, cur = [], int(cb)
    for _ in range(4):  # newest-first from his buy back 60 min
        j = st_get(f"/trades/{mint}", {"sortDirection": "DESC", "cursor": cur})
        tr = [t for t in j["trades"] if t["time"] >= cb - 3600_000]
        pre += tr
        if len(tr) < len(j["trades"]) or not j.get("hasNextPage") or not j["trades"]:
            break
        cur = j["nextCursor"]
    hold, cur = [], int(cb)
    for _ in range(6):
        j = st_get(f"/trades/{mint}", {"sortDirection": "ASC", "cursor": cur})
        tr = [t for t in j["trades"] if t["time"] <= cs]
        hold += tr
        if len(tr) < len(j["trades"]) or not j.get("hasNextPage") or not j["trades"]:
            break
        cur = j["nextCursor"]
    return pre[::-1], hold

def _is_round(v):
    return abs(v - round(v)) < 0.03 or abs(v * 10 - round(v * 10)) < 0.02

# ---------------- LEARN ----------------
def analyse(mint, cb, cs, trades, cupsey):
    """Pure function: returns list of observation dicts (wallet-level) for one Cupsey entry. cb/cs in ms."""
    by = {}
    for t in trades:
        by.setdefault(t["wallet"], []).append(t)
    obs = []
    for w, ts in by.items():
        if w in cupsey:
            continue
        pb = [t for t in ts if t["type"] == "buy" and t["time"] < cb - 1000]
        if not pb:
            continue
        sd = [t for t in ts if t["type"] == "sell" and cb - 1000 <= t["time"] <= cs]
        amt_in = sum(t.get("amount", 0) for t in pb)
        amt_out = sum(t.get("amount", 0) for t in sd)
        sol_in = sum(t["volumeSol"] for t in pb)
        sol_out = sum(t["volumeSol"] for t in sd)
        hit = sol_in >= 0.1 and amt_in > 0 and amt_out >= 0.5 * amt_in
        progs = {}
        for t in ts:
            progs[t.get("program", "?")] = progs.get(t.get("program", "?"), 0) + 1
        buys = [t for t in ts if t["type"] == "buy"]
        obs.append(dict(wallet=w, mint=mint, cb=cb / 1000, hit=int(hit), lead_s=(cb - min(t["time"] for t in pb)) / 1000,
                        sol_in=sol_in, sol_out=sol_out,
                        first_sell_s=((min(t["time"] for t in sd) - cb) / 1000) if sd else None,
                        exit_before_s=((cs - max(t["time"] for t in sd)) / 1000) if sd else None,
                        program=max(progs, key=progs.get),
                        round_frac=sum(_is_round(t["volumeSol"]) for t in buys) / max(1, len(buys))))
    return obs

def store_obs(obs):
    for o in obs:
        db.x("""INSERT OR REPLACE INTO t_obs(wallet,mint,cb,hit,lead_s,sol_in,sol_out,first_sell_s,exit_before_s,program,round_frac)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", tuple(o[k] for k in ("wallet","mint","cb","hit","lead_s","sol_in","sol_out","first_sell_s","exit_before_s","program","round_frac")))

def cupsey_wallets():
    return {w["address"] for w in db.wallets() if w["role"] == "cupsey"}

def register_entry(mint, symbol, ts, sol):
    """Called by the watcher on a Cupsey BUY."""
    r = db.q("SELECT * FROM t_entries WHERE mint=?", (mint,))
    if r and ts - r[0]["cb"] < 6 * 3600:
        db.x("UPDATE t_entries SET cupsey_sol=cupsey_sol+? WHERE mint=?", (sol, mint))
        return
    db.x("INSERT OR REPLACE INTO t_entries(mint,symbol,cb,cs,cupsey_sol,status,source) VALUES(?,?,?,?,?,'open','live')", (mint, symbol, ts, None, sol))

def register_exit(mint, ts):
    db.x("UPDATE t_entries SET cs=? WHERE mint=? AND status='open'", (ts, mint))

def _due_entries():
    now = time.time()
    out = []
    for e in db.q("SELECT * FROM t_entries WHERE status='open'"):
        if (e["cupsey_sol"] or 0) < config.TRACK_MIN_SOL:
            if now - e["cb"] > 6 * 3600:
                db.x("UPDATE t_entries SET status='skipped (small)' WHERE mint=?", (e["mint"],))
            continue
        cupsey_open = db.q("""SELECT
              (SELECT COALESCE(SUM(tokens),0) FROM events WHERE mint=? AND role='cupsey' AND side='BUY' AND ts>=?) b,
              (SELECT COALESCE(SUM(tokens),0) FROM events WHERE mint=? AND role='cupsey' AND side='SELL' AND ts>=?) s""",
                           (e["mint"], e["cb"] - 5, e["mint"], e["cb"] - 5))[0]
        sold_out = cupsey_open["b"] > 0 and cupsey_open["s"] >= 0.9 * cupsey_open["b"]
        if (sold_out and e["cs"] and now - e["cs"] > 60) or now - e["cb"] > 45 * 60 + 60:
            out.append(e)
    return out

def process_entry(e):
    cb = e["cb"] * 1000
    cs = (e["cs"] or min(time.time(), e["cb"] + 45 * 60)) * 1000
    pre, hold = fetch_window(e["mint"], cb, cs)
    obs = analyse(e["mint"], cb, cs, pre + hold, cupsey_wallets())
    store_obs(obs)
    hits = [o for o in obs if o["hit"]]
    db.x("UPDATE t_entries SET status='done', processed_ts=?, n_pre=?, n_hits=? WHERE mint=?", (time.time(), len(obs), len(hits), e["mint"]))
    STATUS["entries_processed"] += 1
    # trace links for profitable hits (cheap for fresh wallets, skipped for busy ones)
    for o in sorted(hits, key=lambda o: -(o["sol_out"] - o["sol_in"]))[:25]:
        if o["sol_out"] - o["sol_in"] >= 0.3:
            try:
                trace(o["wallet"])
            except Exception as ex:
                log.debug("trace %s failed: %s", o["wallet"], ex)
    refresh_operators()
    flag_new_suspects()

# ---------------- LINK ----------------
def _transfers_in_tx(t, me):
    """Yield (counterparty, kind, amount, direction) for SOL and USDC moves involving `me`."""
    m = t["meta"]; keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
    swap = len(m.get("postTokenBalances") or []) > 2  # DEX swaps touch many token accounts -> ignore their SOL moves
    out = []
    signer = keys[0]
    if me in keys and not swap:
        i = keys.index(me)
        d = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
        if abs(d) >= 0.01:
            for j, k in enumerate(keys):
                dj = (m["postBalances"][j] - m["preBalances"][j]) / 1e9
                if j != i and dj * d < 0 and abs(dj) >= 0.5 * abs(d):
                    out.append((k, "sol", abs(d), "in" if d > 0 else "out"))
    pre = {b["accountIndex"]: b for b in m.get("preTokenBalances") or []}
    usdc = {}
    for b in m.get("postTokenBalances") or []:
        if b["mint"] != USDC:
            continue
        p = pre.get(b["accountIndex"])
        d = float(b["uiTokenAmount"]["uiAmountString"] or 0) - (float(p["uiTokenAmount"]["uiAmountString"] or 0) if p else 0)
        usdc[b.get("owner")] = usdc.get(b.get("owner"), 0) + d
    if me in usdc and not swap:
        for o, d in usdc.items():
            if o != me and d * usdc[me] < 0 and abs(usdc[me]) >= 20:
                out.append((o, "usdc", abs(usdc[me]), "in" if usdc[me] > 0 else "out"))
    if signer != me and not swap and not out and me in keys:
        out.append((signer, "signer", 0, "in"))
    return out

def is_hub(addr):
    """Exchanges / pools / services: very busy. Cached in t_traced.hub."""
    if addr in KNOWN_HUBS:
        return True
    r = db.q("SELECT hub FROM t_traced WHERE wallet=?", (addr,))
    if r:
        return bool(r[0]["hub"])
    s = rpc_history("getSignaturesForAddress", [addr, {"limit": 1000}]) or []
    hub = len(s) == 1000 and (s[0]["blockTime"] - s[-1]["blockTime"]) < 6 * 3600
    db.x("INSERT OR IGNORE INTO t_traced(wallet,ts,n_sigs,first_ts,hub) VALUES(?,?,?,?,?)", (addr, time.time(), len(s), None, int(hub)))
    return hub

def trace(w, max_pages=2):
    if db.q("SELECT 1 FROM t_traced WHERE wallet=? AND ts>?", (w, time.time() - 7 * 86400)):
        return
    allr, before = [], None
    for _ in range(max_pages):
        p = {"limit": 1000}
        if before: p["before"] = before
        r = rpc_history("getSignaturesForAddress", [w, p]) or []
        allr += r
        if len(r) < 1000: break
        before = r[-1]["signature"]
    complete = bool(allr) and len(allr) < 1000 * max_pages
    db.x("INSERT OR REPLACE INTO t_traced(wallet,ts,n_sigs,first_ts,hub) VALUES(?,?,?,?,0)",
         (w, time.time(), len(allr), allr[-1]["blockTime"] if allr and complete else None))
    ok = [s for s in allr if not s.get("err")]
    picks = []
    if complete:
        picks += list(reversed(ok))[:6]          # funding: earliest txs
    picks += ok[:15]                              # profit sinks: most recent txs
    seen = set()
    for s in picks:
        if s["signature"] in seen: continue
        seen.add(s["signature"])
        t = rpc_history("getTransaction", [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
        if not t: continue
        for other, kind, amt, direction in _transfers_in_tx(t, w):
            if other == w: continue
            k = ("fund_" if direction == "in" else "sink_") + kind
            if direction == "out" and kind == "sol" and amt < 1: continue
            db.x("INSERT OR IGNORE INTO t_links(wallet,other,kind,amount,ts) VALUES(?,?,?,?,?)", (w, other, k, amt, s.get("blockTime")))

def refresh_operators():
    """Addresses linked to >=2 distinct hit wallets (and not a hub) become operators."""
    rows = db.q("""SELECT l.other a, COUNT(DISTINCT l.wallet) n, SUM(CASE WHEN h.hits>=2 THEN 1 ELSE 0 END) n2 FROM t_links l
                   JOIN (SELECT wallet, SUM(hit) hits FROM t_obs GROUP BY wallet HAVING hits>=1) h ON h.wallet=l.wallet
                   GROUP BY l.other HAVING n>=3 OR n2>=2""")
    for r in rows:
        if db.q("SELECT 1 FROM t_operators WHERE address=?", (r["a"],)):
            continue
        if is_hub(r["a"]):
            continue
        db.x("INSERT INTO t_operators(address,label,manual,note,added_ts) VALUES(?,?,0,?,?)", (r["a"], f"Candidate operator {r['a'][:4]}", f"auto: linked to {r['n']} wallets that front-ran Cupsey", time.time()))
        alerts.send("info", f"🧬 Candidate operator: {r['a'][:6]}…", f"Linked (funding / profit flow) to {r['n']} wallets that front-ran Cupsey. Review it on the Suspects tab and switch it on to auto-watch the wallets it funds.")

# ---------------- precision ----------------
_cup_cache = {"t": 0, "cb": {}}
def cupsey_first_buys():
    """mint -> first buy time (ms) for all Cupsey wallets, from SolanaTracker (cached 3 h) + live events."""
    if time.time() - _cup_cache["t"] > 3 * 3600:
        cb = {}
        for w in cupsey_wallets():
            cur = None
            for _ in range(2):
                j = st_get(f"/wallet/{w}/trades", {"cursor": cur} if cur else None)
                for t in j["trades"]:
                    if t["from"]["address"] == WSOL:
                        m = t["to"]["address"]; cb[m] = min(cb.get(m, 1e20), t["time"])
                if not j.get("hasNextPage"): break
                cur = j["nextCursor"]
        _cup_cache.update(t=time.time(), cb=cb)
    cb = dict(_cup_cache["cb"])
    for e in db.q("SELECT mint, MIN(ts) t FROM events WHERE role='cupsey' AND side='BUY' GROUP BY mint"):
        cb[e["mint"]] = min(cb.get(e["mint"], 1e20), e["t"] * 1000)
    return cb

def measure_precision(w):
    """Of the wallet's own recent tokens, share that Cupsey bought within 60 min AFTER it (1 API credit)."""
    r = db.q("SELECT * FROM t_prec WHERE wallet=? AND ts>?", (w, time.time() - 3 * 86400))
    if r:
        return r[0]["prec"]
    cb = cupsey_first_buys()
    if not cb:
        return None
    lo, hi = min(cb.values()), max(cb.values())
    j = st_get(f"/wallet/{w}/trades")
    fb = {}
    for t in j["trades"]:
        if t["from"]["address"] == WSOL and lo <= t["time"] <= hi - 3600_000:
            m = t["to"]["address"]; fb[m] = min(fb.get(m, 1e20), t["time"])
    n = len(fb)
    fol = sum(1 for m, tm in fb.items() if m in cb and -2000 <= cb[m] - tm <= 3600_000)
    prec = fol / n if n >= 5 else None
    db.x("INSERT OR REPLACE INTO t_prec(wallet,tokens,followed,prec,ts) VALUES(?,?,?,?,?)", (w, n, fol, prec, time.time()))
    return prec

# ---------------- scoring ----------------
def wallet_stats():
    rows = db.q("""SELECT wallet, COUNT(*) n_pre, SUM(hit) hits, SUM(CASE WHEN hit=1 THEN sol_out-sol_in ELSE 0 END) profit,
                   AVG(CASE WHEN hit=1 THEN lead_s END) lead, AVG(round_frac) rnd,
                   SUM(CASE WHEN hit=1 AND exit_before_s BETWEEN 0 AND 30 AND first_sell_s>=5 THEN 1 ELSE 0 END) antic,
                   MAX(cb) last_cb, MIN(cb) first_cb
                   FROM t_obs GROUP BY wallet HAVING hits>=1""")
    n_entries = max(1, db.q("SELECT COUNT(*) n FROM t_entries WHERE status='done'")[0]["n"])
    ops = {r["address"] for r in db.q("SELECT address FROM t_operators")}
    links = {}
    for l in db.q("SELECT wallet, other, kind FROM t_links"):
        if l["other"] in ops:
            links.setdefault(l["wallet"], set()).add(l["other"])
    traced = {r["wallet"]: r for r in db.q("SELECT * FROM t_traced")}
    precs = {r["wallet"]: r for r in db.q("SELECT * FROM t_prec")}
    out = []
    for r in rows:
        hits = r["hits"] or 0
        rate = hits / r["n_pre"]
        tr = traced.get(r["wallet"])
        burner = bool(tr and tr["n_sigs"] and tr["n_sigs"] < 1500 and tr["first_ts"] and time.time() - tr["first_ts"] < 14 * 86400)
        pr = precs.get(r["wallet"]); prec = pr["prec"] if pr else None
        s = 0
        s += 20 * min(1, math.log1p(hits) / math.log1p(8))       # repeat behaviour
        s += 10 * rate if r["n_pre"] >= 2 else 3 * rate           # hits / times it pre-bought
        s += 10 * min(1, (r["antic"] or 0) / 3)                   # sold right before Cupsey's exit
        s += 5 * min(1, max(0, r["profit"] or 0) / 20)
        s += 25 if r["wallet"] in links else 0                    # linked to an operator
        s += 30 * min(1, prec / 0.25) if prec is not None else 0  # Cupsey buys what it bought (selectivity)
        s += 5 if burner else 0
        if prec is not None and prec < 0.05 and r["wallet"] not in links:
            s *= 0.5                                              # hyperactive trader that catches his coins by volume
        out.append(dict(wallet=r["wallet"], score=round(min(100, s)), hits=hits, n_pre=r["n_pre"], rate=round(rate, 2),
                        profit=round(r["profit"] or 0, 2), lead_s=round(r["lead"] or 0), antic=r["antic"] or 0,
                        round_frac=round(r["rnd"] or 0, 2), operators=sorted(links.get(r["wallet"], [])), burner=burner,
                        prec=prec, prec_n=(pr["tokens"] if pr else None), last=r["last_cb"], first=r["first_cb"]))
    out.sort(key=lambda x: -x["score"])
    return out, n_entries

def flag_new_suspects(max_measure=15):
    """Measure precision for promising wallets (1 credit each), then auto-watch high scorers."""
    stats, _ = wallet_stats()
    measured = 0
    for s in stats:
        if measured >= max_measure or s["score"] < config.SUSPECT_AUTO_WATCH_SCORE - 30:
            break
        if s["prec"] is None and not db.q("SELECT 1 FROM t_prec WHERE wallet=?", (s["wallet"],)):
            try:
                measure_precision(s["wallet"]); measured += 1
            except Exception as ex:
                log.debug("precision %s: %s", s["wallet"], ex)
    stats, _ = wallet_stats()
    for s in stats:
        if s["score"] < config.SUSPECT_AUTO_WATCH_SCORE:
            break
        if s["prec"] is None and not s["operators"]:
            continue  # never auto-watch without the selectivity check
        if not db.q("SELECT 1 FROM wallet_overrides WHERE address=?", (s["wallet"],)):
            db.x("INSERT INTO wallet_overrides(address,enabled,label,role,added_manually,added_ts) VALUES(?,?,?,?,?,?)",
                 (s["wallet"], 1, f"Suspect {s['wallet'][:4]}", "suspect", 1, time.time()))
            alerts.send("info", f"🕵️ New suspect auto-watched: {s['wallet'][:6]}…",
                        f"Score {s['score']}: front-ran Cupsey {s['hits']}× (profit {s['profit']} SOL). You'll get alerts when it trades.")

def on_operator_transfer(op, child, kind, amount, ts):
    """Watcher hook: an operator sent funds to `child`."""
    if child == op or is_hub(child):
        return
    db.x("INSERT OR IGNORE INTO t_links(wallet,other,kind,amount,ts) VALUES(?,?,?,?,?)", (child, op, "fund_" + kind, amount, ts))
    if not db.q("SELECT 1 FROM wallet_overrides WHERE address=?", (child,)):
        db.x("INSERT INTO wallet_overrides(address,enabled,label,role,added_manually,added_ts) VALUES(?,?,?,?,?,?)",
             (child, 1, f"Child of {op[:4]} ({child[:4]})", "suspect", 1, time.time()))
        alerts.send("shadow_buy", f"🧬 Operator {op[:6]}… funded a NEW wallet",
                    f"`{child}` received {amount:.2f} {kind.upper()}. It's now watched - you'll be alerted on its first trade.", urgent=True)

# ---------------- seeding / loop ----------------
def seed_from_file(path):
    try:
        data = json.load(open(path))
    except Exception:
        return
    if db.q("SELECT COUNT(*) n FROM t_entries")[0]["n"] > 0:
        return
    for e in data.get("entries", []):
        db.x("INSERT OR IGNORE INTO t_entries(mint,symbol,cb,cs,cupsey_sol,status,processed_ts,n_pre,n_hits,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
             (e["mint"], e.get("symbol"), e["cb"], e["cs"], e.get("cupsey_sol"), "done", time.time(), e.get("n_pre"), e.get("n_hits"), "research"))
    store_obs(data.get("obs", []))
    for l in data.get("links", []):
        db.x("INSERT OR IGNORE INTO t_links(wallet,other,kind,amount,ts) VALUES(?,?,?,?,?)", tuple(l))
    for o in data.get("operators", []):
        db.x("INSERT OR IGNORE INTO t_operators(address,label,manual,note,added_ts) VALUES(?,?,?,?,?)", (o["address"], o["label"], 1, o.get("note"), time.time()))
    for w, n, fol, prec in data.get("prec", []):
        db.x("INSERT OR REPLACE INTO t_prec(wallet,tokens,followed,prec,ts) VALUES(?,?,?,?,?)", (w, n, fol, prec, time.time()))
    for addr, label in data.get("watch", []):
        db.x("INSERT OR IGNORE INTO wallet_overrides(address,enabled,label,role,added_manually,added_ts) VALUES(?,?,?,?,?,?)",
             (addr, 1, label, "suspect", 1, time.time()))
    for h in data.get("hubs", []):
        db.x("INSERT OR IGNORE INTO t_traced(wallet,ts,n_sigs,first_ts,hub) VALUES(?,?,?,?,1)", (h, time.time(), 1000, None))
    log.info("tracker seeded with %d entries", len(data.get("entries", [])))

def loop():
    while True:
        try:
            due = _due_entries()
            STATUS["queue"] = len(due)
            for e in due:
                if not config.SOLANATRACKER_API_KEY:
                    break
                day = time.strftime("%Y-%m-%d")
                used = db.kv_get("credits:" + day, 0)
                if used >= config.TRACKER_DAILY_CREDITS:
                    STATUS["last_error"] = f"daily credit cap reached ({used})"
                    break
                before = STATUS["credits_used"]
                try:
                    process_entry(e)
                except Exception as ex:
                    STATUS["last_error"] = f"{e['mint'][:6]}: {ex}"
                    log.warning("process %s failed: %s", e["mint"], ex)
                    db.x("UPDATE t_entries SET status='error' WHERE mint=?", (e["mint"],))
                db.kv_set("credits:" + day, used + STATUS["credits_used"] - before)
        except Exception as ex:
            STATUS["last_error"] = str(ex)
        time.sleep(30)

def start():
    init_db()
    seed_from_file(config.ROOT / "data" / "tracker_seed.json")
    threading.Thread(target=loop, daemon=True, name="tracker").start()
