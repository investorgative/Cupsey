#!/usr/bin/env bash
# One-shot installer for Raspberry Pi OS (64-bit recommended). Run from the repo root:  bash deploy/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"
USER_NAME="$(whoami)"

echo "==> Python venv + deps"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip curl
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> cloudflared"
if ! command -v cloudflared >/dev/null; then
  ARCH="$(dpkg --print-architecture)"   # arm64 / armhf / amd64
  curl -fsSL -o /tmp/cloudflared.deb "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb"
  sudo dpkg -i /tmp/cloudflared.deb
fi

if [ ! -f .env ]; then
  cp .env.example .env
  PIN=$(printf "%04d" $((RANDOM % 10000)))
  sed -i "s/^DASHBOARD_PIN=.*/DASHBOARD_PIN=${PIN}/" .env
  echo "==> Created .env with dashboard PIN ${PIN} - edit it now to add your Discord webhook:  nano .env"
fi

echo "==> systemd service"
sudo tee /etc/systemd/system/shadowwatch.service >/dev/null <<UNIT
[Unit]
Description=ShadowWatch (Cupsey shadow wallet alerts + dashboard)
After=network-online.target
Wants=network-online.target

[Service]
User=${USER_NAME}
WorkingDirectory=${DIR}/shadowwatch
ExecStart=${DIR}/.venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now shadowwatch
echo
echo "Done. Local:  http://$(hostname -I | awk '{print $1}'):8751"
echo "Public link is posted to Discord on start, or:  journalctl -u shadowwatch | grep trycloudflare"
echo "Logs: journalctl -u shadowwatch -f"
