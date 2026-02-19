# Smoke Tests

## Commands

1. Set DB URL

```bash
export DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME"
```

PowerShell equivalent:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME"
```

2. Load gold marts (full refresh)

```bash
python Development/Sprint-3/code/backend/scripts/load_gold_marts.py
```

3. Generate gold profiles

```bash
python Development/Sprint-3/code/backend/scripts/generate_gold_profiles.py
```

4. Verify generated profiles

```bash
python Development/Sprint-3/code/backend/scripts/verify_gold_profiles.py
```

5. Verify no hardcoded mart constants remain in source

```bash
python Development/Sprint-3/code/backend/scripts/check_no_hardcoded_marts.py
```

6. Run backend API

```bash
cd Development/Sprint-3/code/backend
uvicorn app.main:app --reload
```

7. Run API smoke script (dataset route first, legacy fallback)

```bash
python Development/Sprint-3/code/backend/scripts/smoke_api_local.py --dataset-id silkroute
```

8. Run frontend

```bash
cd Development/Sprint-3/code/frontend
npm run dev
```

## Checklist (Manual)

- `GET /api/datasets/silkroute/profiling/aggregations` returns gold marts from backend registry.
- `GET /api/profiling/aggregations` still works as legacy alias.
- Table profiling tab loads for selected gold marts.
- Column profiling tab loads and displays column stats.
- Chart builder queries/render come from DB data (no mock/random values).
- `POST /api/datasets/silkroute/query/aggregate` returns `{columns, rows, meta}`.
- `POST /api/profiling/chart-data` still works and does not fail on inf/nan serialization.
- No legacy hardcoded marts/constants remain in FE/BE source (legacy `backend/out/mart_*_profile.json` excluded).
