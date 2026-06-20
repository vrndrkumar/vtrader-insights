#!/usr/bin/env bash
# =============================================================
# deploy.sh — VTrader Stock Intelligence
# Run this on the SERVER as root after first-time setup
# Usage:  bash deploy.sh
# =============================================================
set -e

PROJECT_DIR="/home/vtrader/insights"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo ""
echo "═══════════════════════════════════════════════"
echo "  VTrader Stock Intelligence — Deploy"
echo "═══════════════════════════════════════════════"
echo ""

# ── 1. Python venv + dependencies ────────────────────────────
echo "[1/5] Installing backend dependencies..."
cd "$BACKEND_DIR"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -r requirements.txt -q
echo "      ✓ Backend dependencies installed"

# ── 2. Build frontend ─────────────────────────────────────────
echo "[2/5] Building frontend..."
cd "$FRONTEND_DIR"
npm install --silent
# Use production env file for build
cp .env.production .env
npm run build
# Restore local env so local dev still works
cp .env.production .env.production.bak 2>/dev/null || true
echo "      ✓ Frontend built → dist/"

# ── 3. Install systemd service ────────────────────────────────
echo "[3/5] Installing systemd service..."
cp "$PROJECT_DIR/vtrader-api.service" /etc/systemd/system/vtrader-api.service
systemctl daemon-reload
systemctl enable vtrader-api
systemctl restart vtrader-api
sleep 2
if systemctl is-active --quiet vtrader-api; then
  echo "      ✓ vtrader-api service running"
else
  echo "      ✗ Service failed to start — check: journalctl -u vtrader-api -n 50"
  exit 1
fi

# ── 4. Update nginx config ────────────────────────────────────
echo "[4/5] Updating nginx config..."
cp "$PROJECT_DIR/nginx-production.conf" /etc/nginx/conf.d/insights.vtrader.in.conf
nginx -t && systemctl reload nginx
echo "      ✓ Nginx reloaded"

# ── 5. Health check ───────────────────────────────────────────
echo "[5/5] Health check..."
sleep 1
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health)
if [ "$STATUS" = "200" ]; then
  echo "      ✓ API responding — HTTP $STATUS"
else
  echo "      ✗ API health check failed (HTTP $STATUS) — check: journalctl -u vtrader-api -n 30"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Deployment complete!"
echo "  → https://insights.vtrader.in"
echo "═══════════════════════════════════════════════"
echo ""