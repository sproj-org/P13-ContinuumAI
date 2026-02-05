from sqlalchemy import create_engine, text

e = create_engine('postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres')

with e.connect() as c:
    print('=== EXISTING PRIMARY KEYS ===')
    r = c.execute(text("""
        SELECT tc.table_name, string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position)
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'silkroute'
        GROUP BY tc.table_name ORDER BY tc.table_name
    """))
    rows = r.fetchall()
    if rows:
        for row in rows:
            print(f'  {row[0]}: {row[1]}')
    else:
        print('  NONE')

    print()
    print('=== EXISTING FOREIGN KEYS ===')
    r = c.execute(text("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu 
            ON tc.constraint_name = ccu.constraint_name AND tc.constraint_schema = ccu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'silkroute'
        ORDER BY tc.table_name
    """))
    rows = r.fetchall()
    if rows:
        for row in rows:
            print(f'  {row[0]}.{row[1]} -> {row[2]}.{row[3]}')
    else:
        print('  NONE')

    print()
    print('=== EXISTING INDEXES ===')
    r = c.execute(text("""
        SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'silkroute' ORDER BY tablename
    """))
    rows = r.fetchall()
    if rows:
        for row in rows:
            print(f'  {row[0]}: {row[1]}')
    else:
        print('  NONE')

    print()
    print('=== INVENTORY ORPHAN CHECK ===')
    r = c.execute(text("""
        SELECT COUNT(*) FROM silkroute.inventory_snapshots 
        WHERE store_id NOT IN (SELECT store_id FROM silkroute.stores)
    """))
    print(f'  Orphan rows: {r.scalar()}')

    r = c.execute(text("""
        SELECT DISTINCT store_id FROM silkroute.inventory_snapshots 
        WHERE store_id NOT IN (SELECT store_id FROM silkroute.stores)
        ORDER BY store_id
    """))
    orphans = [row[0] for row in r.fetchall()]
    print(f'  Orphan store_ids: {orphans}')

    r = c.execute(text("SELECT COUNT(*) FROM silkroute.stores WHERE store_id = 'S000'"))
    print(f'  S000 in stores table: {r.scalar() > 0}')

    # Check if all orphans are S000
    r = c.execute(text("""
        SELECT DISTINCT store_id FROM silkroute.inventory_snapshots 
        WHERE store_id NOT IN (SELECT store_id FROM silkroute.stores)
        AND store_id != 'S000'
    """))
    non_s000 = [row[0] for row in r.fetchall()]
    print(f'  Orphans that are NOT S000: {non_s000}')

    # Check duplicate PKs before enforcing
    print()
    print('=== DUPLICATE PK CHECK ===')
    checks = [
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
    for table, col in checks:
        r = c.execute(text(f"""
            SELECT COUNT(*) - COUNT(DISTINCT {col}) as dups
            FROM silkroute.{table}
        """))
        dups = r.scalar()
        status = "✅" if dups == 0 else f"❌ {dups} duplicates"
        print(f'  {table}.{col}: {status}')

    # Composite PK checks
    r = c.execute(text("""
        SELECT COUNT(*) - COUNT(DISTINCT (snapshot_date, store_id, sku_id))
        FROM silkroute.inventory_snapshots
    """))
    dups = r.scalar()
    print(f'  inventory_snapshots.(snapshot_date, store_id, sku_id): {"✅" if dups == 0 else f"❌ {dups} duplicates"}')

    r = c.execute(text("""
        SELECT COUNT(*) - COUNT(DISTINCT (sku_id, attribute_name))
        FROM silkroute.variant_attributes
    """))
    dups = r.scalar()
    print(f'  variant_attributes.(sku_id, attribute_name): {"✅" if dups == 0 else f"❌ {dups} duplicates"}')

    r = c.execute(text("""
        SELECT COUNT(*) - COUNT(DISTINCT (category, attribute_name))
        FROM silkroute.category_attribute_definitions
    """))
    dups = r.scalar()
    print(f'  category_attribute_definitions.(category, attribute_name): {"✅" if dups == 0 else f"❌ {dups} duplicates"}')
