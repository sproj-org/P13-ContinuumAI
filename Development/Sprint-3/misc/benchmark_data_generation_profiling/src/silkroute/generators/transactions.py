from __future__ import annotations
import random
import numpy as np
import pandas as pd
from silkroute.config import Config

def gen_transactions_and_lines(
    cfg: Config,
    customers: pd.DataFrame,
    stores: pd.DataFrame,
    salespeople: pd.DataFrame,
    products: pd.DataFrame,
    skus: pd.DataFrame,
    promos: pd.DataFrame,
    pattern_sets: dict,
    people_sets: dict,
    customer_sets: dict,
):
    start = pd.to_datetime(cfg.start_date)
    end = pd.to_datetime(cfg.end_date)
    days = pd.date_range(start, end, freq="D")

    store_ids = stores["store_id"].tolist()
    under_stores = set(random.sample(store_ids, cfg.underperforming_store_count))
    remaining_stores = [s for s in store_ids if s not in under_stores]
    discount_heavy_stores = set(random.sample(remaining_stores, cfg.discount_heavy_store_count))

    payment_store = ["cash", "card"]
    payment_online = ["card", "wallet", "cod"]

    hero_skus = set(pattern_sets["hero_skus"])

    sku_join = skus.merge(products[["product_id","category","subcategory"]], on="product_id", how="left")
    fashion_skus = sku_join[sku_join["category"]=="Fashion"]["sku_id"].tolist()
    elec_skus = sku_join[sku_join["category"]=="Electronics"]["sku_id"].tolist()
    addon_skus = sku_join[sku_join["category"]=="Attach & Addons"]["sku_id"].tolist()

    # promos active lookup
    promos2 = promos.copy()
    promos2["start_date"] = pd.to_datetime(promos2["start_date"])
    promos2["end_date"] = pd.to_datetime(promos2["end_date"])
    pr_promos = {}
    for _, r in promos2.iterrows():
        pr_promos.setdefault(r["product_id"], []).append(r)

    months = pd.period_range(start, end, freq="M")
    online_shares = np.linspace(cfg.online_share_start, cfg.online_share_end, len(months))
    online_share_by_month = {m: float(s) for m, s in zip(months, online_shares)}

    # tx per day with seasonality
    base_daily = cfg.n_transactions / len(days)
    daily_lambda = []
    for d in days:
        season = 1.25 if d.month in [11,12] else (1.10 if d.month in [3,4] else 1.0)
        weekend = 1.08 if d.weekday() in [4,5] else 1.0
        daily_lambda.append(base_daily * season * weekend)

    daily_counts = np.random.poisson(lam=daily_lambda)
    diff = cfg.n_transactions - daily_counts.sum()
    if diff != 0:
        idxs = np.random.choice(len(daily_counts), size=min(abs(diff), len(daily_counts)), replace=False)
        for idx in idxs:
            daily_counts[idx] = max(0, daily_counts[idx] + (1 if diff>0 else -1))

    # roll up to month totals
    daily_df = pd.DataFrame({"day": days, "n": daily_counts})
    daily_df["month"] = daily_df["day"].dt.to_period("M")
    month_counts = daily_df.groupby("month")["n"].sum().to_dict()

    # customer propensity
    seg_weight = {"loyal":2.2, "regular":1.0, "price_sensitive":1.2, "one_time":0.55, "high_return":1.1}
    cust_df = customers.copy()
    cust_weights = cust_df["segment"].map(seg_weight).fillna(1.0).to_numpy(float)
    cust_weights = cust_weights / cust_weights.sum()

    sp_by_store = salespeople.groupby("store_id")["salesperson_id"].apply(list).to_dict()
    top_salespeople = set(people_sets["top_salespeople"])
    discount_heavy_salespeople = set(people_sets["discount_heavy_salespeople"])

    base_price_map = skus.set_index("sku_id")["base_price"].to_dict()
    sku_to_product = skus.set_index("sku_id")["product_id"].to_dict()

    def discount_rate(channel, store_id, salesperson_id, customer_id, sku_id):
        base = 0.0
        seg = cust_df.loc[cust_df["customer_id"]==customer_id, "segment"].iloc[0]
        if seg == "price_sensitive": base += 0.06
        if seg == "loyal": base += 0.015
        if channel == "store":
            if store_id in discount_heavy_stores: base += 0.06
            if salesperson_id in discount_heavy_salespeople: base += 0.07
            if salesperson_id in top_salespeople: base -= 0.03
        else:
            base += 0.02
        if sku_id in hero_skus:
            base -= 0.02
        return float(np.clip(base + np.random.normal(0,0.01), 0.0, 0.25))

    def attach_prob(channel, salesperson_id, customer_id, primary_cat):
        p = 0.10 if channel=="online" else 0.14
        seg = cust_df.loc[cust_df["customer_id"]==customer_id, "segment"].iloc[0]
        if seg=="loyal": p += 0.10
        if seg=="one_time": p -= 0.05
        if salesperson_id in top_salespeople: p += 0.18
        if primary_cat=="Electronics": p += 0.15
        return float(np.clip(p, 0.02, 0.75))

    tx_rows = []
    line_rows = []
    tx_id = 1
    line_id = 1

    # ✅ Enforce online share by month
    for m in months:
        n_tx_m = int(month_counts.get(m, 0))
        target_share = online_share_by_month[m]
        online_tx_m = int(round(n_tx_m * target_share))
        store_tx_m = n_tx_m - online_tx_m

        # list of days in this month to sample timestamps
        days_m = daily_df[daily_df["month"]==m]["day"].tolist()
        if not days_m:
            continue

        def make_tx(channel: str):
            nonlocal tx_id, line_id
            tid = f"T{tx_id:07d}"; tx_id += 1
            day = random.choice(days_m)
            ts = day + pd.to_timedelta(np.random.randint(0, 24*60), unit="m")

            cust_id = np.random.choice(cust_df["customer_id"].values, p=cust_weights)

            store_id = None
            sp_id = None
            if channel == "store":
                weights = np.array([0.65 if s in under_stores else 1.0 for s in store_ids], float)
                weights = weights / weights.sum()
                store_id = np.random.choice(store_ids, p=weights)
                sp_pool = sp_by_store.get(store_id, salespeople["salesperson_id"].tolist())
                sp_id = random.choice(sp_pool)

            # basket size
            base_basket = np.random.poisson(1.2) + 1
            seg = cust_df.loc[cust_df["customer_id"]==cust_id, "segment"].iloc[0]
            if seg=="loyal" and random.random()<0.35: base_basket += 1
            if sp_id in top_salespeople and random.random()<0.45: base_basket += 1
            basket_size = int(np.clip(base_basket, 1, 7))

            # primary category
            if random.random() < (0.62 if channel=="store" else 0.58):
                primary_cat = "Fashion"
                primary_sku = random.choice(fashion_skus) if fashion_skus else random.choice(skus["sku_id"].tolist())
            else:
                primary_cat = "Electronics"
                if random.random() < cfg.hero_primary_pick_prob and hero_skus:
                    primary_sku = random.choice(list(hero_skus))
                else:
                    primary_sku = random.choice(elec_skus) if elec_skus else random.choice(skus["sku_id"].tolist())

            basket = [primary_sku]
            for _ in range(basket_size - 1):
                r = random.random()
                if r < 0.55:
                    basket.append(random.choice(fashion_skus) if fashion_skus else random.choice(skus["sku_id"].tolist()))
                elif r < 0.80:
                    basket.append(random.choice(elec_skus) if elec_skus else random.choice(skus["sku_id"].tolist()))
                else:
                    basket.append(random.choice(addon_skus) if addon_skus else random.choice(skus["sku_id"].tolist()))

            if random.random() < attach_prob(channel, sp_id, cust_id, primary_cat):
                for _a in range(1 if random.random()<0.7 else 2):
                    basket.append(random.choice(addon_skus) if addon_skus else random.choice(skus["sku_id"].tolist()))

            total = 0.0
            pay = random.choice(payment_online if channel=="online" else payment_store)

            for sku_id in basket:
                qty = 1
                if sku_id in addon_skus and random.random()<0.18:
                    qty = int(np.random.choice([2,3], p=[0.8,0.2]))

                base_price = float(base_price_map[sku_id])
                unit_price = base_price * float(np.clip(np.random.normal(1.0,0.02), 0.93, 1.07))

                # ✅ hero premium to strengthen concentration a bit
                if sku_id in hero_skus:
                    unit_price *= float(np.clip(np.random.normal(1.05,0.02), 1.01, 1.10))

                promo_discount = 0.0
                product_id = sku_to_product[sku_id]
                if product_id in pr_promos:
                    active = [p for p in pr_promos[product_id] if (p["start_date"] <= ts <= p["end_date"])]
                    if active:
                        p = random.choice(active)
                        promo_discount = (random.choice([0.05,0.10,0.15]) if p["discount_type"]=="percent"
                                         else float(random.choice([200,500,1000])) / max(unit_price,1.0))

                d = discount_rate(channel, store_id, sp_id, cust_id, sku_id) + promo_discount
                d = float(np.clip(d, 0.0, 0.35))

                # ✅ clearance tail injection (visible extreme discounts)
                if channel=="store" and store_id in discount_heavy_stores and random.random() < cfg.clearance_line_prob:
                    d = max(d, float(np.random.uniform(cfg.clearance_discount_min, cfg.clearance_discount_max)))

                line_total = float(qty * unit_price * (1.0 - d))
                total += line_total

                line_rows.append({
                    "line_id": f"L{line_id:08d}",
                    "transaction_id": tid,
                    "sku_id": sku_id,
                    "quantity": qty,
                    "unit_price": round(unit_price,2),
                    "discount": round(d,4),
                    "line_total": round(line_total,2),
                })
                line_id += 1

            tx_rows.append({
                "transaction_id": tid,
                "transaction_ts": ts.isoformat(),
                "channel_type": channel,
                "store_id": store_id,
                "customer_id": cust_id,
                "salesperson_id": sp_id,
                "payment_method": pay,
                "total_amount": round(total,2),
            })

        for _ in range(online_tx_m): make_tx("online")
        for _ in range(store_tx_m): make_tx("store")

    tx_df = pd.DataFrame(tx_rows)
    lines_df = pd.DataFrame(line_rows)

    # Trim to target lines (keep referential integrity)
    if len(lines_df) > cfg.n_lines_target:
        tx_keep = tx_df.sample(int(cfg.n_lines_target / (len(lines_df)/len(tx_df))), random_state=cfg.seed)["transaction_id"]
        tx_keep = set(tx_keep.tolist())
        lines_df = lines_df[lines_df["transaction_id"].isin(tx_keep)].reset_index(drop=True)
        tx_df = tx_df[tx_df["transaction_id"].isin(tx_keep)].reset_index(drop=True)
        totals = lines_df.groupby("transaction_id")["line_total"].sum().reset_index()
        tx_df = tx_df.drop(columns=["total_amount"]).merge(totals, on="transaction_id", how="left").rename(columns={"line_total":"total_amount"})

    meta = {
        "underperforming_stores": sorted(list(under_stores)),
        "discount_heavy_stores": sorted(list(discount_heavy_stores)),
        "online_share_by_month": {str(k): v for k,v in online_share_by_month.items()},
    }
    return tx_df, lines_df, meta
