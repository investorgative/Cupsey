"""ShadowWatch - Raspberry Pi wallet watcher + PIN-protected dashboard on :8751."""
import os, time, hmac, logging, secrets, json
from functools import wraps
from flask import Flask, request, session, redirect, jsonify, render_template, url_for
import config, db, alerts, watcher, tunnel, tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = Flask(__name__, static_folder="static", template_folder="templates")

def _secret():
    s = config.SECRET_KEY or db.kv_get("secret_key")
    if not s:
        s = secrets.token_hex(32); db.kv_set("secret_key", s)
    return s
app.secret_key = _secret()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14)

# ---- auth (4 digit PIN, with lockout because 10k combinations are brute-forceable) ----
MAX_FAILS, LOCK_SECONDS, GLOBAL_MAX_FAILS = 5, 15 * 60, 25

def client_ip():
    if request.remote_addr in ("127.0.0.1", "::1"):  # behind cloudflared
        return request.headers.get("CF-Connecting-IP") or request.remote_addr
    return request.remote_addr

def locked(ip):
    now = time.time()
    r = db.q("SELECT * FROM login_fail WHERE ip=?", (ip,))
    g = db.q("SELECT * FROM login_fail WHERE ip='*global*'")
    return (r and r[0]["until"] > now) or (g and g[0]["until"] > now)

def register_fail(ip):
    now = time.time()
    for key, mx in ((ip, MAX_FAILS), ("*global*", GLOBAL_MAX_FAILS)):
        r = db.q("SELECT * FROM login_fail WHERE ip=?", (key,))
        n = (r[0]["n"] if r and r[0]["until"] > now - 3600 else 0) + 1
        until = now + LOCK_SECONDS if n >= mx else now  # 'until' doubles as last-fail time
        if n >= mx: n = 0
        db.x("INSERT INTO login_fail(ip,n,until) VALUES(?,?,?) ON CONFLICT(ip) DO UPDATE SET n=excluded.n, until=excluded.until", (key, n, until))
        if until > now:
            alerts.send("info", "🔐 Dashboard login locked", f"Too many wrong PINs ({'all IPs' if key=='*global*' else ip}). Locked 15 min.")

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("ok"):
            if request.path.startswith("/api/"):
                return jsonify(error="auth"), 401
            return redirect(url_for("login"))
        return f(*a, **k)
    return w

@app.after_request
def headers(r):
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "no-referrer"
    return r

@app.route("/login", methods=["GET", "POST"])
def login():
    err = None
    ip = client_ip()
    if request.method == "POST":
        if locked(ip):
            err = "Too many attempts. Try again in 15 minutes."
        elif hmac.compare_digest(request.form.get("pin", ""), config.PIN):
            session.clear(); session["ok"] = True; session.permanent = True
            return redirect("/")
        else:
            register_fail(ip); time.sleep(1.0); err = "Wrong code."
    return render_template("login.html", err=err)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/")
@login_required
def index():
    return render_template("index.html")

# ---- API ----
def setups(hours=24):
    """Tokens where shadow wallets bought before a Cupsey buy, with live state."""
    since = time.time() - hours * 3600
    core = {w["address"] for w in db.wallets() if w["role"] == "cupsey" or w.get("manual") or (w.get("score") or 0) >= config.MIN_SHADOW_SCORE_ALERT}
    ev = [e for e in db.q("SELECT * FROM events WHERE ts>=? ORDER BY ts", (since,)) if e["wallet"] in core]
    by = {}
    for e in ev:
        by.setdefault(e["mint"], []).append(e)
    out = []
    for mint, es in by.items():
        cb = [e for e in es if e["role"] == "cupsey" and e["side"] == "BUY"]
        sb = [e for e in es if e["role"] == "shadow" and e["side"] == "BUY"]
        if not sb:
            continue
        ss = [e for e in es if e["role"] == "shadow" and e["side"] == "SELL"]
        cs = [e for e in es if e["role"] == "cupsey" and e["side"] == "SELL"]
        first_c = cb[0]["ts"] if cb else None
        lead = [first_c - e["ts"] for e in sb if first_c and e["ts"] <= first_c]
        sold = ss or cs
        if not cb: state = "shadow only"
        else: state = "EXIT - cluster selling" if sold else "LIVE - full size"
        if sold and time.time() - max(e["ts"] for e in ss + cs) > 120: state = "closed"
        out.append({"mint": mint, "symbol": es[-1]["symbol"], "state": state, "shadows": sorted({e["label"] for e in sb}),
                    "first_shadow": sb[0]["ts"], "cupsey_buy": first_c, "lead_s": max(lead) if lead else None,
                    "shadow_sold": bool(ss), "cupsey_sold": bool(cs), "last": es[-1]["ts"], "mcap": es[-1]["mcap"]})
    return sorted(out, key=lambda s: -s["last"])

