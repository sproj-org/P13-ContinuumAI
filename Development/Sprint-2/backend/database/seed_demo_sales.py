"""
Seed the Railway MySQL instance with demo_sales.csv into DEMO_TABLE.
"""
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.types import String, Float, Integer, DateTime
from dotenv import load_dotenv
import os

load_dotenv()

def _normalize_url(url: str) -> str:
    # Ensure we use the PyMySQL driver when a generic mysql:// URL is provided
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+pymysql://", 1)
    return url

DATABASE_URL = _normalize_url(os.getenv("DATABASE_URL", "sqlite:///./vizro.db"))
TABLE = os.getenv("DEMO_TABLE", "sales_demo")
CSV_PATH = os.getenv("CSV_PATH", "database/data/demo_sales.csv")


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set")
    csv_path = Path(CSV_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found")

    df = pd.read_csv(csv_path)
    for col in ("order_date", "lead_date", "close_date", "first_purchase_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    dtype = {
        "order_id": String(64),
        "opportunity_id": String(64),
        "customer_id": String(64),
        "product_id": String(64),
        "product_name": String(255),
        "category": String(128),
        "salesperson": String(128),
        "region": String(128),
        "country": String(128),
        "city": String(128),
        "stage": String(128),
        "channel": String(128),
        "order_date": DateTime(),
        "lead_date": DateTime(),
        "close_date": DateTime(),
        "first_purchase_date": DateTime(),
        "revenue": Float(),
        "units": Float(),
        "is_returning": Integer(),
        "aov": Float(),
        "sales_cycle_days": Float(),
    }

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        df.to_sql(TABLE, conn, if_exists="replace", index=False, dtype=dtype)
    print(f"Seeded {len(df)} rows into {TABLE}")


if __name__ == "__main__":
    main()
