from __future__ import annotations
import random
import numpy as np
import pandas as pd
from silkroute.config import Config

def gen_products_and_skus(cfg: Config, catalogs: dict):
    category_map = catalogs["category_map"]
    brands_map = catalogs["brands"]

    products = []
    all_leaf = []
    for top_cat, subcat_map in category_map.items():
        for mid_cat, leafs in subcat_map.items():
            for leaf in leafs:
                all_leaf.append((top_cat, mid_cat, leaf))

    chosen = random.sample(all_leaf, k=min(cfg.n_products, len(all_leaf)))
    while len(chosen) < cfg.n_products:
        chosen.append(random.choice(all_leaf))

    for i in range(cfg.n_products):
        top_cat, mid_cat, leaf = chosen[i]
        brand = random.choice(brands_map[top_cat])
        products.append({
            "product_id": f"PR{i+1:04d}",
            "product_name": f"{brand} {leaf.title()}",
            "brand": brand,
            "category": top_cat,
            "subcategory": f"{mid_cat} > {leaf}",
            "status": "active",
        })
    products_df = pd.DataFrame(products)

    sizes = ["XS", "S", "M", "L", "XL"]
    colors_common = ["Black", "White", "Navy", "Grey", "Red", "Blue", "Green"]
    colors_elec = ["Black", "Silver", "Gold", "Blue"]

    def base_price_for(cat: str, subcat: str) -> float:
        if cat == "Fashion":
            if "Footwear" in subcat: return float(np.random.randint(3500, 16000))
            if "Accessories" in subcat: return float(np.random.randint(800, 5500))
            return float(np.random.randint(1500, 9000))
        if cat == "Electronics":
            if "Smartphones" in subcat: return float(np.random.randint(45000, 220000))
            if "Laptops" in subcat: return float(np.random.randint(120000, 420000))
            if "Audio devices" in subcat: return float(np.random.randint(6000, 45000))
            return float(np.random.randint(1000, 14000))
        if "Extended services" in subcat: return float(np.random.randint(3000, 25000))
        if "Cases & protection" in subcat: return float(np.random.randint(500, 6000))
        return float(np.random.randint(1200, 18000))

    skus = []
    sku_attrs = []
    sku_id_counter = 1

    for _, pr in products_df.iterrows():
        cat = pr["category"]; subcat = pr["subcategory"]
        nvar = np.random.randint(2, 5) if cat == "Fashion" else np.random.randint(1, 3)

        for _ in range(nvar):
            sku_id = f"SKU{sku_id_counter:05d}"
            sku_id_counter += 1

            size = None
            color = None
            if cat == "Fashion":
                size = random.choice(sizes)
                color = random.choice(colors_common)
            elif cat == "Electronics":
                color = random.choice(colors_elec)
            else:
                color = random.choice(["Black", "White", "Blue", "Red", "Transparent"])

            bp = base_price_for(cat, subcat)
            skus.append({
                "sku_id": sku_id,
                "product_id": pr["product_id"],
                "size": size,
                "color": color,
                "base_price": round(bp, 2),
                "active_flag": True,
            })

            if cat == "Fashion":
                sku_attrs += [
                    {"sku_id": sku_id, "attribute_name": "material", "attribute_value": random.choice(["cotton", "denim", "polyester", "leather"]), "attribute_type": "text"},
                    {"sku_id": sku_id, "attribute_name": "season", "attribute_value": random.choice(["summer", "winter", "all_season"]), "attribute_type": "text"},
                ]
            elif cat == "Electronics":
                sku_attrs += [{"sku_id": sku_id, "attribute_name": "warranty_months", "attribute_value": str(random.choice([12,18,24])), "attribute_type": "int"}]
                if "Smartphones" in subcat:
                    sku_attrs += [
                        {"sku_id": sku_id, "attribute_name": "storage_gb", "attribute_value": str(random.choice([128,256,512])), "attribute_type": "int"},
                        {"sku_id": sku_id, "attribute_name": "battery_mah", "attribute_value": str(random.choice([4500,5000,6000])), "attribute_type": "int"},
                    ]
                if "Laptops" in subcat:
                    sku_attrs += [
                        {"sku_id": sku_id, "attribute_name": "ram_gb", "attribute_value": str(random.choice([8,16,32])), "attribute_type": "int"},
                        {"sku_id": sku_id, "attribute_name": "screen_size_in", "attribute_value": str(random.choice([13.3,14.0,15.6,16.0])), "attribute_type": "float"},
                    ]
            else:
                if "Cases & protection" in subcat:
                    sku_attrs += [{"sku_id": sku_id, "attribute_name": "compatibility", "attribute_value": random.choice(["Android","iPhone","Laptop 14in","Laptop 15.6in"]), "attribute_type": "text"}]

    skus_df = pd.DataFrame(skus)
    sku_attrs_df = pd.DataFrame(sku_attrs)
    cat_attr_defs_df = catalogs["category_attribute_definitions"].copy()

    if len(skus_df) > cfg.n_skus_target:
        skus_df = skus_df.sample(cfg.n_skus_target, random_state=cfg.seed).sort_values("sku_id").reset_index(drop=True)
        keep = set(skus_df["sku_id"].tolist())
        sku_attrs_df = sku_attrs_df[sku_attrs_df["sku_id"].isin(keep)].reset_index(drop=True)

    hero_skus = set(skus_df.sample(cfg.hero_sku_count, random_state=cfg.seed)["sku_id"].tolist())
    remaining = skus_df[~skus_df["sku_id"].isin(hero_skus)]
    high_return_skus = set(remaining.sample(cfg.high_return_sku_count, random_state=cfg.seed+2)["sku_id"].tolist())

    return products_df, skus_df, sku_attrs_df, cat_attr_defs_df, {
        "hero_skus": sorted(list(hero_skus)),
        "high_return_skus": sorted(list(high_return_skus)),
    }