@app.route("/api/state")
@login_required
def api_state():
    data = db.load_wallet_file()
    stats = db.q("SELECT wallet, COUNT(*) n, SUM(side='BUY') buys, SUM(side='SELL') sells, MAX(ts) last FROM events GROUP BY wallet")
    st = {s["wallet"]: s for s in stats}
    ws = db.wallets()
    for w in ws:
        w["live"] = st.get(w["address"])
    return jsonify(
        now=time.time(), tunnel_url=db.kv_get("tunnel_url"), watcher=watcher.STATUS,
        alerts={"discord": bool(config.DISCORD_WEBHOOK_URL), "ntfy": bool(config.NTFY_TOPIC), "telegram": bool(config.TELEGRAM_BOT_TOKEN)},
        wallets=ws, generated=data.get("generated"), method=data.get("method"), summary=data.get("summary"),
        events=db.q("SELECT * FROM events ORDER BY ts DESC LIMIT 250"), setups=setups(),
    )

@app.route("/api/wallet", methods=["POST"])
@login_required
def api_wallet():
    j = request.get_json(force=True)
    a = (j.get("address") or "").strip()
    if not (32 <= len(a) <= 44 and a.isalnum()):
        return jsonify(error="bad address"), 400
    if j.get("delete"):
        db.x("DELETE FROM wallet_overrides WHERE address=? AND added_manually=1", (a,))
        return jsonify(ok=True)
    cur = db.q("SELECT * FROM wallet_overrides WHERE address=?", (a,))
    cur = cur[0] if cur else {"enabled": None, "label": None, "role": None, "added_manually": 0}
    enabled = j.get("enabled", cur["enabled"] if cur["enabled"] is not None else (1 if j.get("add") else None))
    db.x("""INSERT INTO wallet_overrides(address,enabled,label,role,added_manually,added_ts) VALUES(?,?,?,?,?,?)
            ON CONFLICT(address) DO UPDATE SET enabled=excluded.enabled, label=excluded.label, role=excluded.role, added_manually=excluded.added_manually""",
         (a, None if enabled is None else int(bool(enabled)), j.get("label", cur["label"]), j.get("role", cur["role"]) or "shadow",
          int(bool(j.get("add") or cur["added_manually"])), time.time()))
    return jsonify(ok=True)

@app.route("/api/tracker")
@login_required
def api_tracker():
    stats, n = tracker.wallet_stats()
    watched = {r["address"] for r in db.q("SELECT address FROM wallet_overrides WHERE enabled=1")}
    for s in stats[:200]:
        s["watched"] = s["wallet"] in watched
    ops = db.q("SELECT * FROM t_operators ORDER BY manual DESC, added_ts DESC")
    en = {w["address"]: w["enabled"] for w in db.wallets() if w["role"] == "operator"}
    for o in ops:
        o["enabled"] = en.get(o["address"], False)
        o["children"] = db.q("SELECT wallet, kind, amount, ts FROM t_links WHERE other=? ORDER BY ts DESC LIMIT 50", (o["address"],))
    return jsonify(status=tracker.STATUS, n_entries=n, suspects=stats[:200], operators=ops,
                   entries=db.q("SELECT * FROM t_entries ORDER BY cb DESC LIMIT 60"),
                   key=bool(config.SOLANATRACKER_API_KEY))

@app.route("/api/operator", methods=["POST"])
@login_required
def api_operator():
    j = request.get_json(force=True); a = (j.get("address") or "").strip()
    if not (32 <= len(a) <= 44 and a.isalnum()):
        return jsonify(error="bad address"), 400
    if j.get("delete"):
        db.x("DELETE FROM t_operators WHERE address=?", (a,))
    else:
        db.x("INSERT OR REPLACE INTO t_operators(address,label,manual,note,added_ts) VALUES(?,?,?,?,?)", (a, j.get("label") or f"Operator {a[:4]}", 1, "added manually", time.time()))
    return jsonify(ok=True)

@app.route("/api/test-alert", methods=["POST"])
@login_required
def api_test():
    alerts.send("info", "🧪 ShadowWatch test", "If you see this, alerts work.", mint="So11111111111111111111111111111111111111112")
    return jsonify(ok=True)

def main():
    alerts.start()
    tracker.start()
    watcher.start()
    if config.TUNNEL:
        tunnel.start()
    alerts.send("info", "🟢 ShadowWatch started", f"Watching {len([w for w in db.wallets() if w['enabled']])} wallets.")
    from waitress import serve
    serve(app, host="0.0.0.0", port=config.PORT, threads=8)

if __name__ == "__main__":
    main()
