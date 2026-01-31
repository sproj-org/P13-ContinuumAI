from __future__ import annotations
import os, json
import pandas as pd

def ensure_outdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def save_tables(outdir: str, tables: dict[str, pd.DataFrame]) -> None:
    ensure_outdir(outdir)
    for name, df in tables.items():
        df.to_parquet(os.path.join(outdir, f"{name}.parquet"), index=False)
        df.to_csv(os.path.join(outdir, f"{name}.csv"), index=False)

def save_manifest(outdir: str, manifest: dict) -> None:
    ensure_outdir(outdir)
    with open(os.path.join(outdir, "seed_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
