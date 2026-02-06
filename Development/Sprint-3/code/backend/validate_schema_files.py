"""
Validate that the schema definition files (silkroute_schema.sql, aggregations_schema.sql)
accurately reflect the actual database schema.
"""
from sqlalchemy import create_engine, text

DB = 'postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres'
e = create_engine(DB)

# Expected from silkroute_schema.sql
SILKROUTE_TABLES = {
    'channels': {'pk': ['channel_type'], 'fks': 0},
    'stores': {'pk': ['store_id'], 'fks': 0},
    'customers': {'pk': ['customer_id'], 'fks': 0},
    'salespeople': {'pk': ['salesperson_id'], 'fks': 1},
    'products': {'pk': ['product_id'], 'fks': 0},
    'product_variants_skus': {'pk': ['sku_id'], 'fks': 1},
    'variant_attributes': {'pk': None, 'uq': ['attribute_name', 'sku_id'], 'fks': 1},
    'category_attribute_definitions': {'pk': None, 'uq': ['attribute_name', 'category'], 'fks': 0},
    'promotions': {'pk': ['promo_id'], 'fks': 1},
    'transactions': {'pk': ['transaction_id'], 'fks': 2},
    'transaction_lines': {'pk': ['line_id'], 'fks': 2},
    'inventory_snapshots': {'pk': None, 'uq': ['sku_id', 'snapshot_date', 'store_id'], 'fks': 2},
    'returns': {'pk': ['return_id'], 'fks': 2},
}

AGGREGATIONS_TABLES = {
    'sales_detailed': {'pk': ['line_id'], 'fks': 6},
    'store_daily_performance': {'pk': ['calendar_date', 'store_id'], 'fks': 1},
    'customer_360': {'pk': ['customer_id'], 'fks': 1},
}

passed = 0
failed = 0

def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}  — {detail}")

