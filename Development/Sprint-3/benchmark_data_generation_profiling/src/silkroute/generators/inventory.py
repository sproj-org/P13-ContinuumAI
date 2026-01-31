from __future__ import annotations
import random
import numpy as np
import pandas as pd
from silkroute.config import Config

def gen_inventory_snapshots(cfg: Config, stores: pd.DataFrame, skus: pd.DataFrame, tx: pd.DataFrame, lines: pd.DataFrame, pattern_sets: dict):
    start = pd.to_datetime(cfg.start_date)
    end = pd.to_datetime(cfg.end_date)
    snap_dates = pd.date_range(start, end, freq=f"{cfg.inventory_snapshot_freq_days}D")

    hero_skus = set(pattern_sets["hero_skus"])
    store_ids = stores["store_id"].tolist()
    dc_id = "S000"
    locs = store_ids + [dc_id]

    inv = {}
    for loc in locs:
        for sku in skus["sku_id"].tolist():
            if sku in hero_skus:
                stock = int(np.random.randint(5,25)) if loc!=dc_id else int(np.random.randint(20,60))
            else:
                stock = int(np.random.randint(10,60)) if loc!=dc_id else int(np.random.randint(30,120))
            inv[(loc,sku)] = stock

    tx2 = tx.copy()
    tx2["transaction_ts"] = pd.to_datetime(tx2["transaction_ts"])
    tx2["inv_loc"] = np.where(tx2["channel_type"]=="online", dc_id, tx2["store_id"])

    lines2 = lines.merge(tx2[["transaction_id","transaction_ts","inv_loc"]], on="transaction_id", how="left")
    lines2["transaction_ts"] = pd.to_datetime(lines2["transaction_ts"])

    out = []
    for d in snap_dates:
        window_start = d - pd.to_timedelta(cfg.inventory_snapshot_freq_days, unit="D")
        sold = lines2[(lines2["transaction_ts"] > window_start) & (lines2["transaction_ts"] <= d)].copy()
        agg = sold.groupby(["inv_loc","sku_id"])["quantity"].sum().reset_index()
        for _, r in agg.iterrows():
            key = (r["inv_loc"], r["sku_id"])
            inv[key] = max(0, inv.get(key,0) - int(r["quantity"]))

        for loc in locs:
            for sku in skus["sku_id"].tolist():
                key = (loc, sku)
                soh = inv[key]
                reorder_point = 8 if sku in hero_skus else 12
                order_qty = 18 if sku in hero_skus else 28

                lead_time_factor = 0.65 if (sku in hero_skus and d.month in [10,11,12]) else 1.0
                if soh < reorder_point and random.random() < lead_time_factor:
                    on_order = order_qty
                    if random.random() < 0.25:
                        inv[key] += int(order_qty * 0.5)
                        on_order = int(order_qty * 0.5)
                else:
                    on_order = int(np.random.choice([0,0,0,10], p=[0.6,0.2,0.1,0.1]))

                out.append({
                    "snapshot_date": d.date().isoformat(),
                    "store_id": loc,
                    "sku_id": sku,
                    "stock_on_hand": int(inv[key]),
                    "stock_on_order": int(on_order),
                })
    return pd.DataFrame(out)
