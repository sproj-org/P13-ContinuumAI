from sqlalchemy import create_engine, text

DB_URL = 'add_your_db_url_here'
engine = create_engine(DB_URL)

with engine.connect() as conn:

    # Check if aggregations schema exists
    result = conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'aggregations' ORDER BY table_name
    """)).fetchall()
    
    if not result:
        print("❌ 'aggregations' schema has NO tables or does not exist!")
        exit()

    tables = [r[0] for r in result]
    print('='*70)
    print('AGGREGATIONS SCHEMA - TABLES FOUND')
    print('='*70)
    for t in tables:
        print(f'  - {t}')

    # Column details per table
    print('\n')
    print('='*70)
    print('COLUMNS & DATA TYPES')
    print('='*70)

    for t in tables:
        cols = conn.execute(text(f"""
            SELECT column_name, data_type, is_nullable, character_maximum_length
            FROM information_schema.columns 
            WHERE table_schema = 'aggregations' AND table_name = '{t}'
            ORDER BY ordinal_position
        """)).fetchall()
        
        print(f'\n### {t.upper()} ({len(cols)} columns) ###')
        for c in cols:
            nullable = 'NULL' if c[2] == 'YES' else 'NOT NULL'
            length = f'({c[3]})' if c[3] else ''
            print(f'  {c[0]}: {c[1]}{length} {nullable}')

    # Existing constraints
    print('\n')
    print('='*70)
    print('EXISTING CONSTRAINTS')
    print('='*70)

    constraints = conn.execute(text("""
        SELECT tc.table_name, tc.constraint_type, tc.constraint_name,
               kcu.column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = 'aggregations'
        ORDER BY tc.table_name, tc.constraint_type
    """)).fetchall()

    if constraints:
        for c in constraints:
            print(f'  {c[0]}: {c[1]} on ({c[3]}) [{c[2]}]')
    else:
        print('  ❌ NO CONSTRAINTS DEFINED')

    # Row counts
    print('\n')
    print('='*70)
    print('ROW COUNTS')
    print('='*70)

    for t in tables:
        count = conn.execute(text(f"SELECT COUNT(*) FROM aggregations.{t}")).fetchone()[0]
        print(f'  {t}: {count} rows')

    # SANITY CHECKS
    print('\n')
    print('='*70)
    print('SANITY CHECK 1: Uniqueness of ID columns')
    print('='*70)

    id_checks = {
        'sales_detailed': 'line_id',
        'customer_360': 'customer_id',
    }

    for t, col in id_checks.items():
        if t in tables:
            result = conn.execute(text(f"""
                SELECT COUNT(*) AS total, COUNT(DISTINCT {col}) AS unique_vals,
                       COUNT(*) - COUNT({col}) AS nulls
                FROM aggregations.{t}
            """)).fetchone()
            total, unique, nulls = result
            dup = total - unique
            status = '✅ UNIQUE' if dup == 0 else f'❌ {dup} DUPLICATES'
            null_status = f' ⚠️ {nulls} NULLs' if nulls > 0 else ''
            print(f'  {t}.{col}: {total} rows, {unique} unique {status}{null_status}')

    # Composite uniqueness for store_daily_performance
    if 'store_daily_performance' in tables:
        result = conn.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT (calendar_date::text || store_id)) AS unique_combos
            FROM aggregations.store_daily_performance
        """)).fetchone()
        total, unique = result
        dup = total - unique
        status = '✅ UNIQUE' if dup == 0 else f'❌ {dup} DUPLICATES'
        print(f'  store_daily_performance.(calendar_date, store_id): {total} rows, {unique} unique {status}')

    print('\n')
    print('='*70)
    print('SANITY CHECK 2: Referential Integrity (do FK columns match silkroute?)')
    print('='*70)

    ref_checks = [
        ('sales_detailed', 'transaction_id', 'silkroute.transactions', 'transaction_id'),
        ('sales_detailed', 'customer_id', 'silkroute.customers', 'customer_id'),
        ('sales_detailed', 'sku_id', 'silkroute.product_variants_skus', 'sku_id'),
        ('sales_detailed', 'line_id', 'silkroute.transaction_lines', 'line_id'),
        ('customer_360', 'customer_id', 'silkroute.customers', 'customer_id'),
        ('store_daily_performance', 'store_id', 'silkroute.stores', 'store_id'),
    ]

    for agg_table, agg_col, src_table, src_col in ref_checks:
        if agg_table in tables:
            result = conn.execute(text(f"""
                SELECT COUNT(*) FROM aggregations.{agg_table} a
                LEFT JOIN {src_table} s ON a.{agg_col} = s.{src_col}
                WHERE s.{src_col} IS NULL AND a.{agg_col} IS NOT NULL
            """)).fetchone()
            orphans = result[0]
            status = '✅ Valid' if orphans == 0 else f'❌ {orphans} orphan records'
            print(f'  {agg_table}.{agg_col} -> {src_table}.{src_col}: {status}')

    print('\n')
    print('='*70)
    print('SANITY CHECK 3: NULL analysis on key columns')
    print('='*70)

    for t in tables:
        cols = conn.execute(text(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'aggregations' AND table_name = '{t}'
            ORDER BY ordinal_position
        """)).fetchall()

        print(f'\n  ### {t.upper()} ###')
        for c in cols:
            col_name = c[0]
            result = conn.execute(text(f"""
                SELECT COUNT(*) - COUNT({col_name}) AS null_count,
                       ROUND(100.0 * (COUNT(*) - COUNT({col_name})) / NULLIF(COUNT(*), 0), 2) AS null_pct
                FROM aggregations.{t}
            """)).fetchone()
            null_count, null_pct = result
            if null_count > 0:
                print(f'    {col_name}: {null_count} NULLs ({null_pct}%)')
            else:
                print(f'    {col_name}: ✅ No NULLs')

    print('\n')
    print('='*70)
    print('SANITY CHECK 4: Data range / basic stats on numeric columns')
    print('='*70)

    numeric_checks = {
        'sales_detailed': ['quantity', 'unit_price', 'discount', 'base_price', 'margin'],
        'store_daily_performance': ['daily_revenue', 'transaction_count', 'units_sold_count', 'avg_basket_value', 'stock_on_hand_eod'],
        'customer_360': ['total_lifetime_spend', 'total_order_count', 'return_rate_pct'],
    }

    for t, cols in numeric_checks.items():
        if t in tables:
            print(f'\n  ### {t.upper()} ###')
            for col in cols:
                try:
                    result = conn.execute(text(f"""
                        SELECT MIN({col}), MAX({col}), 
                               ROUND(AVG({col})::numeric, 2),
                               COUNT(CASE WHEN {col} < 0 THEN 1 END) AS negatives
                        FROM aggregations.{t}
                    """)).fetchone()
                    neg_warn = f' ⚠️ {result[3]} negative values' if result[3] > 0 else ''
                    print(f'    {col}: min={result[0]}, max={result[1]}, avg={result[2]}{neg_warn}')
                except:
                    print(f'    {col}: (could not compute)')
