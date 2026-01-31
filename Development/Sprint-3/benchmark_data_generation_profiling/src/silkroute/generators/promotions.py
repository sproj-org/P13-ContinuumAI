from __future__ import annotations
import random
import numpy as np
import pandas as pd
from silkroute.config import Config

def gen_promotions(cfg: Config, products: pd.DataFrame) -> pd.DataFrame:
    promo_types = ["seasonal_sale", "flash_sale", "bundle_offer", "clearance"]
    discount_types = ["percent", "fixed"]

    n_promos = 12
    pr_ids = products["product_id"].tolist()
    start = pd.to_datetime(cfg.start_date)
    end = pd.to_datetime(cfg.end_date)
    total_days = (end - start).days

    rows = []
    for i in range(n_promos):
        p = random.choice(pr_ids)
        s = start + pd.to_timedelta(np.random.randint(0, total_days - 14), unit="D")
        e = s + pd.to_timedelta(np.random.randint(7, 21), unit="D")
        rows.append({
            "promo_id": f"PROMO{i+1:03d}",
            "product_id": p,
            "promo_type": random.choice(promo_types),
            "start_date": s.date().isoformat(),
            "end_date": min(e, end).date().isoformat(),
            "discount_type": random.choice(discount_types),
        })
    return pd.DataFrame(rows)
