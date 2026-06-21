#!/usr/bin/env bash
# =============================================================
# deploy.sh — VTrader Stock Intelligence
# Fresh-server-safe deployment script.
# Run this on the SERVER as root.
# Usage:  bash deploy.sh
# =============================================================
set -e

PROJECT_DIR="/home/vtrader/insights"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo ""
echo "═══════════════════════════════════════════════"
echo "  VTrader Stock Intelligence — Fresh Deploy"
echo "═══════════════════════════════════════════════"
echo ""

# ── 0. System prerequisites ──────────────────────────────────
echo "[0/6] Checking system prerequisites..."

if ! command -v python3 &> /dev/null; then
  echo "      ✗ python3 not found. Install it first: apt-get install -y python3"
  exit 1
fi
echo "      ✓ python3 found: $(python3 --version)"

# python3-venv is a SEPARATE package on Debian/Ubuntu — having python3
# does NOT guarantee venv creation works. This was the root cause of
# the previous "pip: not found" failure (venv silently created an
# empty/broken folder with no pip inside it).
if ! python3 -c "import venv" &> /dev/null; then
  echo "      → python3-venv module missing, installing..."
  apt-get update -qq
  apt-get install -y python3-venv python3-pip -qq
fi
echo "      ✓ python3-venv available"

if ! command -v node &> /dev/null; then
  echo "      → Node.js not found, installing Node 20.x..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
  apt-get install -y nodejs -qq
fi
echo "      ✓ node found: $(node --version)"

if ! command -v nginx &> /dev/null; then
  echo "      ✗ nginx not found. Install it first: apt-get install -y nginx"
  exit 1
fi
echo "      ✓ nginx found"

if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
  echo "      ✗ backend/ or frontend/ folder not found in $PROJECT_DIR"
  echo "        Upload the project first via rsync, then re-run this script."
  exit 1
fi
echo "      ✓ Project folders present"

# ── 1. Python venv + dependencies ────────────────────────────
echo ""
echo "[1/6] Setting up backend virtual environment..."
cd "$BACKEND_DIR"

# Remove any broken/partial venv from a previous failed attempt
if [ -d ".venv" ] && [ ! -f ".venv/bin/pip" ]; then
  echo "      → Found broken .venv (no pip inside), removing it..."
  rm -rf .venv
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Verify venv actually has pip before proceeding — fail loudly and
# clearly instead of the confusing ".venv/bin/pip: not found" error
if [ ! -f ".venv/bin/pip" ]; then
  echo "      ✗ venv creation failed — pip not found inside .venv/bin/"
  echo "        Try manually: python3 -m venv .venv --clear"
  exit 1
fi
echo "      ✓ Virtual environment ready"

echo "[2/6] Installing backend dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "      ✓ Backend dependencies installed"

# Verify .env.production exists before relying on it
if [ ! -f "$BACKEND_DIR/.env.production" ]; then
  echo "      ✗ backend/.env.production not found."
  echo "        Create it first with DB credentials, ANTHROPIC_API_KEY, etc."
  exit 1
fi
echo "      ✓ backend/.env.production found"

# ── 3. Build frontend ─────────────────────────────────────────
echo ""
echo "[3/6] Building frontend..."
cd "$FRONTEND_DIR"

if [ ! -f ".env.production" ]; then
  echo "      ✗ frontend/.env.production not found."
  echo "        Create it with: VITE_API_BASE_URL=https://insights.vtrader.in/api"
  exit 1
fi

npm install --silent
cp .env.production .env
npm run build

if [ ! -f "dist/index.html" ]; then
  echo "      ✗ Build failed — dist/index.html not found"
  exit 1
fi
echo "      ✓ Frontend built → dist/"

# ── 4. Install systemd service ────────────────────────────────
echo ""
echo "[4/6] Installing systemd service..."
if [ ! -f "$PROJECT_DIR/vtrader-api.service" ]; then
  echo "      ✗ vtrader-api.service not found in $PROJECT_DIR"
  exit 1
fi
cp "$PROJECT_DIR/vtrader-api.service" /etc/systemd/system/vtrader-api.service
systemctl daemon-reload
systemctl enable vtrader-api
systemctl restart vtrader-api
sleep 3

if systemctl is-active --quiet vtrader-api; then
  echo "      ✓ vtrader-api service running"
else
  echo "      ✗ Service failed to start"
  echo "        Last 30 log lines:"
  journalctl -u vtrader-api -n 30 --no-pager
  exit 1
fi

# ── 5. Update nginx config ────────────────────────────────────
echo ""
echo "[5/6] Updating nginx config..."
if [ ! -f "$PROJECT_DIR/nginx-production.conf" ]; then
  echo "      ✗ nginx-production.conf not found in $PROJECT_DIR"
  exit 1
fi
cp "$PROJECT_DIR/nginx-production.conf" /etc/nginx/conf.d/insights.vtrader.in.conf

if ! nginx -t 2>&1; then
  echo "      ✗ nginx config test failed — check the error above"
  exit 1
fi
systemctl reload nginx
echo "      ✓ Nginx reloaded"

# ── 6. Health check ───────────────────────────────────────────
echo ""
echo "[6/6] Health check..."
sleep 2
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health)
if [ "$STATUS" = "200" ]; then
  echo "      ✓ Backend API responding — HTTP $STATUS"
else
  echo "      ✗ Backend health check failed (HTTP $STATUS)"
  echo "        Check: journalctl -u vtrader-api -n 30"
fi

FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://insights.vtrader.in)
if [ "$FRONTEND_STATUS" = "200" ]; then
  echo "      ✓ Frontend responding — HTTP $FRONTEND_STATUS"
else
  echo "      ⚠ Frontend check returned HTTP $FRONTEND_STATUS (may need DNS/SSL propagation time)"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Deployment complete!"
echo "  → https://insights.vtrader.in"
echo "  → API health: https://insights.vtrader.in/api/health"
echo "═══════════════════════════════════════════════"
echo ""