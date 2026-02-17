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

4. Verify generated profiles + hardcoded mart guard

```bash
python Development/Sprint-3/code/backend/scripts/verify_gold_profiles.py
```

5. Run backend API

```bash
cd Development/Sprint-3/code/backend
uvicorn app.main:app --reload
```

6. Run frontend

```bash
cd Development/Sprint-3/code/frontend
npm run dev
```

## Checklist

- `GET /api/profiling/aggregations` shows only `gold_*` marts from backend registry.
- Table profiling tab loads for selected gold marts.
- Column profiling tab loads and displays column stats.
- Chart builder queries/render come from DB data (no mock/random values).
- No legacy hardcoded mart ids remain in FE/BE code (legacy `backend/out/mart_*_profile.json` excluded).
