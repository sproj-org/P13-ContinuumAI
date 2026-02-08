"""Run aggregations constraint migration and verify."""
from sqlalchemy import create_engine, text
from pathlib import Path

DB = 'add_your_db_url_here'
engine = create_engine(DB)

sql_path = Path(__file__).parent / 'database' / 'migrate_aggregations_constraints.sql'
sql = sql_path.read_text(encoding='utf-8')

print("=" * 65)
print("Running: migrate_aggregations_constraints.sql")
print("=" * 65)

with engine.connect() as c:
    c.execute(text(sql))
    c.commit()
    print("\n✅ Migration completed!\n")

    # Verify PKs
    print("--- PRIMARY KEYS ---")
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
    for row in r.fetchall():
        print(f"  ✅ {row[0]}: ({row[1]})")

    # Verify FKs
    print("\n--- FOREIGN KEYS ---")
    r = c.execute(text("""
        SELECT tc.table_name, kcu.column_name,
               ccu.table_schema || '.' || ccu.table_name || '.' || ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'aggregations'
        ORDER BY tc.table_name, kcu.column_name
    """))
    for row in r.fetchall():
        print(f"  ✅ {row[0]}.{row[1]} → {row[2]}")

    # Verify Indexes
    print("\n--- INDEXES ---")
    r = c.execute(text("""
        SELECT tablename, indexname FROM pg_indexes
        WHERE schemaname = 'aggregations' ORDER BY tablename, indexname
    """))
    for row in r.fetchall():
        print(f"  ✅ {row[0]}: {row[1]}")

    # Summary
    print("\n--- SUMMARY ---")
    for ctype in ['PRIMARY KEY', 'FOREIGN KEY']:
        r = c.execute(text(f"""
            SELECT COUNT(*) FROM information_schema.table_constraints
            WHERE constraint_type = '{ctype}' AND table_schema = 'aggregations'
        """))
        print(f"  {ctype}: {r.scalar()}")
    r = c.execute(text("""
        SELECT COUNT(*) FROM pg_indexes
        WHERE schemaname = 'aggregations' AND indexname LIKE 'idx_%'
    """))
    print(f"  INDEXES (custom): {r.scalar()}")
