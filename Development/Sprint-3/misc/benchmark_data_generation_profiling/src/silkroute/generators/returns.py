from __future__ import annotations
import random
import numpy as np
import pandas as pd
from silkroute.config import Config

def gen_returns(cfg: Config, customers: pd.DataFrame, products: pd.DataFrame, skus: pd.DataFrame, tx: pd.DataFrame, lines: pd.DataFrame, pattern_sets: dict, customer_sets: dict):
    tx2 = tx.copy()
    tx2["transaction_ts"] = pd.to_datetime(tx2["transaction_ts"])

    cust_seg = customers.set_index("customer_id")["segment"].to_dict()
    sku_to_product = skus.set_index("sku_id")["product_id"].to_dict()
    product_to_cat = products.set_index("product_id")["category"].to_dict()

    high_return_skus = set(pattern_sets["high_return_skus"])
    high_return_customers = set(customer_sets["high_return_customers"])

    lo, hi = cfg.return_rate_target
    target_rate = float(np.random.uniform(lo, hi))
    n_ret_tx = int(len(tx2) * target_rate)
    ret_tx_ids = set(tx2.sample(n_ret_tx, random_state=cfg.seed)["transaction_id"].tolist())

    reasons = ["size_issue","defective","not_as_described","changed_mind","delivery_issue","compatibility_issue","quality_issue"]

    out = []
    rid = 1

    for tid in ret_tx_ids:
        tx_lines = lines[lines["transaction_id"] == tid]
        if tx_lines.empty:
            continue

        cust_id = tx2.loc[tx2["transaction_id"] == tid, "customer_id"].iloc[0]
        seg = cust_seg.get(cust_id, "regular")

        # ✅ stronger multi-line returns for high-return customers
        if cust_id in high_return_customers and random.random() < cfg.high_return_customer_3line_prob:
            k = 3
        else:
            k = 2 if random.random() < cfg.return_two_lines_prob else 1

        line_rows = tx_lines.to_dict("records")
        weights = []
        for r in line_rows:
            w = 1.0
            if r["sku_id"] in high_return_skus:
                w *= cfg.high_return_sku_weight_mult
            if cust_id in high_return_customers:
                w *= cfg.high_return_customer_weight_mult
            if seg == "one_time":
                w *= 0.8
            cat = product_to_cat.get(sku_to_product[r["sku_id"]], "")
            if cat == "Electronics":
                w *= 1.25
            weights.append(w)

        weights = np.array(weights, float)
        weights = weights / weights.sum()

        chosen = np.random.choice(len(line_rows), size=min(k, len(line_rows)), replace=False, p=weights)

        for idx in chosen:
            r = line_rows[int(idx)]
            sku_id = r["sku_id"]
            refund_amount = float(r["line_total"]) * float(np.random.uniform(0.9, 1.0))

            cat = product_to_cat.get(sku_to_product[sku_id], "")
            if cat == "Fashion":
                rr = "size_issue" if random.random() < 0.55 else random.choice(reasons)
            elif cat == "Electronics":
                rr = "defective" if random.random() < 0.35 else ("not_as_described" if random.random() < 0.5 else random.choice(reasons))
            else:
                rr = "compatibility_issue" if random.random() < 0.35 else random.choice(reasons)

            out.append({
                "return_id": f"R{rid:07d}",
                "transaction_id": tid,
                "sku_id": sku_id,
                "return_reason": rr,
                "refund_amount": round(refund_amount, 2),
            })
            rid += 1

    return pd.DataFrame(out)
