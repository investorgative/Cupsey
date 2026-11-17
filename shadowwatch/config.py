"""Configuration, loaded from .env (KEY=VALUE lines) next to the project root or from the environment."""
import os, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
PROJECT = ROOT.parent

def _load_env():
    for p in (PROJECT / ".env", ROOT / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_env()

def env(k, d=""):
    return os.environ.get(k, d)

PIN = env("DASHBOARD_PIN", "0000")
PORT = int(env("PORT", "8751"))
SECRET_KEY = env("SECRET_KEY", "") or None

# Comma separated list. Public RPCs work; a free Helius / QuickNode / Alchemy RPC is faster and less rate-limited.
RPC_URLS = [u.strip() for u in env("RPC_URLS", "https://api.mainnet-beta.solana.com,https://solana-rpc.publicnode.com").split(",") if u.strip()]
POLL_SECONDS = float(env("POLL_SECONDS", "2.5"))

DISCORD_WEBHOOK_URL = env("DISCORD_WEBHOOK_URL")
DISCORD_PING = env("DISCORD_PING", "")          # e.g. <@123456789> or @here, prepended to urgent alerts
NTFY_TOPIC = env("NTFY_TOPIC")                  # optional: phone push via ntfy.sh
NTFY_SERVER = env("NTFY_SERVER", "https://ntfy.sh")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")

SOLANATRACKER_API_KEY = env("SOLANATRACKER_API_KEY")   # only needed for re-running discovery

# Alert tuning
MIN_SHADOW_SCORE_ALERT = float(env("MIN_SHADOW_SCORE_ALERT", "40"))  # shadows below this score are watched but don't ping
ALERT_CUPSEY_BUYS = env("ALERT_CUPSEY_BUYS", "1") == "1"
ALERT_CUPSEY_SELLS = env("ALERT_CUPSEY_SELLS", "1") == "1"
SETUP_WINDOW_SECONDS = int(env("SETUP_WINDOW_SECONDS", "600"))  # shadow buy -> cupsey buy within this = setup

TUNNEL = env("TUNNEL", "1") == "1"
CLOUDFLARED_BIN = env("CLOUDFLARED_BIN", "cloudflared")

DB_PATH = env("DB_PATH", str(ROOT / "data" / "shadowwatch.db"))
WALLETS_PATH = ROOT / "data" / "wallets.json"
