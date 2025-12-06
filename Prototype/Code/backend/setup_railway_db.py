"""
Setup Railway MySQL database with schema and data
"""
import pymysql
import os

# Railway connection details
DB_CONFIG = {
    'host': 'maglev.proxy.rlwy.net',
    'port': 56816,
    'user': 'root',
    'password': 'XuPJRAiYLDeuoFgYafHzAEIHakMrbZVM',
    'database': 'railway',
    'connect_timeout': 30,
    'read_timeout': 30,
    'write_timeout': 30
}

def execute_sql_file(cursor, filepath):
    """Execute SQL commands from a file"""
    print(f"\n📄 Executing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Remove comments at start of lines
    lines = sql_content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Keep the line if it's not a comment-only line
        if not line.strip().startswith('--'):
            cleaned_lines.append(line)
    sql_content = '\n'.join(cleaned_lines)
    
    # Split by semicolon
    statements = sql_content.split(';')
    
    executed = 0
    for statement in statements:
        stmt = statement.strip()
        if not stmt:
            continue
        # Skip DESCRIBE statements
        if stmt.upper().startswith('DESCRIBE'):
            continue
        
        try:
            cursor.execute(stmt)
            executed += 1
            if executed % 5 == 0:
                print(f"  ✓ {executed} statements executed")
        except Exception as e:
            error_msg = str(e)[:150]
            # Only show real errors, not DROP TABLE warnings
            if '1146' not in str(e):  # Table doesn't exist is OK for DROP
                print(f"  ⚠ Error: {error_msg}")
    
    print(f"  ✓ Total: {executed} statements executed successfully")

def main():
    print("🚀 Setting up Railway MySQL Database...\n")
    
    # Connect to database
    print("📡 Connecting to Railway MySQL...")
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    print("✓ Connected successfully!\n")
    
    # Execute schema file
    schema_file = 'database/fix_schema_railway.sql'
    if os.path.exists(schema_file):
        execute_sql_file(cursor, schema_file)
        conn.commit()
        print("✓ Schema created successfully!")
    else:
        print(f"⚠ Schema file not found: {schema_file}")
    
    # Check tables
    print("\n📋 Checking created tables...")
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"✓ Found {len(tables)} tables:")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Close connection
    cursor.close()
    conn.close()
    print("\n✅ Database setup complete!")
    print("\n📝 Next step: Run ETL pipeline to load data")
    print("   python database/full_etl_pipeline.py")

if __name__ == "__main__":
    main()
