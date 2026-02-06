"""
Run new aggregations schema migration:
1. Verify database connection
2. Drop old aggregations schema
3. Create new 6-table aggregations schema
"""

from sqlalchemy import create_engine, text, inspect
from pathlib import Path
import sys

# Database connection
DATABASE_URL = "postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"

def main():
    print("=" * 80)
    print("AGGREGATIONS SCHEMA MIGRATION")
    print("=" * 80)
    
    # Step 1: Test connection
    print("\n[1/4] Testing database connection...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✅ Connected to: {version[:50]}...")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    
    # Step 2: Check current aggregations schema
    print("\n[2/4] Checking current aggregations and marts schemas...")
    with engine.connect() as conn:
        # Check aggregations schema
        result = conn.execute(text("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_schema = 'aggregations' AND table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'aggregations'
            ORDER BY table_name;
        """))
        agg_tables = result.fetchall()
        
        # Check marts schema
        result = conn.execute(text("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_schema = 'marts' AND table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'marts'
            ORDER BY table_name;
        """))
        marts_tables = result.fetchall()
        
        if agg_tables:
            print(f"Found {len(agg_tables)} existing tables in aggregations schema:")
            for table_name, col_count in agg_tables:
                row_count_query = text(f"SELECT COUNT(*) FROM aggregations.{table_name}")
                row_count = conn.execute(row_count_query).scalar()
                print(f"  • {table_name}: {col_count} columns, {row_count:,} rows")
        else:
            print("  No existing aggregations schema found")
            
        if marts_tables:
            print(f"Found {len(marts_tables)} existing tables in marts schema:")
            for table_name, col_count in marts_tables:
                row_count_query = text(f"SELECT COUNT(*) FROM marts.{table_name}")
                row_count = conn.execute(row_count_query).scalar()
                print(f"  • {table_name}: {col_count} columns, {row_count:,} rows")
    
    # Step 3: Drop old schemas
    print("\n[3/4] Dropping old schemas...")
    confirm = input("⚠️  This will delete all data in aggregations and marts schemas. Continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("❌ Migration cancelled by user")
        sys.exit(0)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS aggregations CASCADE;"))
            conn.execute(text("DROP SCHEMA IF EXISTS marts CASCADE;"))
            conn.commit()
            print("✅ Old schemas dropped successfully")
    except Exception as e:
        print(f"❌ Failed to drop schemas: {e}")
        sys.exit(1)
    
    # Step 4: Run new schema SQL
    print("\n[4/4] Creating new marts schema (3 tables + metadata)...")
    sql_file = Path(__file__).parent / "database" / "schema" / "new_aggregations.sql"
    
    if not sql_file.exists():
        print(f"❌ SQL file not found: {sql_file}")
        sys.exit(1)
    
    sql_content = sql_file.read_text(encoding='utf-8')
    
    try:
        with engine.connect() as conn:
            # Execute the entire SQL file
            conn.execute(text(sql_content))
            conn.commit()
            print("✅ New schema created successfully")
    except Exception as e:
        print(f"❌ Failed to create new schema: {e}")
        sys.exit(1)
    
    # Verification
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    with engine.connect() as conn:
        # Check marts schema tables created
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'marts'
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result.fetchall()]
        
        print(f"\n✅ Created {len(tables)} tables in marts schema:")
        for table_name in tables:
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM marts.{table_name}")).scalar()
            print(f"  • {table_name}: {row_count:,} rows")
        
        # Check dataset registry
        if 'dataset_registry' in tables:
            print("\n📊 Dataset Registry:")
            result = conn.execute(text("""
                SELECT dataset_key, display_name, 
                       COALESCE(last_refreshed_at::text, 'Never') as last_refresh
                FROM marts.dataset_registry
                ORDER BY dataset_key;
            """))
            for dataset_key, display_name, last_refresh in result.fetchall():
                print(f"  • {dataset_key}: {display_name} (refreshed: {last_refresh})")
        
        # Check foreign keys
        result = conn.execute(text("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'marts'
            ORDER BY tc.table_name, kcu.column_name;
        """))
        fks = result.fetchall()
        print(f"\n🔗 Foreign Keys: {len(fks)} total")
        fk_summary = {}
        for table, col, fk_schema, fk_table, fk_col in fks:
            if table not in fk_summary:
                fk_summary[table] = 0
            fk_summary[table] += 1
        for table, count in fk_summary.items():
            print(f"  • {table}: {count} FKs")
        
        # Check indexes
        result = conn.execute(text("""
            SELECT 
                tablename,
                COUNT(*) as index_count
            FROM pg_indexes
            WHERE schemaname = 'marts'
              AND indexname NOT LIKE '%_pkey'
            GROUP BY tablename
            ORDER BY tablename;
        """))
        indexes = result.fetchall()
        print(f"\n📈 Custom Indexes:")
        for table, count in indexes:
            print(f"  • {table}: {count} indexes")
    
    print("\n" + "=" * 80)
    print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\nNew marts schema created with:")
    print("  • 3 metadata tables (dataset_registry, dataset_fields, dataset_refresh_log)")
    print("  • 3 data mart tables (mart_sales, mart_customers, mart_stores)")
    print("  • All data loaded from silkroute schema")
    print("\nNext steps:")
    print("  1. Update profiling service to use marts.dataset_registry")
    print("  2. Query mart_sales, mart_customers, mart_stores for dashboards")
    print("  3. Use dataset_fields.semantic_role for auto-chart suggestions")

if __name__ == "__main__":
    main()
