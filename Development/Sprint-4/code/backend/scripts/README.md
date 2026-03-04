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
