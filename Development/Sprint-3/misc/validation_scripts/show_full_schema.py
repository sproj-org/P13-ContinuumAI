from sqlalchemy import create_engine, text

e = create_engine('add_your_db_url_here')

with e.connect() as c:
    r = c.execute(text("""
        SELECT
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END AS pk,
            CASE WHEN uq.column_name IS NOT NULL THEN 'UQ' ELSE '' END AS uq,
            CASE WHEN fk.column_name IS NOT NULL THEN fk.ref ELSE '' END AS fk_ref
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON t.table_name = c.table_name AND t.table_schema = c.table_schema
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'silkroute'
        ) pk ON pk.table_name = c.table_name AND pk.column_name = c.column_name
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'silkroute'
        ) uq ON uq.table_name = c.table_name AND uq.column_name = c.column_name
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name,
                   ccu.table_name || '.' || ccu.column_name AS ref
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name AND tc.constraint_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'silkroute'
        ) fk ON fk.table_name = c.table_name AND fk.column_name = c.column_name
        WHERE t.table_schema = 'silkroute' AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position
    """))
    rows = r.fetchall()

    cur_table = ''
    for row in rows:
        tbl, col, dtype, nullable, pk, uq, fk_ref = row
        if tbl != cur_table:
            if cur_table:
                print()
            print("=" * 95)
            print(f"  TABLE: silkroute.{tbl}")
            print("=" * 95)
            header = f"  {'Column':<30} {'Type':<20} {'Null':<6} {'Key':<5} {'FK Reference'}"
            print(header)
            print(f"  {'-'*30} {'-'*20} {'-'*6} {'-'*5} {'-'*30}")
            cur_table = tbl
        key = pk if pk else (uq if uq else '')
        print(f"  {col:<30} {dtype:<20} {nullable:<6} {key:<5} {fk_ref}")
