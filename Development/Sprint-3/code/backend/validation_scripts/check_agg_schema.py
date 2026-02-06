"""Sanity check on aggregations schema: tables, columns, constraints, data quality."""
from sqlalchemy import create_engine, text

DB = 'postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres'
e = create_engine(DB)

with e.connect() as c:

    # 1. Tables
    print("=" * 70)
    print("1. TABLES IN aggregations SCHEMA")
    print("=" * 70)
    r = c.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'aggregations' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """))
    tables = [row[0] for row in r.fetchall()]
    for t in tables:
        cnt = c.execute(text(f"SELECT COUNT(*) FROM aggregations.{t}")).scalar()
        print(f"  {t}: {cnt:,} rows")

    # 2. Columns per table
    print()
    print("=" * 70)
    print("2. COLUMNS")
    print("=" * 70)
    for t in tables:
        r = c.execute(text(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'aggregations' AND table_name = '{t}'
            ORDER BY ordinal_position
        """))
        print(f"\n  --- aggregations.{t} ---")
        for row in r.fetchall():
            print(f"    {row[0]:<30} {row[1]:<25} nullable={row[2]}")

    # 3. Primary Keys
    print()
    print("=" * 70)
    print("3. PRIMARY KEYS")
    print("=" * 70)
    r = c.execute(text("""
        SELECT tc.table_name,
               string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position)
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'aggregations'
        GROUP BY tc.table_name ORDER BY tc.table_name
    """))
    pks = r.fetchall()
    if pks:
        for row in pks:
            print(f"  ✅ {row[0]}: ({row[1]})")
    else:
        print("  NONE")

    # 4. Foreign Keys
    print()
    print("=" * 70)
    print("4. FOREIGN KEYS")
    print("=" * 70)
    r = c.execute(text("""
        SELECT tc.table_name, kcu.column_name,
               ccu.table_schema || '.' || ccu.table_name || '.' || ccu.column_name AS ref
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'aggregations'
        ORDER BY tc.table_name
    """))
    fks = r.fetchall()
    if fks:
        for row in fks:
            print(f"  ✅ {row[0]}.{row[1]} → {row[2]}")
    else:
        print("  NONE")

    # 5. Unique constraints
    print()
    print("=" * 70)
    print("5. UNIQUE CONSTRAINTS")
    print("=" * 70)
    r = c.execute(text("""
        SELECT tc.table_name, tc.constraint_name,
               string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position)
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'aggregations'
        GROUP BY tc.table_name, tc.constraint_name
    """))
    uqs = r.fetchall()
    if uqs:
        for row in uqs:
            print(f"  ✅ {row[0]}: ({row[2]})")
    else:
        print("  NONE")

    # 6. Indexes
    print()
    print("=" * 70)
    print("6. INDEXES")
    print("=" * 70)
    r = c.execute(text("""
        SELECT tablename, indexname FROM pg_indexes
        WHERE schemaname = 'aggregations' ORDER BY tablename, indexname
    """))
    idxs = r.fetchall()
    if idxs:
        for row in idxs:
            print(f"  {row[0]}: {row[1]}")
    else:
        print("  NONE (apart from auto PK indexes)")

    # 7. Referential integrity check — do aggregation IDs match silkroute?
    print()
    print("=" * 70)
    print("7. REFERENTIAL INTEGRITY vs silkroute")
    print("=" * 70)
    checks = [
        ("sales_detailed", "transaction_id", "silkroute.transactions", "transaction_id", False),
        ("sales_detailed", "line_id", "silkroute.transaction_lines", "line_id", False),
        ("sales_detailed", "sku_id", "silkroute.product_variants_skus", "sku_id", False),
        ("sales_detailed", "customer_id", "silkroute.customers", "customer_id", True),
        ("sales_detailed", "store_id", "silkroute.stores", "store_id", True),
        ("sales_detailed", "channel_type", "silkroute.channels", "channel_type", False),
        ("store_daily_performance", "store_id", "silkroute.stores", "store_id", False),
        ("customer_360", "customer_id", "silkroute.customers", "customer_id", False),
    ]
    for child, col, parent, pcol, nullable in checks:
        if child not in tables:
            print(f"  ⚠️  {child} table missing, skipping")
            continue
        null_clause = f"AND a.{col} IS NOT NULL" if nullable else ""
        r = c.execute(text(f"""
            SELECT COUNT(*) FROM aggregations.{child} a
            WHERE NOT EXISTS (
                SELECT 1 FROM {parent} p WHERE p.{pcol} = a.{col}
            ) {null_clause}
        """))
        orphans = r.scalar()
        status = "✅" if orphans == 0 else f"❌ {orphans} orphans"
        print(f"  {child}.{col} → {parent}.{pcol}: {status}")

    # 8. Check for NULLs and data quality
    print()
    print("=" * 70)
    print("8. NULL RATES IN AGGREGATION TABLES")
    print("=" * 70)
    for t in tables:
        r = c.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'aggregations' AND table_name = '{t}'
            ORDER BY ordinal_position
        """))
        cols = [row[0] for row in r.fetchall()]
        print(f"\n  --- {t} ---")
        for col in cols:
            r = c.execute(text(f"""
                SELECT COUNT(*) FILTER (WHERE {col} IS NULL) AS nulls,
                       COUNT(*) AS total
                FROM aggregations.{t}
            """))
            nulls, total = r.fetchone()
            pct = (nulls / total * 100) if total > 0 else 0
            flag = "" if pct == 0 else f"  ⚠️" if pct < 50 else f"  🔴"
            if pct > 0:
                print(f"    {col:<30} {nulls:>6}/{total} ({pct:.1f}%){flag}")
