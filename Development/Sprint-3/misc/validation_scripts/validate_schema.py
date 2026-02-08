"""
Validate that silkroute schema constraints match TARGET_SCHEMAS from 00_schema_validation.ipynb.
Checks: PKs, UNIQUE constraints, FKs, column existence, row counts.
"""
from sqlalchemy import create_engine, text

DB_URL = 'postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres'
engine = create_engine(DB_URL)

# ── TARGET_SCHEMAS (copied from notebook) ──
TARGET_SCHEMAS = {
    "channels": {
        "required": ["channel_type", "channel_name"],
        "primary_key": ["channel_type"],
    },
    "stores": {
        "required": ["store_id", "store_name", "city", "region", "store_type"],
        "primary_key": ["store_id"],
    },
    "customers": {
        "required": ["customer_id", "segment", "city", "region", "first_purchase_date"],
        "primary_key": ["customer_id"],
    },
    "salespeople": {
        "required": ["salesperson_id", "name", "role", "store_id"],
        "primary_key": ["salesperson_id"],
        "foreign_keys": [("store_id", "stores", "store_id")],
    },
    "products": {
        "required": ["product_id", "product_name", "brand", "category", "subcategory", "status"],
        "primary_key": ["product_id"],
    },
    "product_variants_skus": {
        "required": ["sku_id", "product_id", "size", "color", "base_price", "active_flag"],
        "primary_key": ["sku_id"],
        "foreign_keys": [("product_id", "products", "product_id")],
    },
    "variant_attributes": {
        "required": ["sku_id", "attribute_name", "attribute_value", "attribute_type"],
        "primary_key": None,
        "foreign_keys": [("sku_id", "product_variants_skus", "sku_id")],
    },
    "category_attribute_definitions": {
        "required": ["category", "attribute_name", "attribute_type", "required_flag"],
        "primary_key": None,
    },
    "promotions": {
        "required": ["promo_id", "product_id", "promo_type", "start_date", "end_date", "discount_type"],
        "primary_key": ["promo_id"],
        "foreign_keys": [("product_id", "products", "product_id")],
    },
    "transactions": {
        "required": ["transaction_id", "transaction_ts", "channel_type", "store_id", "customer_id", "salesperson_id", "payment_method", "total_amount"],
        "primary_key": ["transaction_id"],
        "foreign_keys": [
            ("channel_type", "channels", "channel_type"),
            ("customer_id", "customers", "customer_id"),
        ],
    },
    "transaction_lines": {
        "required": ["line_id", "transaction_id", "sku_id", "quantity", "unit_price", "discount", "line_total"],
        "primary_key": ["line_id"],
        "foreign_keys": [
            ("transaction_id", "transactions", "transaction_id"),
            ("sku_id", "product_variants_skus", "sku_id"),
        ],
    },
    "inventory_snapshots": {
        "required": ["snapshot_date", "store_id", "sku_id", "stock_on_hand", "stock_on_order"],
        "primary_key": None,
        "foreign_keys": [
            ("sku_id", "product_variants_skus", "sku_id"),
            ("store_id", "stores", "store_id"),
        ],
    },
    "returns": {
        "required": ["return_id", "transaction_id", "sku_id", "return_reason", "refund_amount"],
        "primary_key": ["return_id"],
        "foreign_keys": [
            ("transaction_id", "transactions", "transaction_id"),
            ("sku_id", "product_variants_skus", "sku_id"),
        ],
    },
}

passed = 0
failed = 0
total = 0

def check(label, ok, detail=""):
    global passed, failed, total
    total += 1
    if ok:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}  — {detail}")

