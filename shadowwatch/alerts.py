"""Alert fan-out: Discord webhook (embeds), optional ntfy.sh push, optional Telegram."""
import requests, threading, queue, time, logging
import config

log = logging.getLogger("alerts")
_q = queue.Queue()

COLORS = {"setup": 0x22c55e, "shadow_buy": 0xeab308, "shadow_sell": 0xef4444, "cupsey_buy": 0x3b82f6,
          "cupsey_sell": 0xa855f7, "info": 0x64748b}

def links(mint):
    return (f"[DexScreener](https://dexscreener.com/solana/{mint}) · [Axiom](https://axiom.trade/meme/{mint}) · "
            f"[GMGN](https://gmgn.ai/sol/token/{mint}) · [Solscan](https://solscan.io/token/{mint})")

def send(kind, title, body, mint=None, urgent=False, fields=None):
    _q.put((kind, title, body, mint, urgent, fields or []))

def _discord(kind, title, body, mint, urgent, fields):
    if not config.DISCORD_WEBHOOK_URL:
        return
    desc = body + (("\n" + links(mint)) if mint else "")
    payload = {
        "username": "ShadowWatch",
        "content": (config.DISCORD_PING + " " if urgent and config.DISCORD_PING else "") + (title if urgent else ""),
        "embeds": [{"title": title, "description": desc, "color": COLORS.get(kind, 0x64748b),
                    "fields": [{"name": n, "value": v, "inline": True} for n, v in fields][:25],
                    "footer": {"text": f"`{mint}`" if mint else "ShadowWatch"},
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}],
    }
    for _ in range(4):
        r = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 1)))
            continue
        break

def _ntfy(kind, title, body, mint, urgent, fields):
    if not config.NTFY_TOPIC:
        return
    hdr = {"Title": title.encode("utf-8"), "Priority": "5" if urgent else "3", "Tags": kind}
    if mint:
        hdr["Click"] = f"https://dexscreener.com/solana/{mint}"
    requests.post(f"{config.NTFY_SERVER}/{config.NTFY_TOPIC}", data=(body + "\n" + " | ".join(f"{n}: {v}" for n, v in fields)).encode(), headers=hdr, timeout=10)

def _telegram(kind, title, body, mint, urgent, fields):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    txt = f"<b>{title}</b>\n{body}\n" + "\n".join(f"{n}: {v}" for n, v in fields)
    if mint:
        txt += f"\n<code>{mint}</code>\n<a href='https://dexscreener.com/solana/{mint}'>DexScreener</a> | <a href='https://axiom.trade/meme/{mint}'>Axiom</a>"
    requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                  json={"chat_id": config.TELEGRAM_CHAT_ID, "text": txt, "parse_mode": "HTML", "disable_web_page_preview": True,
                        "disable_notification": not urgent}, timeout=10)

def _worker():
    while True:
        item = _q.get()
        for fn in (_discord, _ntfy, _telegram):
            try:
                fn(*item)
            except Exception as e:
                log.warning("alert via %s failed: %s", fn.__name__, e)

def start():
    threading.Thread(target=_worker, daemon=True, name="alerts").start()
