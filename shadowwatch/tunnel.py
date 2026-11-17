"""Runs a free Cloudflare quick tunnel (https://<random>.trycloudflare.com) and reports its URL."""
import subprocess, threading, re, time, logging, shutil
import config, db, alerts

log = logging.getLogger("tunnel")
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

def _run():
    while True:
        binp = shutil.which(config.CLOUDFLARED_BIN) or config.CLOUDFLARED_BIN
        try:
            p = subprocess.Popen([binp, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{config.PORT}"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError:
            log.error("cloudflared not found - install it (see README) or set TUNNEL=0")
            db.kv_set("tunnel_url", None)
            return
        for line in p.stdout:
            m = URL_RE.search(line)
            if m and m.group(0) != db.kv_get("tunnel_url"):
                url = m.group(0)
                db.kv_set("tunnel_url", url)
                log.info("tunnel up: %s", url)
                alerts.send("info", "🌐 Dashboard online", f"New dashboard link (changes when the Pi restarts):\n{url}")
        p.wait()
        log.warning("cloudflared exited (%s), restarting in 10s", p.returncode)
        time.sleep(10)

def start():
    threading.Thread(target=_run, daemon=True, name="tunnel").start()