with engine.connect() as c:

    # ── 1. TABLE EXISTENCE ──
    print("=" * 65)
    print("1. TABLE EXISTENCE")
    print("=" * 65)
    r = c.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'silkroute' ORDER BY table_name
    """))
    db_tables = {row[0] for row in r.fetchall()}
    for t in TARGET_SCHEMAS:
        check(t, t in db_tables, "TABLE MISSING")
    extra = db_tables - set(TARGET_SCHEMAS.keys())
    if extra:
        print(f"  ⚠️  Extra tables not in spec: {extra}")

    # ── 2. REQUIRED COLUMNS ──
    print()
    print("=" * 65)
    print("2. REQUIRED COLUMNS")
    print("=" * 65)
    for t, spec in TARGET_SCHEMAS.items():
        if t not in db_tables:
            continue
        r = c.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'silkroute' AND table_name = '{t}'
        """))
        db_cols = {row[0] for row in r.fetchall()}
        missing = [col for col in spec["required"] if col not in db_cols]
        extra_cols = db_cols - set(spec["required"])
        check(f"{t} columns", len(missing) == 0,
              f"MISSING: {missing}" if missing else "")
        if extra_cols:
            print(f"       (extra cols: {sorted(extra_cols)})")

    # ── 3. PRIMARY KEYS ──
    print()
    print("=" * 65)
    print("3. PRIMARY KEYS")
    print("=" * 65)
    r = c.execute(text("""
        SELECT tc.table_name,
               string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as pk_cols
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'silkroute'
        GROUP BY tc.table_name
    """))
    db_pks = {row[0]: sorted(row[1].split(',')) for row in r.fetchall()}

    for t, spec in TARGET_SCHEMAS.items():
        expected_pk = spec.get("primary_key")
        if expected_pk:
            actual = db_pks.get(t)
            check(f"{t} PK = {expected_pk}",
                  actual is not None and sorted(expected_pk) == sorted(actual),
                  f"actual={actual}")
        else:
            # Should NOT have a PK (we used UNIQUE instead)
            check(f"{t} PK = None (no PK per spec)",
                  t not in db_pks,
                  f"unexpected PK found: {db_pks.get(t)}")

    # ── 4. UNIQUE CONSTRAINTS (for tables with primary_key: None) ──
    print()
    print("=" * 65)
    print("4. UNIQUE CONSTRAINTS (pk=None tables)")
    print("=" * 65)
    r = c.execute(text("""
        SELECT tc.table_name, tc.constraint_name,
               string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as cols
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'silkroute'
        GROUP BY tc.table_name, tc.constraint_name
    """))
    db_uniques = {}
    for row in r.fetchall():
        db_uniques.setdefault(row[0], []).append(sorted(row[2].split(',')))

    expected_uniques = {
        "variant_attributes": ["attribute_name", "sku_id"],
        "category_attribute_definitions": ["attribute_name", "category"],
        "inventory_snapshots": ["sku_id", "snapshot_date", "store_id"],
    }
    for t, expected_cols in expected_uniques.items():
        actual_list = db_uniques.get(t, [])
        found = any(sorted(expected_cols) == sorted(u) for u in actual_list)
        check(f"{t} UNIQUE ({', '.join(expected_cols)})", found,
              f"actual={actual_list}")

    # ── 5. FOREIGN KEYS ──
    print()
    print("=" * 65)
    print("5. FOREIGN KEYS")
    print("=" * 65)
    r = c.execute(text("""
        SELECT tc.table_name, kcu.column_name,
               ccu.table_name AS ref_table, ccu.column_name AS ref_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
           AND tc.constraint_schema = ccu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'silkroute'
        ORDER BY tc.table_name, kcu.column_name
    """))
    db_fks = set()
    for row in r.fetchall():
        db_fks.add((row[0], row[1], row[2], row[3]))

    for t, spec in TARGET_SCHEMAS.items():
        for fk in spec.get("foreign_keys", []):
            col, ref_table, ref_col = fk
            expected = (t, col, ref_table, ref_col)
            check(f"{t}.{col} → {ref_table}.{ref_col}",
                  expected in db_fks,
                  "FK NOT FOUND in database")

    # ── 6. INDEXES ──
    print()
    print("=" * 65)
    print("6. INDEXES")
    print("=" * 65)
    r = c.execute(text("""
        SELECT tablename, indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'silkroute' AND indexname LIKE 'idx_%'
        ORDER BY tablename, indexname
    """))
    idx_rows = r.fetchall()
    print(f"  Total custom indexes: {len(idx_rows)}")
    for row in idx_rows:
        print(f"  ✅ {row[0]}: {row[1]}")

    # ── 7. REFERENTIAL INTEGRITY (live data) ──
    print()
    print("=" * 65)
    print("7. REFERENTIAL INTEGRITY (live data check)")
    print("=" * 65)
    fk_checks = [
        ("salespeople", "store_id", "stores", "store_id", False),
        ("product_variants_skus", "product_id", "products", "product_id", False),
        ("variant_attributes", "sku_id", "product_variants_skus", "sku_id", False),
        ("promotions", "product_id", "products", "product_id", False),
        ("transactions", "channel_type", "channels", "channel_type", False),
        ("transactions", "customer_id", "customers", "customer_id", False),
        ("transactions", "store_id", "stores", "store_id", True),   # nullable
        ("transactions", "salesperson_id", "salespeople", "salesperson_id", True),
        ("transaction_lines", "transaction_id", "transactions", "transaction_id", False),
        ("transaction_lines", "sku_id", "product_variants_skus", "sku_id", False),
        ("inventory_snapshots", "sku_id", "product_variants_skus", "sku_id", False),
        ("inventory_snapshots", "store_id", "stores", "store_id", False),
        ("returns", "transaction_id", "transactions", "transaction_id", False),
        ("returns", "sku_id", "product_variants_skus", "sku_id", False),
    ]
    for child, col, parent, pcol, nullable in fk_checks:
        null_clause = f"AND c.{col} IS NOT NULL" if nullable else ""
        r = c.execute(text(f"""
            SELECT COUNT(*) FROM silkroute.{child} c
            WHERE NOT EXISTS (
                SELECT 1 FROM silkroute.{parent} p WHERE p.{pcol} = c.{col}
            ) {null_clause}
        """))
        orphans = r.scalar()
        check(f"{child}.{col} → {parent}.{pcol}",
              orphans == 0,
              f"{orphans} orphan rows!")

    # ── 8. PK UNIQUENESS (live data) ──
    print()
    print("=" * 65)
    print("8. PK / UNIQUE UNIQUENESS (live data check)")
    print("=" * 65)
    uniqueness_checks = [
        ("channels", "channel_type"),
        ("stores", "store_id"),
        ("customers", "customer_id"),
        ("salespeople", "salesperson_id"),
        ("products", "product_id"),
        ("product_variants_skus", "sku_id"),
        ("promotions", "promo_id"),
        ("transactions", "transaction_id"),
        ("transaction_lines", "line_id"),
        ("returns", "return_id"),
    ]
    for table, col in uniqueness_checks:
        r = c.execute(text(f"""
            SELECT COUNT(*) - COUNT(DISTINCT {col}) FROM silkroute.{table}
        """))
        dups = r.scalar()
        check(f"{table}.{col} unique", dups == 0, f"{dups} duplicates")

    # Composite unique checks
    composites = [
        ("variant_attributes", "sku_id, attribute_name"),
        ("category_attribute_definitions", "category, attribute_name"),
        ("inventory_snapshots", "snapshot_date, store_id, sku_id"),
    ]
    for table, cols in composites:
        r = c.execute(text(f"""
            SELECT COUNT(*) - COUNT(DISTINCT ({cols})) FROM silkroute.{table}
        """))
        dups = r.scalar()
        check(f"{table}.({cols}) unique", dups == 0, f"{dups} duplicates")

    # ── 9. ROW COUNTS ──
    print()
    print("=" * 65)
    print("9. ROW COUNTS")
    print("=" * 65)
    for t in sorted(TARGET_SCHEMAS.keys()):
        if t in db_tables:
            r = c.execute(text(f"SELECT COUNT(*) FROM silkroute.{t}"))
            cnt = r.scalar()
            print(f"  {t}: {cnt:,} rows")

    # ── SCORECARD ──
    print()
    print("=" * 65)
    print(f"SCORECARD:  {passed}/{total} passed   |   {failed} failed")
    print("=" * 65)
    if failed == 0:
        print("🎉 ALL CHECKS PASSED — Schema is fully enforced!")
    else:
        print(f"⚠️  {failed} check(s) need attention.")
