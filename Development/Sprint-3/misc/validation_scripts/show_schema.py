from sqlalchemy import create_engine, inspect

DB_URL = "postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
e = create_engine(DB_URL)
i = inspect(e)

tables = i.get_table_names(schema='silkroute')

print('='*70)
print('SILKROUTE SCHEMA - TABLE ATTRIBUTES')
print('='*70)

for t in tables:
    print(f'\n### {t.upper()} ###')
    cols = i.get_columns(t, schema='silkroute')
    pk = i.get_pk_constraint(t, schema='silkroute')
    pk_cols = pk.get('constrained_columns', []) if pk else []
    for c in cols:
        pk_mark = ' [PK]' if c['name'] in pk_cols else ''
        nullable = '' if c['nullable'] else ' NOT NULL'
        print(f"  {c['name']}: {c['type']}{pk_mark}{nullable}")

print('\n')
print('='*70)
print('SILKROUTE SCHEMA - FOREIGN KEY RELATIONSHIPS')
print('='*70)

for t in tables:
    fks = i.get_foreign_keys(t, schema='silkroute')
    if fks:
        print(f'\n### {t.upper()} ###')
        for fk in fks:
            local_cols = ', '.join(fk['constrained_columns'])
            ref_table = fk['referred_table']
            ref_schema = fk.get('referred_schema', 'silkroute')
            ref_cols = ', '.join(fk['referred_columns'])
            print(f"  {local_cols} --> {ref_schema}.{ref_table}({ref_cols})")

print('\n')
print('='*70)
print('RELATIONSHIP SUMMARY')
print('='*70)
print('\nTable Dependencies:')
for t in tables:
    fks = i.get_foreign_keys(t, schema='silkroute')
    if fks:
        refs = [fk['referred_table'] for fk in fks]
        print(f"  {t} depends on: {', '.join(refs)}")
