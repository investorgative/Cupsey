# ShadowWatch: Cupsey shadow-wallet tracker

This runs on a Raspberry Pi. It watches Cupsey's public wallets and the hidden wallets he bundles them with, sends alerts to Discord (optionally ntfy or Telegram), and serves a dashboard behind a PIN on port **8751**. A free Cloudflare tunnel makes the dashboard reachable from your phone.

## What was found

| Wallet | Role | Conviction |
|---|---|---|
| `2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f` | Cupsey, public (kolscan) | official |
| `suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK` | Cupsey, public (older) | official |
| `FxN3VZ4BosL5urG2yoeQ156JSdmavm9K5fdLxjkPmaMR` | **Shadow A** | 94 / 100 |
| `7NAd2EpYGGeFofpyvgehSXhH5vg6Ry6VRMW2Y6jiqCu1` | **Shadow B** | 88 / 100 |

- All four wallets buy in **one bundle**: same block, consecutive transaction positions, shuffled order. Sometimes a shadow wallet lands first. A copy-trader can't do that.
- The shadows appear on 97% of his tokens and trade **nothing else**: 216 of 216 of their recent tokens were Cupsey tokens.
- Together the shadows put in **0.99×** the public wallets' size, so his real position is about 2× what kolscan shows.
- They sell **in the same second** as the public wallets (139 of 139 cases). I found no wallet that systematically buys *before* him; those early buyers are generic snipers.
- So following the shadows gives no timing edge over following the public wallets. It does tell you whether a buy is a full-size entry, and it keeps working if he rotates his public wallets.
- ⚠ His public wallets' closed positions were net negative over the last 30 days according to the parsed trade data. Use small size.

The full method and evidence are on the dashboard under "How it works" (source: `research/report.html`).

## Pi setup (about 10 minutes)

```bash
git clone <this repo> shadowwatch && cd shadowwatch
bash deploy/install.sh          # installs deps, cloudflared, systemd service, creates .env with a random PIN
nano .env                       # paste DISCORD_WEBHOOK_URL (and change DASHBOARD_PIN if you like)
sudo systemctl restart shadowwatch
```

- **Discord webhook:** Server settings → Integrations → Webhooks → New Webhook → Copy URL.
- To get pinged on urgent alerts, set `DISCORD_PING=<@your_user_id>`. To find your ID, enable Developer Mode in Discord, right-click yourself and choose "Copy User ID".
- **Recommended second channel:** install the free **ntfy** app and subscribe to an unguessable topic name, then put that name in `NTFY_TOPIC`. Urgent alerts arrive as high-priority pushes, which is faster and louder than Discord.
- **Faster RPC (optional):** create a free [Helius](https://helius.dev) key and set `RPC_URLS=https://mainnet.helius-rpc.com/?api-key=KEY,https://api.mainnet-beta.solana.com`.

### Dashboard link
- On your LAN: `http://<pi-ip>:8751`
- From anywhere: the app starts a Cloudflare quick tunnel and **posts the `https://….trycloudflare.com` link to Discord** each time it starts. The link changes on every restart. If you want a fixed URL, create a named tunnel on a domain you own.
- Login is a 4-digit PIN. 5 wrong tries lock that IP for 15 minutes, and 25 wrong tries in total lock everyone out for 15 minutes. You get a Discord message when a lockout happens.

### Alerts
| Alert | Meaning |
|---|---|
| ✅ **FULL-SIZE ENTRY** | Public wallets and shadow wallets bought together: the normal Cupsey bundle. |
| 👀 **SHADOW-ONLY BUY** | A shadow bought and the public wallets didn't. This hasn't happened yet; it would be the pre-positioning you suspected. |
| 🔵 Cupsey buy (public only) | No shadow joined, so probably a small or test position. |
| 🚨 **EXIT** | First sell by any wallet in the cluster. The others usually sell in the same second. |

### Useful commands
```bash
journalctl -u shadowwatch -f                       # logs
journalctl -u shadowwatch | grep trycloudflare     # current public link
sudo systemctl restart shadowwatch
```

## Self-learning tracker ("Suspects" tab)
Your idea: the shadows are throwaway wallets, so following one wallet doesn't work. You have to find the **people behind them** and catch their **next** wallet.

1. **Learn:** after every Cupsey entry of 5 SOL or more (by default), the Pi downloads that coin's trades from 60 minutes before his buy until he sells. It records every wallet that bought before him and sold at least half while he held, along with its lead time, profit, whether it got out under 30 s before him, and which trading app it used.
2. **Rank:** suspects are scored on repeats, hit rate, early exits and profit, and above all **precision**: how often Cupsey buys a coin after this wallet bought it. Hyperactive traders who catch his coins by volume score low.
3. **Link:** for profitable early buyers it traces who funded them (first SOL, first **USDC**, first co-signer) and where the profit went. An address linked to several such wallets becomes a *candidate operator*.
4. **Catch:** confirmed operators are watched. **When an operator funds a new wallet, that wallet is auto-watched immediately**, so you're alerted on its first trade: 🕵️ SUSPECT BUY ("Cupsey is NOT in yet…") and 🚨 SUSPECT SELL.

The tracker starts with today's research: 111 entries, about 5,000 early-buyer hits, the `EzcD6 → 3szYs → burner` network and 4 confirmed operators.
Cost: about 7–15 SolanaTracker credits per entry analysed (capped by `TRACKER_DAILY_CREDITS`). Funding traces use the free RPC.

## Re-running the discovery
Shadow wallets get rotated, so re-check every week or two. Put a [SolanaTracker](https://www.solanatracker.io/data-api) key in `.env` (`SOLANATRACKER_API_KEY`), then:
```bash
bash research/run_discovery.sh && sudo systemctl restart shadowwatch
```
A run uses about 1,000 API credits and takes about 45 minutes. You can also add wallets by hand on the "Shadow wallets" tab.

## Layout
```
shadowwatch/   app.py (web + PIN auth), watcher.py (RPC polling, swap decoding, alert logic),
               alerts.py (Discord/ntfy/Telegram), tunnel.py (cloudflared), data/wallets.json (discovery output)
research/      discovery pipeline: fetch_cupsey → collect → analyze → score → bundle → export
deploy/        install.sh (venv, cloudflared, systemd)
```
