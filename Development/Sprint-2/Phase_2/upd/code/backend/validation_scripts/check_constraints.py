from sqlalchemy import create_engine, inspect

DB_URL = 'postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres'
e = create_engine(DB_URL)
i = inspect(e)

tables = i.get_table_names(schema='silkroute')

print('='*70)
print('SILKROUTE SCHEMA - CONSTRAINTS ANALYSIS')
print('='*70)

no_pk_tables = []
no_fk_tables = []

for t in tables:
    print(f'\n### {t.upper()} ###')
    
    # Primary Keys
    pk = i.get_pk_constraint(t, schema='silkroute')
    pk_cols = pk.get('constrained_columns', []) if pk else []
    if pk_cols:
        print(f'  Primary Key: {pk_cols}')
    else:
        print('  Primary Key: *** NONE DEFINED ***')
        no_pk_tables.append(t)
    
    # Foreign Keys
    fks = i.get_foreign_keys(t, schema='silkroute')
    if fks:
        for fk in fks:
            print(f'  FK: {fk["constrained_columns"]} -> {fk["referred_table"]}({fk["referred_columns"]})')
    else:
        print('  Foreign Keys: NONE DEFINED')
        no_fk_tables.append(t)
    
    # Unique Constraints
    uniques = i.get_unique_constraints(t, schema='silkroute')
    if uniques:
        for u in uniques:
            print(f'  Unique: {u["column_names"]}')
    
    # Indexes
    indexes = i.get_indexes(t, schema='silkroute')
    if indexes:
        for idx in indexes:
            print(f'  Index: {idx["name"]} on {idx["column_names"]} (unique={idx["unique"]})')

print('\n')
print('='*70)
print('SUMMARY - MISSING CONSTRAINTS')
print('='*70)
print(f'\nTables WITHOUT Primary Key ({len(no_pk_tables)}):')
for t in no_pk_tables:
    print(f'  - {t}')

print(f'\nTables WITHOUT Foreign Keys ({len(no_fk_tables)}):')
for t in no_fk_tables:
    print(f'  - {t}')

# Expected relationships
print('\n')
print('='*70)
print('EXPECTED RELATIONSHIPS (based on column names)')
print('='*70)
expected = [
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

print('\nMissing FK definitions that SHOULD exist:')
for table, col, ref_table, ref_col in expected:
    print(f'  {table}.{col} --> {ref_table}.{ref_col}')
