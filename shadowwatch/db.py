import sqlite3, threading, json, time
from config import DB_PATH, WALLETS_PATH

_lock = threading.RLock()
_conn = None

def conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, sig TEXT UNIQUE, wallet TEXT, label TEXT, role TEXT, side TEXT,
            mint TEXT, symbol TEXT, name TEXT, sol REAL, tokens REAL, mcap REAL, alert TEXT);
        CREATE INDEX IF NOT EXISTS ev_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS ev_mint ON events(mint);
        CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS wallet_overrides(address TEXT PRIMARY KEY, enabled INTEGER, label TEXT, role TEXT, added_manually INTEGER DEFAULT 0, added_ts REAL);
        CREATE TABLE IF NOT EXISTS login_fail(ip TEXT PRIMARY KEY, n INTEGER, until REAL);
        """)
    return _conn

def q(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]

def x(sql, args=()):
    with _lock:
        return conn().execute(sql, args)

def kv_get(k, d=None):
    r = q("SELECT v FROM kv WHERE k=?", (k,))
    return json.loads(r[0]["v"]) if r else d

def kv_set(k, v):
    x("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))

def load_wallet_file():
    try:
        return json.loads(WALLETS_PATH.read_text())
    except Exception:
        return {"generated": None, "cupsey": [], "shadows": []}

def wallets():
    """Merged list of watched wallets: discovery file + manual overrides."""
    data = load_wallet_file()
    ov = {r["address"]: r for r in q("SELECT * FROM wallet_overrides")}
    out = []
    for w in data.get("cupsey", []):
        w = dict(w, role="cupsey")
        out.append(w)
    for w in data.get("shadows", []):
        w = dict(w, role="shadow")
        out.append(w)
    known = {w["address"] for w in out}
    for a, r in ov.items():
        if a not in known and r.get("added_manually"):
            out.append({"address": a, "label": r.get("label") or a[:6], "role": r.get("role") or "shadow",
                        "score": None, "tier": "manual", "evidence": ["Added manually in the dashboard"], "manual": True})
    for w in out:
        o = ov.get(w["address"])
        default_on = w["role"] == "cupsey" or (w.get("score") or 0) >= 45 or w.get("manual")
        w["enabled"] = bool(o["enabled"]) if o and o["enabled"] is not None else default_on
        if o and o.get("label"):
            w["label"] = o["label"]
    return out
