# SalesSight Lite

**Sales KPI Dashboard with Forecasting and AI Insights**

SalesSight Lite is a beginner-friendly college project. Upload order-line CSV data to calculate sales KPIs, explore charts, forecast the next seven days with scikit-learn Linear Regression, and optionally request one plain-text Gemini explanation.

The bundled `sample_sales.csv` is **synthetic demo data** generated with a fixed random seed. It contains 120 consecutive calendar days, several products, multiple orders per day, realistic variation, and a mild upward order-volume trend. No API key is needed for the demo dashboard or forecast.

## Quick start for new users

These instructions are for Windows PowerShell. Install [Git](https://git-scm.com/download/win), [Python 3.11](https://www.python.org/downloads/), and [Node.js 20+](https://nodejs.org/) first.

1. Clone the repository and enter it:

   ```powershell
   git clone https://github.com/abhineeth27/SalesSight-Lite.git
   cd SalesSight-Lite
   ```

2. Start the backend in the first PowerShell window:

   ```powershell
   cd backend
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   uvicorn main:app --reload
   ```

3. Start the frontend in a second PowerShell window:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open <http://localhost:5173> and click **Load Demo Data**. KPIs, charts, and forecasting work without an API key.

5. To enable **Generate AI Insights**, follow the [Google AI Studio Free Tier setup](#google-ai-studio-free-tier-setup), save `backend/.env`, and restart FastAPI.

## How to use the app

1. Click **Load Demo Data** for an immediate tour, or **Download Sample CSV** to inspect the expected format.
2. To analyze your own data, prepare a UTF-8 CSV with `date, order_id, product, quantity, unit_price`, then click **Upload CSV**.
3. Review the four KPI cards, daily revenue chart, top-five products, and the seven-day Basic trend forecast.
4. Read the holdout MAE and mean-baseline comparison. Lower MAE is better; this is an educational trend estimate, not a guarantee.
5. If Gemini is configured, click **Generate AI Insights** once. The response is reused until a different dataset is loaded.

The app does not upload the complete CSV to Gemini. Only a compact server-calculated summary is sent when the button is clicked.

## Features

- Backend-validated CSV upload (CSV only, maximum 5 MB)
- Four Python-calculated KPIs: revenue, unique orders, average order value, and units sold
- Daily revenue and top-five product charts
- Seven-day Linear Regression trend forecast with chronological holdout MAE and a mean baseline
- Missing dates filled with zero revenue
- Optional, click-only Gemini explanation based on a compact trusted summary
- Expiring bounded in-memory analysis/insight cache; no database
- Responsive React UI with loading, empty, success, validation, forecast, and AI error states
- Protection against stale upload and insight responses

## Project structure

```text
SalesSight-Lite/
├── backend/
│   ├── main.py              FastAPI routes
│   ├── analysis.py          validation, KPIs, charts, forecast, compact summary
│   ├── cache.py             bounded process-local TTL/LRU cache
│   ├── llm.py               one optional Gemini request
│   ├── schemas.py           request/response models
│   ├── tests/test_api.py    API and validation tests
│   ├── .env.example
│   └── requirements*.txt
├── frontend/
│   ├── public/sample_sales.csv
│   ├── src/App.jsx
│   ├── src/styles.css
│   └── vite.config.js       /api development proxy
└── scripts/generate_demo_data.py
```

## Requirements

- Windows 10/11 and PowerShell
- Python 3.11 (3.10+ should also work with the pinned packages)
- Node.js 20 or newer
- A Google AI Studio Free Tier key only if you want AI insights

## Run locally on Windows

Open PowerShell in the project folder. Start the backend in the first terminal:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload
```

`--reload` uses one server process for local development. If you run without reload, use exactly one worker because the cache is in memory:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

In a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite development server sends relative `/api` requests to FastAPI at `127.0.0.1:8000`; the Gemini key is never present in React.

Quick checks:

```powershell
# Backend terminal, with the virtual environment active
Invoke-RestMethod http://127.0.0.1:8000/health

# Frontend terminal
npm run build
```

API documentation is available at <http://127.0.0.1:8000/docs>.

## Google AI Studio Free Tier setup

The default is `gemini-3.1-flash-lite`. On **2026-11-05**, Google's official model page listed this exact ID as a stable, text-output-capable model, and the official pricing page listed its Standard Free Tier input and output as free of charge. Availability and quotas can change, so verify them when you create the key:

1. Open the [Google AI Studio API keys page](https://aistudio.google.com/app/apikey) and sign in.
2. Create or select a project, then choose **Create API key**. New accounts normally begin on the Free Tier.
3. In AI Studio's API keys/projects view, confirm that the selected project shows **Free** under its plan or billing tier. Do **not** click **Set up billing**, link a Cloud Billing account, or add a payment method for this project if you want to keep it free-only.
4. Copy `backend/.env.example` to `backend/.env` and replace only the placeholder:

   ```dotenv
   GEMINI_API_KEY=your_real_key_here
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```

5. Restart FastAPI, load a dataset, and click **Generate AI Insights** once.

Official references: [Gemini models](https://ai.google.dev/gemini-api/docs/models), [Gemini 3.1 Flash-Lite model](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing), [billing and tiers](https://ai.google.dev/gemini-api/docs/billing), and [API key quickstart](https://ai.google.dev/gemini-api/docs/api-key).

Important limits:

- Free-tier eligibility, supported regions, model access, and request quotas vary by account/project and can change.
- An API key does not reveal its project's billing status to this app, so SalesSight Lite **cannot verify** whether a key is Free Tier or paid.
- The app never enables billing, switches models/providers, or uses a paid fallback. If the configured model is unavailable or quota-limited, it shows a clear error and leaves the dashboard working.
- Free-tier prompts/responses may be used by Google to improve its products; check the current terms before sending data. This project sends only the compact summary described below.

## CSV format and validation

Required header:

```csv
date,order_id,product,quantity,unit_price
2026-01-01,ORD-10001,Wireless Mouse,2,899.00
```

Rules:

- `date`: real date written exactly as `YYYY-MM-DD`
- `order_id`: nonempty string; leading zeroes are preserved
- `product`: nonempty string
- `quantity`: positive integer
- `unit_price`: finite number greater than or equal to zero
- all lines sharing an `order_id` must share the same date
- extra columns are ignored
- duplicate/identical lines are retained because they may be legitimate

Invalid data is rejected with the rule and up to five example CSV row numbers. The backend does not silently clean invalid rows.

To recreate the synthetic sample exactly:

```powershell
python scripts\generate_demo_data.py
```

## Calculations and forecast

- Row revenue = `quantity × unit_price`
- Total revenue = sum of row revenue
- Total orders = unique order IDs
- Average order value = total revenue / total orders (or zero if there are no orders)
- Units sold = sum of quantity

Revenue is aggregated by calendar day. Missing dates from the first through last observed date are explicitly filled with zero. Forecasting requires at least 30 calendar days.

For evaluation, the last seven historical days are held out. Linear Regression is trained on elapsed day number for the earlier period and evaluated with MAE on those seven days. A simple baseline predicts the training period's mean revenue. Lower MAE is better. The model is then refit on all history and predicts the seven days immediately after the dataset's last date; negative values are clamped to zero.

This is a **Basic trend forecast**. It does not model seasonality, holidays, promotions, or external factors. The app does not show invented confidence intervals, accuracy percentages, or reliability claims.

## AI privacy and behavior

The LLM explains results only. One request is made only when the user clicks the button. Repeat clicks are disabled while loading, and a successful result is reused until new data is loaded.

Gemini receives only:

- date range
- already-calculated KPIs
- top products and revenue
- recent seven-day revenue versus the prior seven days (when available)
- forecast total and evaluation metrics (when available)

It never receives the complete CSV, order IDs, arbitrary client KPI values, or the API key. The key stays in `backend/.env`, which is gitignored. AI output is rendered as plain text, never raw HTML. Missing/invalid keys, model eligibility, rate limits, timeouts, and expired analysis IDs return user-friendly errors while all non-AI features keep working.

## API

- `GET /health` → `{ "status": "ok" }`
- `POST /analyze` → multipart field `file`; returns analysis ID, validated KPIs, chart data, and forecast/evaluation
- `POST /insights` → `{ "analysis_id": "..." }`; uses only the matching server-cached summary

The cache defaults to 100 analyses and a 30-minute TTL. A restart clears it. Because it is process-local, run one FastAPI worker. Configure limits with `ANALYSIS_CACHE_MAX_ITEMS` and `ANALYSIS_CACHE_TTL_SECONDS`.

## Tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests cover health, KPI math, missing-day filling, short-history behavior, seven-day forecasting, next-date selection, validation row examples, cross-date order rejection, file type rejection, missing AI configuration, and expired/unknown analyses.

## Troubleshooting

- **PowerShell blocks virtual-environment activation:** run `Set-ExecutionPolicy -Scope Process Bypass`, then activate `.venv` again. This changes policy only for the current terminal.
- **`py` is not recognized:** reinstall Python and enable **Add Python to PATH**, or use `python -m venv .venv`.
- **`npm` is not recognized:** install the current Node.js LTS release and reopen PowerShell.
- **Port 8000 or 5173 is busy:** stop the previous backend/frontend process with `Ctrl+C`, then retry.
- **AI says it is not configured:** verify `backend/.env` exists, contains `GEMINI_API_KEY`, and restart FastAPI.
- **Gemini key, eligibility, or quota error:** check the project plan and quota in Google AI Studio. The app never switches to a paid model or provider automatically.
- **Analysis expired:** upload the CSV again. The cache is intentionally in memory and is cleared on backend restart.

## Pinned dependency versions

Backend: FastAPI 0.115.6, Uvicorn 0.34.0, python-multipart 0.0.20, Pandas 2.2.3, scikit-learn 1.6.1, google-genai 1.11.0, python-dotenv 1.0.1. Test-only: pytest 8.3.4 and HTTPX 0.28.1.

Frontend: React 19.3.1, React DOM 19.3.1, Vite 8.3.6, `@vitejs/plugin-react` 6.2.1, and Recharts 3.10.1.

