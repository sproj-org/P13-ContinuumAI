from sqlalchemy import create_engine, text

DB_URL = 'add_your_db_url_here'
engine = create_engine(DB_URL)

with engine.connect() as conn:

    print('='*70)
    print('1. UNIQUENESS CHECK (Do ID columns act as natural Primary Keys?)')
    print('='*70)

    pk_checks = [
        ('customers', 'customer_id'),
        ('stores', 'store_id'),
        ('channels', 'channel_type'),
        ('salespeople', 'salesperson_id'),
        ('products', 'product_id'),
        ('product_variants_skus', 'sku_id'),
        ('transactions', 'transaction_id'),
        ('transaction_lines', 'line_id'),
        ('returns', 'return_id'),
        ('promotions', 'promo_id'),
    ]

    for table, col in pk_checks:
        result = conn.execute(text(f"""
            SELECT 
                COUNT(*) AS total_rows,
                COUNT(DISTINCT {col}) AS unique_values,
                COUNT(*) - COUNT({col}) AS null_count
            FROM silkroute.{table}
        """)).fetchone()
        
        total, unique, nulls = result
        is_unique = '✅ UNIQUE' if total == unique else f'❌ DUPLICATES ({total - unique})'
        has_nulls = '' if nulls == 0 else f' ⚠️ {nulls} NULLs'
        print(f'  {table}.{col}: {total} rows, {unique} unique {is_unique}{has_nulls}')

    print('\n')
    print('='*70)
    print('2. REFERENTIAL INTEGRITY (Do FK columns reference valid parent rows?)')
    print('='*70)

    fk_checks = [
        ('transactions', 'store_id', 'stores', 'store_id'),
        ('transactions', 'customer_id', 'customers', 'customer_id'),
        ('transactions', 'salesperson_id', 'salespeople', 'salesperson_id'),
        ('transactions', 'channel_type', 'channels', 'channel_type'),
        ('transaction_lines', 'transaction_id', 'transactions', 'transaction_id'),
        ('transaction_lines', 'sku_id', 'product_variants_skus', 'sku_id'),
        ('returns', 'transaction_id', 'transactions', 'transaction_id'),
        ('returns', 'sku_id', 'product_variants_skus', 'sku_id'),
        ('inventory_snapshots', 'store_id', 'stores', 'store_id'),
        ('inventory_snapshots', 'sku_id', 'product_variants_skus', 'sku_id'),
        ('salespeople', 'store_id', 'stores', 'store_id'),
        ('product_variants_skus', 'product_id', 'products', 'product_id'),
        ('variant_attributes', 'sku_id', 'product_variants_skus', 'sku_id'),
        ('promotions', 'product_id', 'products', 'product_id'),
    ]

    for child_table, child_col, parent_table, parent_col in fk_checks:
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM silkroute.{child_table} c
            LEFT JOIN silkroute.{parent_table} p ON c.{child_col} = p.{parent_col}
            WHERE p.{parent_col} IS NULL AND c.{child_col} IS NOT NULL
        """)).fetchone()
        
        orphans = result[0]
        status = '✅ Valid' if orphans == 0 else f'❌ {orphans} orphan records'
        print(f'  {child_table}.{child_col} -> {parent_table}.{parent_col}: {status}')

    print('\n')
    print('='*70)
    print('3. ROW COUNTS')
    print('='*70)

    tables = ['customers', 'stores', 'channels', 'salespeople', 'products',
              'product_variants_skus', 'variant_attributes', 'category_attribute_definitions',
              'promotions', 'transactions', 'transaction_lines', 'returns', 'inventory_snapshots']

    for t in tables:
        result = conn.execute(text(f"SELECT COUNT(*) FROM silkroute.{t}")).fetchone()
        print(f'  {t}: {result[0]} rows')

    print('\n')
    print('='*70)
    print('4. SAMPLE DATA (first 3 rows per table)')
    print('='*70)

    for t in tables:
        result = conn.execute(text(f"SELECT * FROM silkroute.{t} LIMIT 3"))
        cols = result.keys()
        rows = result.fetchall()
        print(f'\n  ### {t.upper()} ###')
        print(f'  Columns: {list(cols)}')
        for row in rows:
            print(f'  {dict(zip(cols, row))}')
