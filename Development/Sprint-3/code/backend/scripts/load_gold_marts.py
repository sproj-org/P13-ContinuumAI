"""Load gold CSV marts into Postgres schema `gold` using full refresh."""

from __future__ import annotations

import os
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath

import pandas as pd
from sqlalchemy import Text, create_engine, text
from sqlalchemy.engine import Engine

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
GOLD_CSV_DIR = DATA_DIR / "gold_csv"
ZIP_PATH = DATA_DIR / "cont_csvs.zip"
VENDOR_CONT_CSVS_DIR = BASE_DIR / "vendor" / "cont_csvs"
TARGET_SCHEMA = "gold"
INSERT_CHUNKSIZE = 2000

DATETIME_TOKENS = ("date", "_date", "_ts", "timestamp", "datetime", "_at")


def is_identifier_like(column_name: str) -> bool:
    name = column_name.strip().lower()
    return (
        name == "id"
        or name.endswith("_id")
        or name == "code"
        or name.endswith("_code")
        or name.endswith("_key")
    )


def is_datetime_like(column_name: str) -> bool:
    name = column_name.strip().lower()
    return any(token in name for token in DATETIME_TOKENS)


def _is_junk_zip_path(path: PurePosixPath) -> bool:
    junk_parts = {"__MACOSX", "__pycache__"}
    if path.name == ".DS_Store":
        return True
    return any(part in junk_parts for part in path.parts)


def _strip_cont_csvs_prefix(path: PurePosixPath) -> PurePosixPath:
    parts = list(path.parts)
    if parts and parts[0].lower() == "cont_csvs":
        parts = parts[1:]
    if not parts:
        return PurePosixPath(path.name)
    return PurePosixPath(*parts)


def extract_zip_for_provenance_and_data(zip_path: Path) -> None:
    VENDOR_CONT_CSVS_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_CSV_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = PurePosixPath(member.filename)
            if member.is_dir() or _is_junk_zip_path(member_path):
                continue

            normalized_path = _strip_cont_csvs_prefix(member_path)
            vendor_target = VENDOR_CONT_CSVS_DIR / Path(*normalized_path.parts)
            vendor_target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, vendor_target.open("wb") as dst:
                shutil.copyfileobj(src, dst)

            if vendor_target.suffix.lower() == ".csv" and vendor_target.name.startswith("gold_"):
                shutil.copyfile(vendor_target, GOLD_CSV_DIR / vendor_target.name)


def ensure_gold_csv_inputs() -> list[Path]:
    GOLD_CSV_DIR.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(GOLD_CSV_DIR.glob("*.csv"))
    if csv_files:
        return csv_files

    if ZIP_PATH.exists():
        print(
            f"[INFO] {GOLD_CSV_DIR} is empty. Extracting gold CSVs from {ZIP_PATH}..."
        )
        extract_zip_for_provenance_and_data(ZIP_PATH)
        csv_files = sorted(GOLD_CSV_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {GOLD_CSV_DIR}. "
            f"Place extracted gold CSVs there, or add {ZIP_PATH}."
        )

    return csv_files


def normalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Text]]:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    df.replace(r"^\s*$", pd.NA, regex=True, inplace=True)

    text_dtypes: dict[str, Text] = {}

    for column in df.columns:
        col_name = str(column)
        if is_identifier_like(col_name):
            df[column] = df[column].astype("string")
            text_dtypes[col_name] = Text()
            continue

        if is_datetime_like(col_name):
            df[column] = pd.to_datetime(df[column], errors="coerce")
            continue

        if pd.api.types.is_numeric_dtype(df[column]) or pd.api.types.is_datetime64_any_dtype(
            df[column]
        ):
            continue

        numeric_series = pd.to_numeric(df[column], errors="coerce")
        non_null_input = int(df[column].notna().sum())
        non_null_numeric = int(numeric_series.notna().sum())

        if non_null_input > 0 and non_null_numeric > 0:
            parsed_ratio = non_null_numeric / non_null_input
            if parsed_ratio >= 0.8:
                df[column] = numeric_series

    return df, text_dtypes


def load_csv_to_table(engine: Engine, csv_path: Path) -> None:
    table_name = csv_path.stem
    started = time.perf_counter()

    df = pd.read_csv(csv_path, low_memory=False)
    normalized_df, dtype_map = normalize_dataframe(df)
    row_count = len(normalized_df.index)

    normalized_df.to_sql(
        name=table_name,
        con=engine,
        schema=TARGET_SCHEMA,
        if_exists="replace",
        index=False,
        chunksize=INSERT_CHUNKSIZE,
        method="multi",
        dtype=dtype_map or None,
    )

    duration = time.perf_counter() - started
    print(
        f"[OK] schema={TARGET_SCHEMA} table={table_name} rows={row_count} duration={duration:.2f}s"
    )


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is required.")
        return 1

    try:
        csv_files = ensure_gold_csv_inputs()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    try:
        engine = create_engine(database_url)
    except Exception as exc:
        print(f"[ERROR] Failed to create database engine: {exc}")
        return 1

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TARGET_SCHEMA}"'))

        for csv_file in csv_files:
            load_csv_to_table(engine, csv_file)
    except Exception as exc:
        print(f"[ERROR] Failed loading gold marts: {exc}")
        return 1
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
