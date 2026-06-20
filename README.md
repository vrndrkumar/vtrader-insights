# Signal Desk — Swing Trade Analysis System

Real-time stock analysis dashboard backed by your MySQL `stock_mstr` table.  
Analysis runs **only when you click a button** — never automatically.

---

## Architecture

```
MySQL (knowingly_trade.stock_mstr)
        ↓  reads active stocks
FastAPI Backend  ──→  Claude API (web search on)  ──→  Qualitative research
        ↓              ──→  Market data provider        Fundamental / Sector / LLM
        ↓              ──→  Pandas technical engine     RSI / SMA / Structure / Score
        ↓  writes stock_analysis_reports
React Frontend (Vite + Tailwind v4)
```

---

## Quick Start

### 1. Clone / copy this project to your server

```bash
git clone <your-repo> signal-desk
cd signal-desk
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, confirm DB creds, choose MARKET_DATA_PROVIDER
nano .env

# Start the API (port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On first startup, three new tables are auto-created in `knowingly_trade`:
- `stock_analysis_reports` — one row per analysis run per stock
- `market_overview` — rolling market snapshots
- `analysis_jobs` — batch job tracking

`stock_mstr` is **never modified** by this system.

### 3. Frontend

```bash
cd frontend
cp .env.example .env
# Set VITE_API_BASE_URL to where your backend is, e.g.:
# VITE_API_BASE_URL=http://YOUR_SERVER_IP:8000/api
nano .env

npm install
npm run dev          # development (hot-reload)
# OR
npm run build        # production build -> dist/
```

Serve `dist/` with Nginx, Caddy, or `npx serve dist`.

---

## Configuration Reference

| Variable | Default | Purpose |
|---|---|---|
| `DB_HOST` | 127.0.0.1 | MySQL server |
| `DB_USER` | root | MySQL user |
| `DB_PASSWORD` | — | MySQL password |
| `DB_NAME` | knowingly_trade | Database name |
| `ANTHROPIC_API_KEY` | — | **Required for LLM analysis** |
| `MARKET_DATA_PROVIDER` | mock | `mock` / `fyers` / `yfinance` |
| `FYERS_APP_ID` | — | Fyers app id (if provider=fyers) |
| `FYERS_ACCESS_TOKEN` | — | Fyers token (if provider=fyers) |
| `REPORT_FRESHNESS_MINUTES` | 240 | Age at which UI shows "Re-analyze" |
| `BATCH_CONCURRENCY` | 3 | Parallel stocks during Analyze All |
| `CLAUDE_ENABLE_WEB_SEARCH` | true | Let Claude search for current data |

---

## Market Data Providers

| Provider | What it does | When to use |
|---|---|---|
| `mock` | Deterministic synthetic OHLCV seeded per symbol | Demo / dev / no API keys |
| `fyers` | Fyers v3 REST API using `token_id` from `stock_mstr` | You already use Fyers |
| `yfinance` | Yahoo Finance (symbol.NS / symbol.BO) | Quick live prices, no auth needed |

**Tip**: Start with `mock` to verify the full UI flow end-to-end, then switch to `yfinance` for real prices without any setup, and finally `fyers` for production.

---

## How Analysis Works (the "click model")

### Single stock
1. User opens `/stock/SKIPPER` — page shows last cached report or "Not yet analyzed".
2. User clicks **Analyze Now** → `POST /api/analyze/SKIPPER`.
3. Backend: fetches OHLCV history → computes 10+ technical indicators → calls Claude with web search (fundamentals, sector, recent results, analyst views) → scores and persists.
4. Fresh report returned and rendered immediately (~20–60s per stock).

### Selected stocks
1. User checks checkboxes in the stock table.
2. Clicks **Analyze Selected** in the floating bar → `POST /api/analyze/batch` with symbol list.
3. Job runs in background; frontend polls progress every 2.5s.

### Analyze All
1. Click **Analyze All** in the top-right header.
2. Same batch endpoint, no symbol list = all active stocks in `stock_mstr`.
3. Progress shown inline in the button.

---

## Scoring Formula

```
Final Score = 25% Fundamental + 40% Technical + 20% Sector + 15% Momentum

