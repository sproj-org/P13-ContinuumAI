"""
Check silkroute schema tables to understand structure
"""

from sqlalchemy import create_engine, text

DATABASE_URL = "add_your_db_url_here"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=" * 80)
    print("SILKROUTE SCHEMA TABLES")
    print("=" * 80)
    
    result = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'silkroute'
        ORDER BY table_name;
    """))
    
    tables = [row[0] for row in result.fetchall()]
    print(f"\nFound {len(tables)} tables:")
    for table in tables:
        print(f"  • {table}")
    
    print("\n" + "=" * 80)
    print("CHECKING FOR ORDER-RELATED TABLES")
    print("=" * 80)
    
    # Check for orders and order_items specifically
    for table_name in ['orders', 'order_items', 'order_details', 'sales']:
        result = conn.execute(text(f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'silkroute' AND table_name = '{table_name}';
        """))
        exists = result.scalar() > 0
        status = "✅ EXISTS" if exists else "❌ NOT FOUND"
        print(f"{status}: silkroute.{table_name}")
