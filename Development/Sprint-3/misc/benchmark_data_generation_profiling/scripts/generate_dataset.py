from __future__ import annotations
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_path))

from faker import Faker
from silkroute.config import Config
from silkroute.catalogs import build_catalogs
from silkroute.io import save_tables, save_manifest

from silkroute.generators.dimensions import seed_everything, gen_channels, gen_stores, gen_salespeople, gen_customers
from silkroute.generators.products import gen_products_and_skus
from silkroute.generators.promotions import gen_promotions
from silkroute.generators.transactions import gen_transactions_and_lines
from silkroute.generators.inventory import gen_inventory_snapshots
from silkroute.generators.returns import gen_returns


def main():
    cfg = Config()
    seed_everything(cfg.seed)
    fake = Faker()

    outdir = "silkroute_benchmark_out"
    catalogs = build_catalogs()

    channels = gen_channels()
    stores = gen_stores(cfg, fake)
    salespeople, people_sets = gen_salespeople(cfg, fake, stores)
    customers, customer_sets = gen_customers(cfg, fake)

    products, skus, sku_attrs, cat_attr_defs, pattern_sets = gen_products_and_skus(cfg, catalogs)
    promos = gen_promotions(cfg, products)

    tx, lines, meta = gen_transactions_and_lines(
        cfg=cfg,
        customers=customers,
        stores=stores,
        salespeople=salespeople,
        products=products,
        skus=skus,
        promos=promos,
        pattern_sets=pattern_sets,
        people_sets=people_sets,
        customer_sets=customer_sets,
    )

    inventory = gen_inventory_snapshots(cfg, stores, skus, tx, lines, pattern_sets)
    returns = gen_returns(cfg, customers, products, skus, tx, lines, pattern_sets, customer_sets)

    tables = {
        "channels": channels,
        "stores": stores,
        "salespeople": salespeople,
        "customers": customers,
        "products": products,
        "product_variants_skus": skus,
        "variant_attributes": sku_attrs,
        "category_attribute_definitions": cat_attr_defs,
        "promotions": promos,
        "transactions": tx,
        "transaction_lines": lines,
        "inventory_snapshots": inventory,
        "returns": returns,
    }
    save_tables(outdir, tables)

    manifest = {
        "config": cfg.__dict__,
        "pattern_sets": pattern_sets,
        "people_sets": people_sets,
        "customer_sets_summary": {
            "loyal_customers_n": len(customer_sets["loyal_customers"]),
            "high_return_customers_n": len(customer_sets["high_return_customers"]),
        },
        "meta": meta,
    }
    save_manifest(outdir, manifest)

    print("DONE")
    print("Output:", outdir)
    print("Seed manifest:", f"{outdir}/seed_manifest.json")


if __name__ == "__main__":
    main()
