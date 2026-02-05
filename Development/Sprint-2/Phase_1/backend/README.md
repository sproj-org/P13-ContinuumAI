# Continuum Vizro Backend (clean)

FastAPI service (defaults to SQLite for local dev) that exposes auth and a `/query` endpoint capable of returning any number of Plotly charts/KPIs generated from Vizro-like tool functions. Data is sourced from `sales_demo` (seeded from `demo_sales.csv`).

## Setup
```
cd Development/Sprint-2/backend
python -m venv .venv
.\\.venv\\Scripts\\Activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env   # update SECRET_KEY if needed
```

## Seed demo data (SQLite by default)
```
python database/seed_demo_sales.py
```

## Run server
```
uvicorn app.main:app --reload
```
API root: http://127.0.0.1:8000

## Endpoints
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET /filters` (distinct lists for dropdowns)
- `POST /query` -> returns `results` (Plotly chart objects) and `kpis` (text cards)

## Adding new Vizro-style tools
Create a function in `app/tools/` decorated with `@vizro_tool(...)`. It should accept a pandas DataFrame and filters, and return a Plotly Figure, a Plotly JSON dict, or a KPI dict `{type: "kpi", title, body}`. The registry auto-discovers tools and `/query` can run any subset via `tool_names`.
