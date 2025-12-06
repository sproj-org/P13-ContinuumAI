"""
Import CSV data to Railway MySQL database
"""
import pymysql
import csv
import os
from datetime import datetime

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

def parse_date(date_str):
    """Parse date from MM/DD/YYYY format to YYYY-MM-DD"""
    if not date_str or date_str.strip() == '':
        return None
    try:
        dt = datetime.strptime(date_str, '%m/%d/%Y')
        return dt.strftime('%Y-%m-%d')
    except:
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except:
            return None

def import_csv(cursor, table_name, csv_file, date_columns=None):
    """Import CSV file to database table"""
    print(f"\n📥 Importing {csv_file} to {table_name}...")
    
    if not os.path.exists(csv_file):
        print(f"  ⚠ File not found: {csv_file}")
        return
    
    date_columns = date_columns or []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        if not rows:
            print(f"  ⚠ No data in file")
            return
        
        # Get column names from CSV
        columns = list(rows[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        
        # Use INSERT IGNORE to skip duplicates
        sql = f"INSERT IGNORE INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        # Insert in batches
        batch_size = 500
        total = len(rows)
        inserted = 0
        
        for i in range(0, total, batch_size):
            batch = rows[i:i+batch_size]
            values = []
            for row in batch:
                # Convert dates
                row_values = []
                for col in columns:
                    val = row[col]
                    if col in date_columns:
                        val = parse_date(val)
                    row_values.append(val)
                values.append(tuple(row_values))
            
            cursor.executemany(sql, values)
            inserted += cursor.rowcount
            print(f"  ✓ Imported {min(i+batch_size, total)}/{total} rows ({inserted} inserted)")
    
    print(f"  ✅ {inserted} rows imported to {table_name} (skipped {total - inserted} duplicates)")

def main():
    print("🚀 Importing data to Railway MySQL...\n")
    
    # Connect
    print("📡 Connecting to Railway MySQL...")
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    print("✓ Connected!\n")
    
    # Data directory
    data_dir = 'database/data/processed'
    
    # Import order (respecting foreign keys)
    imports = [
        ('Regions', f'{data_dir}/regions.csv', []),
        ('Products', f'{data_dir}/products.csv', []),
        ('Customers', f'{data_dir}/customers.csv', []),
        ('SalesReps', f'{data_dir}/salesreps.csv', ['hire_date']),
        ('SalesTransactions', f'{data_dir}/sales_transactions_enriched.csv', ['order_date']),
        ('Opportunities', f'{data_dir}/opportunities.csv', ['created_date', 'close_date']),
    ]
    
    for table_name, csv_file, date_cols in imports:
        try:
            import_csv(cursor, table_name, csv_file, date_cols)
            conn.commit()
        except Exception as e:
            print(f"  ❌ Error: {e}")
            conn.rollback()
    
    # Verify data
    print("\n📊 Verifying imported data...")
    for table_name, _, _ in imports:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  ✓ {table_name}: {count} rows")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Data import complete!")
    print("\n📝 Next step: Start the backend server")
    print("   .\\start_server.ps1")

if __name__ == "__main__":
    main()
