from __future__ import annotations
import random
import numpy as np
import pandas as pd
from faker import Faker
from silkroute.config import Config

def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)

def gen_channels() -> pd.DataFrame:
    return pd.DataFrame([
        {"channel_type": "store", "channel_name": "SilkRoute (Brick-and-Mortar)"},
        {"channel_type": "online", "channel_name": "SilkRoute Online (Pakistan-only Ecommerce)"},
    ])

def gen_stores(cfg: Config, fake: Faker) -> pd.DataFrame:
    if cfg.cities is None:
        cfg.cities = [("Karachi", "Sindh"), ("Lahore", "Punjab"), ("Islamabad", "ICT")]
    store_types = ["mall", "high_street", "flagship"]
    rows = []
    for i in range(cfg.n_stores):
        city, region = cfg.cities[i % len(cfg.cities)]
        rows.append({
            "store_id": f"S{i+1:03d}",
            "store_name": f"SilkRoute {city} {i%3+1}",
            "city": city,
            "region": region,
            "store_type": random.choice(store_types),
        })
    return pd.DataFrame(rows)

def gen_salespeople(cfg: Config, fake: Faker, stores: pd.DataFrame):
    roles = ["sales_associate", "senior_associate", "floor_supervisor"]
    store_ids = stores["store_id"].tolist()
    rows = []
    for i in range(cfg.n_salespeople):
        rows.append({
            "salesperson_id": f"P{i+1:04d}",
            "name": fake.name(),
            "role": random.choice(roles),
            "store_id": random.choice(store_ids),
        })
    df = pd.DataFrame(rows)

    top_salespeople = set(df.sample(cfg.top_salespeople_count, random_state=cfg.seed)["salesperson_id"].tolist())
    remaining = df[~df["salesperson_id"].isin(top_salespeople)]
    discount_heavy_salespeople = set(
        remaining.sample(max(2, cfg.top_salespeople_count), random_state=cfg.seed+1)["salesperson_id"].tolist()
    )

    return df, {
        "top_salespeople": sorted(list(top_salespeople)),
        "discount_heavy_salespeople": sorted(list(discount_heavy_salespeople)),
    }

def gen_customers(cfg: Config, fake: Faker):
    segments = ["loyal", "price_sensitive", "one_time", "high_return", "regular"]
    probs = np.array([0.14, 0.20, 0.22, 0.10, 0.34]); probs = probs / probs.sum()

    if cfg.cities is None:
        cfg.cities = [("Karachi", "Sindh"), ("Lahore", "Punjab"), ("Islamabad", "ICT")]

    start = pd.to_datetime(cfg.start_date)
    end = pd.to_datetime(cfg.end_date)
    days = (end - start).days

    rows = []
    for i in range(cfg.n_customers):
        city, region = random.choice(cfg.cities)
        seg = np.random.choice(segments, p=probs)
        fp = start + pd.to_timedelta(np.random.randint(0, days+1), unit="D")
        rows.append({
            "customer_id": f"C{i+1:05d}",
            "segment": seg,
            "city": city,
            "region": region,
            "first_purchase_date": fp.date().isoformat(),
        })
    df = pd.DataFrame(rows)
    return df, {
        "loyal_customers": df[df["segment"] == "loyal"]["customer_id"].tolist(),
        "high_return_customers": df[df["segment"] == "high_return"]["customer_id"].tolist(),
    }
