#!/bin/bash
set -e

echo "=== Atelier VEO: Telegram Bot API 2GB Deployment ==="

# 1. Update repository
echo "[1/4] Pulling latest code..."
git pull origin main

# 2. Check and install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "[2/4] Installing Docker..."
    apt-get update && apt-get install -y docker.io
    systemctl enable --now docker
else
    echo "[2/4] Docker is already installed."
fi

# Ensure host shared storage directory exists with full read/write permissions
mkdir -p /var/lib/telegram-bot-api
chmod 777 /var/lib/telegram-bot-api

# 3. Configure .env with API credentials
echo "[3/4] Updating .env..."
ENV_FILE=".env"

set_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

set_env "TELEGRAM_API_ID" "31048518"
set_env "TELEGRAM_API_HASH" "4f7a2efd1717ddb1eee7373e6a59f3cc"
set_env "TELEGRAM_API_SERVER" "http://localhost:8081"
set_env "MAX_VIDEO_SIZE_MB" "2000"

# Install aiofiles in virtualenv if not installed
if [ -f "/root/atelier-veo-elina/.venv/bin/pip" ]; then
    /root/atelier-veo-elina/.venv/bin/pip install aiofiles>=23.2.1 --quiet || true
fi

# 4. Start local Telegram Bot API container with direct host volume mount
echo "[4/4] Starting telegram-bot-api container (2GB local storage)..."
docker rm -f telegram-bot-api 2>/dev/null || true
docker run -d \
  -p 127.0.0.1:8081:8081 \
  --name=telegram-bot-api \
  --restart=always \
  -v /var/lib/telegram-bot-api:/var/lib/telegram-bot-api \
  -e TELEGRAM_API_ID="31048518" \
  -e TELEGRAM_API_HASH="4f7a2efd1717ddb1eee7373e6a59f3cc" \
  -e TELEGRAM_LOCAL=1 \
  aiogram/telegram-bot-api:latest

# Wait 3 seconds for container to initialize
sleep 3

# 5. Restart Elina service
echo "Restarting Elina systemd service..."
systemctl restart elina

echo "=== Deployment Complete! ==="
echo "Checking service status:"
systemctl status elina --no-pager
