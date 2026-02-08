from sqlalchemy import create_engine, text

e = create_engine('add_your_db_url_here')

with e.connect() as c:
    print('=== DISCOUNT ANALYSIS ===')
    r = c.execute(text("""
        SELECT MIN(discount), MAX(discount), ROUND(AVG(discount)::numeric,4),
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY discount)
        FROM aggregations.sales_detailed
    """)).fetchone()
    print(f'  min={r[0]}, max={r[1]}, avg={r[2]}, median={r[3]}')

    print('\n=== SAMPLE ROWS ===')
    rows = c.execute(text("""
        SELECT s.line_id, s.unit_price, s.discount, s.quantity, s.base_price,
               tl.line_total,
               ROUND((s.unit_price * (1 - s.discount) * s.quantity)::numeric, 2) as calc_pct,
               ROUND(((s.unit_price - s.discount) * s.quantity)::numeric, 2) as calc_flat,
               ROUND((s.unit_price * s.quantity)::numeric, 2) as no_disc
        FROM aggregations.sales_detailed s
        JOIN silkroute.transaction_lines tl ON s.line_id = tl.line_id
        LIMIT 15
    """)).fetchall()

    for r in rows:
        pct_match = 'YES' if abs(float(r[5]) - float(r[6])) < 1 else 'NO'
        flat_match = 'YES' if abs(float(r[5]) - float(r[7])) < 1 else 'NO'
        print(f'  {r[0]}: price={r[1]}, disc={r[2]}, qty={r[3]}, base={r[4]}')
        print(f'         line_total={r[5]}, calc_pct={r[6]} (match={pct_match}), calc_flat={r[7]} (match={flat_match})')

    print('\n=== MATCH RATE ===')
    r = c.execute(text("""
        SELECT 
            COUNT(CASE WHEN ABS(tl.line_total - ROUND((s.unit_price * (1 - s.discount) * s.quantity)::numeric, 2)) < 1 THEN 1 END) as pct_matches,
            COUNT(CASE WHEN ABS(tl.line_total - ROUND(((s.unit_price - s.discount) * s.quantity)::numeric, 2)) < 1 THEN 1 END) as flat_matches,
            COUNT(*) as total
        FROM aggregations.sales_detailed s
        JOIN silkroute.transaction_lines tl ON s.line_id = tl.line_id
    """)).fetchone()
    print(f'  Percentage formula matches: {r[0]}/{r[2]} ({round(100*r[0]/r[2],1)}%)')
    print(f'  Flat formula matches:       {r[1]}/{r[2]} ({round(100*r[1]/r[2],1)}%)')

    print('\n=== WHAT IS MARGIN SUPPOSED TO BE? ===')
    print('  Option A: (unit_price - discount) - base_price           [discount as flat amount]')
    print('  Option B: (unit_price * (1 - discount)) - base_price     [discount as percentage]')
    print('  Option C: (line_total / quantity) - base_price            [use actual line_total]')

    r = c.execute(text("""
        SELECT 
            ROUND(AVG((s.unit_price - s.discount) - s.base_price)::numeric, 2) as avg_A,
            COUNT(CASE WHEN (s.unit_price - s.discount) - s.base_price < 0 THEN 1 END) as neg_A,
            ROUND(AVG((s.unit_price * (1 - s.discount)) - s.base_price)::numeric, 2) as avg_B,
            COUNT(CASE WHEN (s.unit_price * (1 - s.discount)) - s.base_price < 0 THEN 1 END) as neg_B,
            ROUND(AVG((tl.line_total / NULLIF(s.quantity, 0)) - s.base_price)::numeric, 2) as avg_C,
            COUNT(CASE WHEN (tl.line_total / NULLIF(s.quantity, 0)) - s.base_price < 0 THEN 1 END) as neg_C
        FROM aggregations.sales_detailed s
        JOIN silkroute.transaction_lines tl ON s.line_id = tl.line_id
    """)).fetchone()
    print(f'  Option A: avg_margin={r[0]}, negatives={r[1]}')
    print(f'  Option B: avg_margin={r[2]}, negatives={r[3]}')
    print(f'  Option C: avg_margin={r[4]}, negatives={r[5]}')