with e.connect() as c:

    print("=" * 75)
    print("VALIDATING: silkroute_schema.sql")
    print("=" * 75)

    # 1. Table count
    r = c.execute(text("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'silkroute' AND table_type = 'BASE TABLE'
    """))
    actual_count = r.scalar()
    check("Table count", actual_count == len(SILKROUTE_TABLES),
          f"expected 13, found {actual_count}")

    # 2. Each table exists
    for tbl in SILKROUTE_TABLES:
        r = c.execute(text(f"""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'silkroute' AND table_name = '{tbl}'
        """))
        exists = r.scalar() > 0
        check(f"Table: {tbl}", exists, "NOT FOUND")

    # 3. Primary keys
    for tbl, spec in SILKROUTE_TABLES.items():
        expected_pk = spec.get('pk')
        if expected_pk:
            r = c.execute(text(f"""
                SELECT string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position)
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'silkroute' AND tc.table_name = '{tbl}'
            """))
            actual = r.scalar()
            actual_cols = sorted(actual.split(',')) if actual else None
            check(f"PK: {tbl}({','.join(expected_pk)})",
                  actual_cols == sorted(expected_pk),
                  f"actual={actual_cols}")

    # 4. Unique constraints (for tables with pk=None)
    for tbl, spec in SILKROUTE_TABLES.items():
        expected_uq = spec.get('uq')
        if expected_uq:
            r = c.execute(text(f"""
                SELECT string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position)
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'UNIQUE'
                  AND tc.table_schema = 'silkroute' AND tc.table_name = '{tbl}'
                LIMIT 1
            """))
            actual = r.scalar()
            actual_cols = sorted(actual.split(',')) if actual else None
            check(f"UNIQUE: {tbl}({','.join(expected_uq)})",
                  actual_cols == sorted(expected_uq),
                  f"actual={actual_cols}")

    # 5. Foreign key counts
    for tbl, spec in SILKROUTE_TABLES.items():
        expected_fks = spec['fks']
        r = c.execute(text(f"""
            SELECT COUNT(DISTINCT tc.constraint_name)
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'silkroute' AND tc.table_name = '{tbl}'
        """))
        actual_fks = r.scalar()
        check(f"FK count: {tbl}", actual_fks == expected_fks,
              f"expected {expected_fks}, found {actual_fks}")

    # 6. Row counts (verify documented counts are approximately correct)
    expected_rows = {
        'channels': 2, 'stores': 7, 'customers': 2500, 'salespeople': 26,
        'products': 90, 'product_variants_skus': 150, 'variant_attributes': 246,
        'category_attribute_definitions': 11, 'promotions': 12,
        'transactions': 11402, 'transaction_lines': 29924,
        'inventory_snapshots': 55650, 'returns': 1287
    }
    for tbl, expected in expected_rows.items():
        r = c.execute(text(f"SELECT COUNT(*) FROM silkroute.{tbl}"))
        actual = r.scalar()
        # Allow ±5% variance
        tolerance = max(1, int(expected * 0.05))
        ok = abs(actual - expected) <= tolerance
        check(f"Row count: {tbl} ≈ {expected:,}",
              ok, f"actual={actual:,}")

    print()
    print("=" * 75)
    print("VALIDATING: aggregations_schema.sql")
    print("=" * 75)

    # 1. Table count
    r = c.execute(text("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'aggregations' AND table_type = 'BASE TABLE'
    """))
    actual_count = r.scalar()
    check("Table count", actual_count == len(AGGREGATIONS_TABLES),
          f"expected 3, found {actual_count}")

    # 2. Each table exists
    for tbl in AGGREGATIONS_TABLES:
        r = c.execute(text(f"""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'aggregations' AND table_name = '{tbl}'
        """))
        exists = r.scalar() > 0
        check(f"Table: {tbl}", exists, "NOT FOUND")

    # 3. Primary keys
    for tbl, spec in AGGREGATIONS_TABLES.items():
        expected_pk = spec['pk']
        r = c.execute(text(f"""
            SELECT string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position)
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'aggregations' AND tc.table_name = '{tbl}'
        """))
        actual = r.scalar()
        actual_cols = sorted(actual.split(',')) if actual else None
        check(f"PK: {tbl}({','.join(expected_pk)})",
              actual_cols == sorted(expected_pk),
              f"actual={actual_cols}")

    # 4. Foreign key counts
    for tbl, spec in AGGREGATIONS_TABLES.items():
        expected_fks = spec['fks']
        r = c.execute(text(f"""
            SELECT COUNT(DISTINCT tc.constraint_name)
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'aggregations' AND tc.table_name = '{tbl}'
        """))
        actual_fks = r.scalar()
        check(f"FK count: {tbl}", actual_fks == expected_fks,
              f"expected {expected_fks}, found {actual_fks}")

    # 5. Row counts
    expected_rows = {
        'sales_detailed': 29924,
        'store_daily_performance': 2096,
        'customer_360': 2500
    }
    for tbl, expected in expected_rows.items():
        r = c.execute(text(f"SELECT COUNT(*) FROM aggregations.{tbl}"))
        actual = r.scalar()
        tolerance = max(1, int(expected * 0.05))
        ok = abs(actual - expected) <= tolerance
        check(f"Row count: {tbl} ≈ {expected:,}",
              ok, f"actual={actual:,}")

    # 6. Index counts
    r = c.execute(text("""
        SELECT COUNT(*) FROM pg_indexes
        WHERE schemaname = 'silkroute' AND indexname LIKE 'idx_%'
    """))
    silkroute_idx = r.scalar()
    check("Silkroute custom indexes = 14", silkroute_idx == 14,
          f"found {silkroute_idx}")

    r = c.execute(text("""
        SELECT COUNT(*) FROM pg_indexes
        WHERE schemaname = 'aggregations' AND indexname LIKE 'idx_%'
    """))
    agg_idx = r.scalar()
    check("Aggregations custom indexes = 11", agg_idx == 11,
          f"found {agg_idx}")

    # Summary
    print()
    print("=" * 75)
    print(f"VALIDATION COMPLETE: {passed} passed, {failed} failed")
    print("=" * 75)
    if failed == 0:
        print("🎉 Schema definition files are 100% accurate!")
    else:
        print(f"⚠️  {failed} mismatch(es) found — update the .sql files")
