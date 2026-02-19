# Sprint-3 Runbook

This runbook covers the Sprint-3 backend flow for gold marts, profiling, and API contracts.

## 1) Environment Variables

Required:

- `DATABASE_URL`
- `JWT_SECRET_KEY`

Optional profiling/generation controls:

- `PROFILE_SAMPLE_ROWS` (default: `5000`)
- `PROFILE_STATEMENT_TIMEOUT_MS` (default: `30000`)
- `PROFILE_MAX_RETRIES` (default: `3`)

PowerShell example:

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/postgres"
$env:JWT_SECRET_KEY="your-secret-key"
```

## 2) Load Gold Tables (Full Refresh)

```powershell
python Development/Sprint-3/code/backend/scripts/load_gold_marts.py
```

Notes:

- Loader reads from `Development/Sprint-3/code/backend/data/gold_csv/`.
- If that folder is empty and `backend/data/cont_csvs.zip` exists, it extracts gold CSVs first.
- Load mode is full refresh (`if_exists="replace"`), no incremental logic.

## 3) Generate Gold Profiles (DB-only)

```powershell
python Development/Sprint-3/code/backend/scripts/generate_gold_profiles.py
```

Guarantees:

- Profiles are generated from DB tables only.
- No CSV fallback path is used.
- Per-table retry with fresh DB engine is applied.
- Output is written only to `backend/out/gold_*_profile.json`.
- Existing `backend/out/mart_*_profile.json` files are not overwritten.

## 4) Verify Profiles + Source Drift

```powershell
python Development/Sprint-3/code/backend/scripts/verify_gold_profiles.py
python Development/Sprint-3/code/backend/scripts/check_no_hardcoded_marts.py
```

## 5) Run Backend

```powershell
cd Development/Sprint-3/code/backend
uvicorn app.main:app --reload
```

## 6) Run API Contract Tests

With backend running locally:

```powershell
python Development/Sprint-3/code/backend/scripts/contract_test_legacy_endpoints.py
python Development/Sprint-3/code/backend/scripts/contract_test_dataset_endpoints.py
python Development/Sprint-3/code/backend/scripts/contract_test_chart_data_shape.py
```

Or one-command wrapper:

```powershell
python Development/Sprint-3/code/backend/scripts/smoke_api_local.py
```

## 7) Run Frontend Check

```powershell
cd Development/Sprint-3/code/frontend
npx tsc --noEmit
npm run dev
```

## 8) Routing/Aliasing Model

Primary Sprint-3 routes are dataset-scoped:

- `/api/datasets/{dataset_id}/profiling/...`
- `/api/datasets/{dataset_id}/query/aggregate`

Legacy routes are preserved as wrappers for `dataset_id="silkroute"`:

- `/api/profiling/aggregations`
- `/api/profiling/aggregations/{table_name}/profile`
- `/api/profiling/aggregations/{table_name}/columns/{column_name}`
- `/api/profiling/chart-data`

This keeps existing UI/client flows backward-compatible during migration.