Verdict thresholds:
  ≥ 78 + no red flags + R:R ≥ 2   → Strong Buy
  ≥ 65 + R:R ≥ 2                  → Buy
  ≥ 50                             → Watchlist
  < 50                             → Avoid
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/stocks` | List/search stocks with latest verdict |
| `GET` | `/api/stocks/{symbol_code}` | Latest report for one stock |
| `POST` | `/api/analyze/{symbol_code}` | **Run analysis now** (single) |
| `POST` | `/api/analyze/batch` | Start batch job (selected or all) |
| `GET` | `/api/jobs/{id}` | Job progress |
| `GET` | `/api/jobs` | Recent jobs |
| `GET` | `/api/dashboard` | Aggregated dashboard data |
| `POST` | `/api/dashboard/refresh-market-overview` | Refresh market overview via Claude |

Full interactive docs at `http://localhost:8000/docs` (Swagger).

---

## Production Deployment (systemd + Nginx)

### Backend service (`/etc/systemd/system/signal-desk-api.service`)

```ini
[Unit]
Description=Signal Desk FastAPI
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/signal-desk/backend
EnvironmentFile=/opt/signal-desk/backend/.env
ExecStart=/opt/signal-desk/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx (`/etc/nginx/sites-available/signal-desk`)

```nginx
server {
    listen 80;
    server_name your.domain.com;

    # Frontend (built files)
    root /opt/signal-desk/frontend/dist;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_read_timeout 120s;  # LLM calls can take up to 60s
    }
}
```

---

## File Structure

```
signal-desk/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app + startup
│   │   ├── config.py            Settings (env vars)
│   │   ├── database.py          SQLAlchemy models + session
│   │   ├── schemas.py           Pydantic request/response models
│   │   ├── market_data.py       Mock / Fyers / yfinance providers
│   │   ├── serializers.py       DB → Pydantic conversion
│   │   ├── jobs.py              Batch analysis background runner
│   │   ├── analysis/
│   │   │   ├── technical.py     OHLCV → indicators + trade setup
│   │   │   ├── llm_engine.py    Claude prompts + web search
│   │   │   ├── scoring.py       Weighted score + verdict logic
│   │   │   └── orchestrator.py  Full pipeline + DB persistence
│   │   └── routers/
│   │       ├── stocks.py        GET /stocks, GET /stocks/{code}
│   │       ├── analysis.py      POST /analyze/*, GET /jobs/*
│   │       └── dashboard.py     GET /dashboard
│   ├── sql/001_create_tables.sql  Optional manual migration
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── lib/
    │   │   ├── api.js           Axios client
    │   │   ├── format.js        ₹ / % / date formatters
    │   │   └── JobContext.jsx   Batch job polling state
    │   ├── components/
    │   │   ├── Layout.jsx       Top bar + nav + Analyze All
    │   │   ├── SearchBar.jsx    Live stock search dropdown
    │   │   ├── ConvictionMeter.jsx  Signature score visualizer
    │   │   ├── VerdictBadge.jsx
    │   │   ├── MarketOverviewCard.jsx
    │   │   ├── TopPickCard.jsx
    │   │   ├── StockTable.jsx   Sortable table with per-row Analyze
    │   │   ├── FilterBar.jsx
    │   │   ├── SelectionBar.jsx Floating bar for selected stocks
    │   │   ├── SectorStrengthChart.jsx
    │   │   ├── VerdictDistribution.jsx
    │   │   ├── PriceLevelLadder.jsx  Visual stop/entry/target track
    │   │   └── ui.jsx           Card, Tabs, BulletList, StatItem, Pill
    │   ├── pages/
    │   │   ├── Dashboard.jsx    Main dashboard
    │   │   ├── StockReport.jsx  Individual stock (swing + long-term)
    │   │   └── FullReport.jsx   Printable full screening report
    │   ├── App.jsx              Routes
    │   ├── main.jsx
    │   └── index.css            Tailwind v4 + design tokens
    ├── .env.example
    └── package.json
```
