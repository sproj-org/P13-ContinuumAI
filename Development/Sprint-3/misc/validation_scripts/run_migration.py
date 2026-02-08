"""Run the migration script to enforce constraints on silkroute schema."""
from sqlalchemy import create_engine, text
from pathlib import Path

DB_URL = 'postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres'
engine = create_engine(DB_URL)

sql_path = Path(__file__).parent / 'database' / 'migrate_silkroute_constraints.sql'
sql = sql_path.read_text(encoding='utf-8')

print("=" * 60)
print("Running migration: migrate_silkroute_constraints.sql")
print("=" * 60)

with engine.connect() as conn:
    # Execute the entire script as one transaction
    conn.execute(text(sql))
    conn.commit()
    print("\n✅ Migration completed successfully!\n")

    # Verification
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    print("\n--- PRIMARY KEYS ---")
    r = conn.execute(text("""
        SELECT tc.table_name, string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as pk_cols
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'silkroute'
        GROUP BY tc.table_name ORDER BY tc.table_name
    """))
    for row in r.fetchall():
        print(f"  ✅ {row[0]}: ({row[1]})")

    print("\n--- UNIQUE CONSTRAINTS ---")
    r = conn.execute(text("""
        SELECT tc.table_name, tc.constraint_name,
               string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as cols
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'silkroute'
        GROUP BY tc.table_name, tc.constraint_name ORDER BY tc.table_name
    """))
    for row in r.fetchall():
        print(f"  ✅ {row[0]}: ({row[2]})")

    print("\n--- FOREIGN KEYS ---")
    r = conn.execute(text("""
        SELECT tc.table_name, kcu.column_name, 
               ccu.table_name AS ref_table, ccu.column_name AS ref_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu 
            ON tc.constraint_name = ccu.constraint_name AND tc.constraint_schema = ccu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'silkroute'
        ORDER BY tc.table_name, kcu.column_name
    """))
    for row in r.fetchall():
        print(f"  ✅ {row[0]}.{row[1]} → {row[2]}.{row[3]}")

    print("\n--- INDEXES ---")
    r = conn.execute(text("""
        SELECT tablename, indexname FROM pg_indexes 
        WHERE schemaname = 'silkroute' 
        AND indexname LIKE 'idx_%'
        ORDER BY tablename, indexname
    """))
    for row in r.fetchall():
        print(f"  ✅ {row[0]}: {row[1]}")

    # Verify S000 was inserted
    print("\n--- S000 DC STORE ---")
    r = conn.execute(text("SELECT store_id, store_name, store_type FROM silkroute.stores WHERE store_id = 'S000'"))
    row = r.fetchone()
    if row:
        print(f"  ✅ {row[0]}: {row[1]} ({row[2]})")
    else:
        print("  ❌ S000 not found!")

    # Summary counts
    print("\n--- SUMMARY ---")
    for ctype in ['PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY']:
        r = conn.execute(text(f"""
            SELECT COUNT(*) FROM information_schema.table_constraints
            WHERE constraint_type = '{ctype}' AND table_schema = 'silkroute'
        """))
        print(f"  {ctype}: {r.scalar()}")

    r = conn.execute(text("""
        SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'silkroute' AND indexname LIKE 'idx_%'
    """))
    print(f"  INDEXES (custom): {r.scalar()}")
