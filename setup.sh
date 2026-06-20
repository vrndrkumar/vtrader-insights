#!/usr/bin/env bash
# setup.sh — run once after cloning to prepare both backend and frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=== Signal Desk — Setup ==="
echo ""

# ---- Backend -------------------------------------------------------
echo "[1/4] Setting up Python backend..."
cd backend
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt -q
deactivate

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "  ✓ Created backend/.env from .env.example"
  echo "  → Edit backend/.env and set ANTHROPIC_API_KEY before running."
else
  echo "  ✓ backend/.env already exists, skipping."
fi
cd ..

# ---- Frontend ------------------------------------------------------
echo ""
echo "[2/4] Installing frontend dependencies..."
cd frontend
npm install --silent
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  ✓ Created frontend/.env from .env.example"
  echo "  → Set VITE_API_BASE_URL if your backend is not on localhost:8000"
else
  echo "  ✓ frontend/.env already exists, skipping."
fi
cd ..

# ---- SQL migration note -------------------------------------------
echo ""
echo "[3/4] Database tables will be created automatically on first API startup."
echo "  (stock_mstr is read-only — three new tables are added beside it.)"
echo "  Optional: run backend/sql/001_create_tables.sql manually if you prefer."

# ---- Done ----------------------------------------------------------
echo ""
echo "[4/4] Done! Start the system with two terminals:"
echo ""
echo "  # Terminal 1 — Backend API"
echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo ""
echo "  # Terminal 2 — Frontend dev server"
echo "  cd frontend && npm run dev"
echo ""
echo "  Then open http://localhost:5173"
echo ""
