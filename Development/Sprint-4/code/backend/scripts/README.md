# Backend Scripts

## Data Placement

Use one of these input setups:

1. Extracted CSVs (preferred):
- Place gold files in `Development/Sprint-3/code/backend/data/gold_csv/`
- Expected files:
  - `gold_sales_daily.csv`
  - `gold_store_sku_daily.csv`
  - `gold_store_360.csv`
  - `gold_product_360.csv`
  - `gold_customer_360.csv`
  - `gold_employee_360.csv`
  - `gold_inventory_health_daily.csv`

2. Zip input:
- Place zip at `Development/Sprint-3/code/backend/data/cont_csvs.zip`
- If `gold_csv/` is missing or empty, `load_gold_marts.py` will extract gold CSVs there before loading.

## Set DATABASE_URL

PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME"
```

Bash:

```bash
export DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME"
```

## Run Loader

```bash
python Development/Sprint-3/code/backend/scripts/load_gold_marts.py
```

## Full Refresh Behavior

`load_gold_marts.py` always loads each CSV into `gold.<table_name>` using:
- `if_exists="replace"`
- chunked multi-row inserts (`chunksize`, `method="multi"`)

No incremental logic is used.

## Minimal Alert Scheduler (Windows)

Use `setup_minimal_alert_scheduler.ps1` to register a recurring Windows Task Scheduler job.
The scheduled job runs `run_minimal_alert.py` without `--force`, so an email is sent only when a KPI/rule transitions into `critical`.

Internally, the task executes `run_minimal_alert_scheduled.ps1`, which calls the Python runner from backend root.

### Create/Update Task

```powershell
Set-Location Development/Sprint-4/code/backend
powershell -ExecutionPolicy Bypass -File scripts/setup_minimal_alert_scheduler.ps1 -DatasetId silkroute -EveryMinutes 60
```

### Verify Task

```powershell
schtasks /Query /TN ContinuumAI-MinimalAlert-silkroute /FO LIST /V
```

### Remove Task

```powershell
schtasks /Delete /TN ContinuumAI-MinimalAlert-silkroute /F
```

## Minimal Alert Event Hook (No Core Code Changes)

Use this script at your strategy recompute completion point (pipeline/job step). It runs alert checks in non-force mode and appends monitor logs.

```powershell
Set-Location Development/Sprint-4/code/backend
python scripts/run_minimal_alert_event_hook.py --dataset-id silkroute --source strategy_recompute
```

Monitor log path (JSONL): `out/alerts_monitor.jsonl`

Logged fields include:
- `alert_triggered`
- `email_sent`
- `reason`
- `transition_count`
- `revision`
- `generated_at`

## Minimal Alert Daily Backup Scheduler (Windows)

Create a daily fallback task (recommended with event-hook primary):

```powershell
Set-Location Development/Sprint-4/code/backend
powershell -ExecutionPolicy Bypass -File scripts/setup_minimal_alert_backup_daily.ps1 -DatasetId silkroute -Time 09:00
```
