-- ==============================================================
-- ContinuumAI MVP - Physical Mart Tables (Sales / Customers / Stores)
-- Source schema: silkroute (Universal benchmark schema)
-- Generated: consolidated DDL + constraints + refresh/load statements
-- ==============================================================

BEGIN;

-- ----------------------------------------------------------------
-- 1) Schema
-- ----------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS marts;
-- ----------------------------------------------------------------
-- 1.1 Dataset Registry (for dataset picker / profiling / agents)
-- ----------------------------------------------------------------
-- A lightweight registry that allows the app to discover datasets,
-- understand their grain, time column, keys, and suggested default fields.

DROP TABLE IF EXISTS marts.dataset_fields CASCADE;
DROP TABLE IF EXISTS marts.dataset_registry CASCADE;
DROP TABLE IF EXISTS marts.dataset_refresh_log CASCADE;

CREATE TABLE marts.dataset_registry (
  dataset_key           TEXT PRIMARY KEY,         -- stable identifier e.g. 'sales', 'customers', 'stores'
  display_name          TEXT NOT NULL,
  schema_name           TEXT NOT NULL,
  object_name           TEXT NOT NULL,
  object_type           TEXT NOT NULL DEFAULT 'table',  -- table | view | materialized_view
  grain_description     TEXT NOT NULL,             -- e.g. '1 row per transaction line'
  time_column           TEXT NULL,                 -- e.g. 'transaction_ts' or 'sales_date' when applicable
  primary_keys          TEXT[] NOT NULL,           -- array of PK columns
  foreign_keys          JSONB NOT NULL DEFAULT '{}'::jsonb,  -- map: col -> 'schema.table(col)'
  default_dimensions    TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
  default_measures      TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
  description           TEXT NULL,

  refresh_strategy      TEXT NOT NULL DEFAULT 'truncate_insert', -- truncate_insert | incremental | none
  last_refreshed_at     TIMESTAMPTZ NULL,
  is_active             BOOLEAN NOT NULL DEFAULT TRUE,

  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT chk_dataset_key_nonempty CHECK (length(dataset_key) > 0),
  CONSTRAINT chk_object_type CHECK (object_type in ('table','view','materialized_view'))
);

CREATE INDEX idx_dataset_registry_active ON marts.dataset_registry(is_active);
CREATE INDEX idx_dataset_registry_object ON marts.dataset_registry(schema_name, object_name);

CREATE TABLE marts.dataset_fields (
  dataset_key        TEXT NOT NULL REFERENCES marts.dataset_registry(dataset_key) ON DELETE CASCADE,
  column_name        TEXT NOT NULL,
  data_type          TEXT NOT NULL,
  semantic_role      TEXT NOT NULL, -- id | time | dimension | measure | attribute
  is_nullable        BOOLEAN NOT NULL DEFAULT TRUE,
  description        TEXT NULL,
  example_expression TEXT NULL,      -- optional SQL snippet e.g. 'unit_price*quantity'
  PRIMARY KEY (dataset_key, column_name),
  CONSTRAINT chk_semantic_role CHECK (semantic_role in ('id','time','dimension','measure','attribute'))
);

CREATE INDEX idx_dataset_fields_role ON marts.dataset_fields(dataset_key, semantic_role);

CREATE TABLE marts.dataset_refresh_log (
  run_id           BIGSERIAL PRIMARY KEY,
  dataset_key      TEXT NOT NULL REFERENCES marts.dataset_registry(dataset_key) ON DELETE CASCADE,
  started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at      TIMESTAMPTZ NULL,
  status           TEXT NOT NULL DEFAULT 'started',  -- started|success|failed
  row_count        BIGINT NULL,
  message          TEXT NULL,
  CONSTRAINT chk_refresh_status CHECK (status in ('started','success','failed'))
);

-- seed registry entries (kept intentionally minimal but useful)
INSERT INTO marts.dataset_registry (
  dataset_key, display_name, schema_name, object_name, object_type,
  grain_description, time_column, primary_keys, foreign_keys,
  default_dimensions, default_measures, description
) VALUES
(
  'sales',
  'Sales (Transaction Line)',
  'marts', 'mart_sales', 'table',
  '1 row per transaction line (basket item) with denormalized customer/store/product context',
  'transaction_ts',
  ARRAY['line_id'],
  jsonb_build_object(
    'transaction_id','silkroute.transactions(transaction_id)',
    'customer_id','silkroute.customers(customer_id)',
    'store_id','silkroute.stores(store_id)',
    'salesperson_id','silkroute.salespeople(salesperson_id)',
    'sku_id','silkroute.product_variants_skus(sku_id)',
    'product_id','silkroute.products(product_id)',
    'channel_type','silkroute.channels(channel_type)'
  ),
  ARRAY['sales_date','channel_type','store_region','store_city','store_type','category','subcategory','brand','product_name','customer_segment','customer_region','customer_city','payment_method'],
  ARRAY['gross_line_amount','discount_amount','net_line_amount','margin_line_amount','quantity'],
  'Primary dataset for profiling, chart builder and agent reasoning. All time grains are computed by grouping on sales_date or transaction_ts.'
),
(
  'customers',
  'Customers (360)',
  'marts', 'mart_customers', 'table',
  '1 row per customer with RFM-style KPIs and return behavior',
  'last_purchase_date',
  ARRAY['customer_id'],
  jsonb_build_object(
    'customer_id','silkroute.customers(customer_id)'
  ),
  ARRAY['segment','region','city','preferred_channel','preferred_category','preferred_subcategory','preferred_brand'],
  ARRAY['orders','net_sales','avg_order_value','return_txn_rate','return_amount_rate','recency_days'],
  'Customer summary dataset for segmentation, churn heuristics and identifying high-value / high-return customers.'
),
(
  'stores',
  'Stores (360)',
  'marts', 'mart_stores', 'table',
  '1 row per store with performance KPIs and return rates',
  'last_sale_date',
  ARRAY['store_id'],
  jsonb_build_object(
    'store_id','silkroute.stores(store_id)'
  ),
  ARRAY['region','city','store_type'],
  ARRAY['orders','net_sales','avg_order_value','return_txn_rate','return_amount_rate','unique_customers'],
  'Store summary dataset for benchmarking and intervention flags.'
);

-- Optional (but helpful) field metadata for the most important columns

-- keep updated_at current
CREATE OR REPLACE FUNCTION marts.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dataset_registry_updated_at ON marts.dataset_registry;
CREATE TRIGGER trg_dataset_registry_updated_at
BEFORE UPDATE ON marts.dataset_registry
FOR EACH ROW EXECUTE FUNCTION marts.set_updated_at();

INSERT INTO marts.dataset_fields (dataset_key, column_name, data_type, semantic_role, is_nullable, description, example_expression) VALUES
-- sales ids/time
('sales','line_id','text','id',false,'Unique line item identifier',NULL),
('sales','transaction_id','text','id',false,'Order identifier',NULL),
('sales','transaction_ts','timestamp','time',true,'Transaction timestamp (cast from raw text)',NULL),
('sales','sales_date','date','time',true,'Calendar date derived from transaction_ts',NULL),
('sales','customer_id','text','id',false,'Customer identifier',NULL),
('sales','store_id','text','id',true,'Store identifier (NULL for online)',NULL),
('sales','sku_id','text','id',false,'SKU identifier',NULL),
('sales','product_id','text','id',false,'Product identifier',NULL),
('sales','channel_type','text','dimension',false,'Sales channel (store/online)',NULL),
-- sales measures
('sales','gross_line_amount','double precision','measure',false,'Unit price * quantity','unit_price * quantity'),
('sales','discount_amount','double precision','measure',false,'Gross * discount_pct (discount_pct is 0..1)','gross_line_amount * discount_pct'),
('sales','net_line_amount','double precision','measure',false,'Canonical net line total after discount','line_total'),
('sales','margin_line_amount','double precision','measure',false,'Net - (base_price*quantity)','net_line_amount - (base_price*quantity)'),
('sales','quantity','bigint','measure',false,'Units sold on the line',NULL),

-- customers keys/metrics
('customers','customer_id','text','id',false,'Customer identifier',NULL),
('customers','last_purchase_date','date','time',true,'Last observed purchase date',NULL),
('customers','orders','int','measure',false,'Distinct orders per customer',NULL),
('customers','net_sales','double precision','measure',false,'Total net sales per customer',NULL),
('customers','recency_days','int','measure',true,'Days since last purchase',NULL),

-- stores keys/metrics
('stores','store_id','text','id',false,'Store identifier',NULL),
('stores','orders','int','measure',false,'Distinct orders in store channel',NULL),
('stores','net_sales','double precision','measure',false,'Total net sales in store channel',NULL);



-- ----------------------------------------------------------------
-- 2) MART TABLES (DDL + constraints)
-- ----------------------------------------------------------------

-- ==============================================================
-- 2.1 marts.mart_sales  (transaction_line grain)
-- ==============================================================

DROP TABLE IF EXISTS marts.mart_sales CASCADE;

CREATE TABLE marts.mart_sales (
  -- keys
  line_id                 TEXT PRIMARY KEY,
  transaction_id          TEXT NOT NULL,
  sku_id                  TEXT NOT NULL,
  product_id              TEXT NOT NULL,
  customer_id             TEXT NOT NULL,

  -- denormalized customer
  customer_segment         TEXT NULL,
  customer_city            TEXT NULL,
  customer_region          TEXT NULL,

  -- transaction context
  transaction_ts          TIMESTAMP NULL,
  sales_date              DATE NULL,
  channel_type            TEXT NOT NULL,
  store_id                TEXT NULL,
  salesperson_id          TEXT NULL,
  payment_method          TEXT NULL,

  -- denormalized product / sku
  product_name            TEXT NULL,
  brand                   TEXT NULL,
  category                TEXT NULL,
  subcategory             TEXT NULL,
  product_status          TEXT NULL,
  size                    TEXT NULL,
  color                   TEXT NULL,
  base_price              DOUBLE PRECISION NULL,
  active_flag             BOOLEAN NULL,

  -- denormalized store
  store_name              TEXT NULL,
  store_city              TEXT NULL,
  store_region            TEXT NULL,
  store_type              TEXT NULL,

  -- denormalized salesperson
  salesperson_name        TEXT NULL,
  salesperson_role        TEXT NULL,

  -- measures (line)
  quantity                BIGINT NOT NULL,
  unit_price              DOUBLE PRECISION NOT NULL,
  discount_pct            DOUBLE PRECISION NULL, -- per silkroute_schema.sql: percentage (0.00–0.45)

  gross_line_amount       DOUBLE PRECISION NOT NULL,
  discount_amount         DOUBLE PRECISION NOT NULL,
  net_line_amount         DOUBLE PRECISION NOT NULL,
  margin_line_amount      DOUBLE PRECISION NOT NULL,

  -- returns enrichment
  is_returned             BOOLEAN NOT NULL DEFAULT FALSE,
  return_reason           TEXT NULL,
  refund_amount           DOUBLE PRECISION NOT NULL DEFAULT 0,

  -- promotions enrichment (inferred)
  promo_id                TEXT NULL,
  promo_type              TEXT NULL,
  promo_start_date        DATE NULL,
  promo_end_date          DATE NULL,
  promo_discount_type     TEXT NULL,

  -- -------- constraints (PK already defined) --------
  CONSTRAINT fk_ms_txn
    FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id),
  CONSTRAINT fk_ms_sku
    FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id),
  CONSTRAINT fk_ms_product
    FOREIGN KEY (product_id) REFERENCES silkroute.products(product_id),
  CONSTRAINT fk_ms_customer
    FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id),
  CONSTRAINT fk_ms_channel
    FOREIGN KEY (channel_type) REFERENCES silkroute.channels(channel_type),
  CONSTRAINT fk_ms_store
    FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id),
  CONSTRAINT fk_ms_salesperson
    FOREIGN KEY (salesperson_id) REFERENCES silkroute.salespeople(salesperson_id),

  -- Promotions are inferred by date window; promo_id is nullable and not a true FK.
  -- Returns are inferred by txn+sku; return_id not stored in mart to avoid ambiguity.

  -- basic data integrity
  CONSTRAINT chk_ms_nonneg
    CHECK (quantity >= 0 AND unit_price >= 0 AND gross_line_amount >= 0 AND discount_amount >= 0 AND net_line_amount >= 0),

  CONSTRAINT chk_ms_discount_pct
    CHECK (discount_pct IS NULL OR (discount_pct >= 0 AND discount_pct <= 1)),

  -- channel/store semantics (matches universal schema note: store_id & salesperson_id NULL for online)
  CONSTRAINT chk_ms_channel_store_nulls
    CHECK (
      (channel_type = 'online' AND store_id IS NULL AND salesperson_id IS NULL)
      OR
      (channel_type = 'store'  AND store_id IS NOT NULL)
    )
);

CREATE INDEX idx_ms_sales_date     ON marts.mart_sales(sales_date);
CREATE INDEX idx_ms_store          ON marts.mart_sales(store_id);
CREATE INDEX idx_ms_customer       ON marts.mart_sales(customer_id);
CREATE INDEX idx_ms_category        ON marts.mart_sales(category, subcategory);
CREATE INDEX idx_ms_txn            ON marts.mart_sales(transaction_id);
CREATE INDEX idx_ms_sku            ON marts.mart_sales(sku_id);


-- ==============================================================
-- 2.2 marts.mart_customers  (customer grain)
-- ==============================================================

DROP TABLE IF EXISTS marts.mart_customers CASCADE;

CREATE TABLE marts.mart_customers (
  customer_id           TEXT PRIMARY KEY,

  -- dims
  segment               TEXT NULL,
  city                  TEXT NULL,
  region                TEXT NULL,

  first_purchase_date   DATE NULL,
  last_purchase_date    DATE NULL,
  tenure_days           INT NULL,
  recency_days          INT NULL,

  -- KPIs
  orders                INT NOT NULL,
  line_items            INT NOT NULL,
  units                 BIGINT NOT NULL,
  gross_sales           DOUBLE PRECISION NOT NULL,
  discount_amount       DOUBLE PRECISION NOT NULL,
  net_sales             DOUBLE PRECISION NOT NULL,
  avg_order_value       DOUBLE PRECISION NOT NULL,
  avg_units_per_order   DOUBLE PRECISION NOT NULL,

  -- preferences
  preferred_channel     TEXT NULL,
  preferred_category    TEXT NULL,
  preferred_subcategory TEXT NULL,
  preferred_brand       TEXT NULL,

  -- returns
  returned_orders       INT NOT NULL,
  return_txn_rate       DOUBLE PRECISION NOT NULL,
  refund_amount         DOUBLE PRECISION NOT NULL,
  return_amount_rate    DOUBLE PRECISION NOT NULL,
  top_return_reason     TEXT NULL,

  CONSTRAINT fk_mc_customer
    FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id),

  CONSTRAINT chk_mc_rates
    CHECK (
      orders >= 0 AND line_items >= 0 AND units >= 0 AND gross_sales >= 0 AND discount_amount >= 0 AND net_sales >= 0
      AND return_txn_rate >= 0 AND return_txn_rate <= 1
      AND return_amount_rate >= 0
    )
);

CREATE INDEX idx_mc_segment         ON marts.mart_customers(segment);
CREATE INDEX idx_mc_region          ON marts.mart_customers(region);


-- ==============================================================
-- 2.3 marts.mart_stores  (store grain)
-- ==============================================================

DROP TABLE IF EXISTS marts.mart_stores CASCADE;

CREATE TABLE marts.mart_stores (
  store_id            TEXT PRIMARY KEY,

  -- dims
  store_name          TEXT NULL,
  store_type          TEXT NULL,
  city                TEXT NULL,
  region              TEXT NULL,

  -- lifetime span
  first_sale_date     DATE NULL,
  last_sale_date      DATE NULL,
  active_days         INT NOT NULL,

  -- KPIs
  orders              INT NOT NULL,
  unique_customers    INT NOT NULL,
  units               BIGINT NOT NULL,
  gross_sales         DOUBLE PRECISION NOT NULL,
  discount_amount     DOUBLE PRECISION NOT NULL,
  net_sales           DOUBLE PRECISION NOT NULL,
  avg_order_value     DOUBLE PRECISION NOT NULL,

  -- returns
  refund_amount       DOUBLE PRECISION NOT NULL,
  return_amount_rate  DOUBLE PRECISION NOT NULL,
  return_txn_rate     DOUBLE PRECISION NOT NULL,

  CONSTRAINT fk_ms_store
    FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id),

  CONSTRAINT chk_mst_rates
    CHECK (
      orders >= 0 AND unique_customers >= 0 AND units >= 0 AND gross_sales >= 0 AND discount_amount >= 0 AND net_sales >= 0
      AND return_txn_rate >= 0 AND return_txn_rate <= 1
      AND return_amount_rate >= 0
    )
);

CREATE INDEX idx_mst_region         ON marts.mart_stores(region);


-- ----------------------------------------------------------------
-- 3) REFRESH / LOAD (truncate + insert)  (run order: sales -> customers -> stores)
-- ----------------------------------------------------------------

-- ==============================================================
-- 3.1 Load marts.mart_sales
-- ==============================================================

TRUNCATE TABLE marts.mart_sales;

WITH tx AS (
  SELECT
    transaction_id,
    NULLIF(transaction_ts, '')::timestamp AS transaction_ts,
    NULLIF(transaction_ts, '')::timestamp::date AS sales_date,
    channel_type,
    store_id,
    customer_id,
    salesperson_id,
    payment_method
  FROM silkroute.transactions
),
returns_agg AS (
  SELECT
    transaction_id,
    sku_id,
    SUM(COALESCE(refund_amount, 0))::double precision AS refund_amount,
    -- true-ish "mode": reason with highest count; tie-breaker lexicographically
    (
      SELECT rr.return_reason
      FROM silkroute.returns rr
      WHERE rr.transaction_id = r.transaction_id AND rr.sku_id = r.sku_id AND rr.return_reason IS NOT NULL
      GROUP BY rr.return_reason
      ORDER BY COUNT(*) DESC, rr.return_reason ASC
      LIMIT 1
    ) AS return_reason
  FROM silkroute.returns r
  GROUP BY transaction_id, sku_id
),
promo_match AS (
  -- Infer promo per (product_id, sales_date). If multiple promos overlap, choose latest start_date.
  SELECT DISTINCT ON (product_id, sales_date)
    product_id,
    sales_date,
    promo_id,
    promo_type,
    NULLIF(start_date,'')::date AS promo_start_date,
    NULLIF(end_date,'')::date AS promo_end_date,
    discount_type AS promo_discount_type
  FROM (
    SELECT
      p.product_id,
      d.sales_date,
      p.promo_id,
      p.promo_type,
      p.start_date,
      p.end_date,
      p.discount_type,
      ROW_NUMBER() OVER (
        PARTITION BY p.product_id, d.sales_date
        ORDER BY NULLIF(p.start_date,'')::date DESC NULLS LAST
      ) AS rn
    FROM silkroute.promotions p
    JOIN (
      SELECT DISTINCT NULLIF(transaction_ts,'')::timestamp::date AS sales_date
      FROM silkroute.transactions
      WHERE transaction_ts IS NOT NULL AND transaction_ts <> ''
    ) d
      ON d.sales_date BETWEEN NULLIF(p.start_date,'')::date AND NULLIF(p.end_date,'')::date
  ) x
  WHERE rn = 1
)
INSERT INTO marts.mart_sales (
  line_id, transaction_id, sku_id, product_id, customer_id,
  customer_segment, customer_city, customer_region,
  transaction_ts, sales_date, channel_type, store_id, salesperson_id, payment_method,
  product_name, brand, category, subcategory, product_status, size, color, base_price, active_flag,
  store_name, store_city, store_region, store_type,
  salesperson_name, salesperson_role,
  quantity, unit_price, discount_pct,
  gross_line_amount, discount_amount, net_line_amount, margin_line_amount,
  is_returned, return_reason, refund_amount,
  promo_id, promo_type, promo_start_date, promo_end_date, promo_discount_type
)
SELECT
  tl.line_id,
  tl.transaction_id,
  tl.sku_id,
  sku.product_id,
  tx.customer_id,
  cu.segment AS customer_segment,
  cu.city AS customer_city,
  cu.region AS customer_region,

  tx.transaction_ts,
  tx.sales_date,
  tx.channel_type,
  tx.store_id,
  tx.salesperson_id,
  tx.payment_method,

  pr.product_name,
  pr.brand,
  pr.category,
  pr.subcategory,
  pr.status AS product_status,
  sku.size,
  sku.color,
  sku.base_price,
  sku.active_flag,

  st.store_name,
  st.city AS store_city,
  st.region AS store_region,
  st.store_type,

  sp.name AS salesperson_name,
  sp.role AS salesperson_role,

  COALESCE(tl.quantity, 0) AS quantity,
  COALESCE(tl.unit_price, 0) AS unit_price,
  tl.discount AS discount_pct,

  (COALESCE(tl.unit_price,0) * COALESCE(tl.quantity,0))::double precision AS gross_line_amount,
  ((COALESCE(tl.unit_price,0) * COALESCE(tl.quantity,0)) * COALESCE(tl.discount,0))::double precision AS discount_amount,
  COALESCE(tl.line_total, 0)::double precision AS net_line_amount,
  (COALESCE(tl.line_total,0) - (COALESCE(sku.base_price,0) * COALESCE(tl.quantity,0)))::double precision AS margin_line_amount,

  (COALESCE(ra.refund_amount,0) > 0) AS is_returned,
  ra.return_reason,
  COALESCE(ra.refund_amount,0)::double precision AS refund_amount,

  pm.promo_id,
  pm.promo_type,
  pm.promo_start_date,
  pm.promo_end_date,
  pm.promo_discount_type

FROM silkroute.transaction_lines tl
JOIN tx
  ON tx.transaction_id = tl.transaction_id
JOIN silkroute.product_variants_skus sku
  ON sku.sku_id = tl.sku_id
JOIN silkroute.products pr
  ON pr.product_id = sku.product_id
LEFT JOIN silkroute.customers cu
  ON cu.customer_id = tx.customer_id
LEFT JOIN silkroute.stores st
  ON st.store_id = tx.store_id
LEFT JOIN silkroute.salespeople sp
  ON sp.salesperson_id = tx.salesperson_id
LEFT JOIN returns_agg ra
  ON ra.transaction_id = tl.transaction_id AND ra.sku_id = tl.sku_id
LEFT JOIN promo_match pm
  ON pm.product_id = sku.product_id AND pm.sales_date = tx.sales_date;

-- refresh bookkeeping
UPDATE marts.dataset_registry SET last_refreshed_at = now() WHERE dataset_key = 'sales';
INSERT INTO marts.dataset_refresh_log(dataset_key, finished_at, status, row_count, message)
VALUES ('sales', now(), 'success', (SELECT COUNT(*) FROM marts.mart_sales), 'Loaded marts.mart_sales via truncate+insert');


-- ==============================================================
-- 3.2 Load marts.mart_customers (derived from marts.mart_sales)
-- ==============================================================

TRUNCATE TABLE marts.mart_customers;

WITH base AS (
  SELECT * FROM marts.mart_sales
),
agg AS (
  SELECT
    customer_id,
    MIN(sales_date) AS first_purchase_date_derived,
    MAX(sales_date) AS last_purchase_date,
    COUNT(DISTINCT transaction_id)::int AS orders,
    COUNT(*)::int AS line_items,
    SUM(quantity)::bigint AS units,
    SUM(gross_line_amount)::double precision AS gross_sales,
    SUM(discount_amount)::double precision AS discount_amount,
    SUM(net_line_amount)::double precision AS net_sales,
    COUNT(DISTINCT CASE WHEN is_returned THEN transaction_id END)::int AS returned_orders,
    SUM(refund_amount)::double precision AS refund_amount
  FROM base
  GROUP BY customer_id
),
pref_channel AS (
  SELECT DISTINCT ON (customer_id)
    customer_id,
    channel_type AS preferred_channel
  FROM (
    SELECT customer_id, channel_type, SUM(net_line_amount) AS s
    FROM base
    GROUP BY customer_id, channel_type
  ) x
  ORDER BY customer_id, s DESC
),
pref_cat AS (
  SELECT DISTINCT ON (customer_id)
    customer_id,
    category AS preferred_category,
    subcategory AS preferred_subcategory,
    brand AS preferred_brand
  FROM (
    SELECT customer_id, category, subcategory, brand, SUM(net_line_amount) AS s
    FROM base
    GROUP BY customer_id, category, subcategory, brand
  ) x
  ORDER BY customer_id, s DESC
),
top_reason AS (
  SELECT DISTINCT ON (customer_id)
    customer_id,
    return_reason AS top_return_reason
  FROM (
    SELECT customer_id, return_reason, COUNT(*) AS c
    FROM base
    WHERE is_returned AND return_reason IS NOT NULL
    GROUP BY customer_id, return_reason
  ) x
  ORDER BY customer_id, c DESC, top_return_reason ASC
)
INSERT INTO marts.mart_customers
SELECT
  a.customer_id,
  c.segment,
  c.city,
  c.region,
  COALESCE(NULLIF(c.first_purchase_date,'')::date, a.first_purchase_date_derived) AS first_purchase_date,
  a.last_purchase_date,
  (a.last_purchase_date - COALESCE(NULLIF(c.first_purchase_date,'')::date, a.first_purchase_date_derived))::int AS tenure_days,
  (CURRENT_DATE - a.last_purchase_date)::int AS recency_days,

  a.orders,
  a.line_items,
  a.units,
  a.gross_sales,
  a.discount_amount,
  a.net_sales,
  CASE WHEN a.orders = 0 THEN 0 ELSE (a.net_sales / a.orders) END AS avg_order_value,
  CASE WHEN a.orders = 0 THEN 0 ELSE (a.units::double precision / a.orders) END AS avg_units_per_order,

  pc.preferred_channel,
  pcat.preferred_category,
  pcat.preferred_subcategory,
  pcat.preferred_brand,

  a.returned_orders,
  CASE WHEN a.orders = 0 THEN 0 ELSE (a.returned_orders::double precision / a.orders) END AS return_txn_rate,
  a.refund_amount,
  CASE WHEN a.net_sales = 0 THEN 0 ELSE (a.refund_amount / a.net_sales) END AS return_amount_rate,
  tr.top_return_reason
FROM agg a
LEFT JOIN silkroute.customers c
  ON c.customer_id = a.customer_id
LEFT JOIN pref_channel pc
  ON pc.customer_id = a.customer_id
LEFT JOIN pref_cat pcat
  ON pcat.customer_id = a.customer_id
LEFT JOIN top_reason tr
  ON tr.customer_id = a.customer_id;


-- ==============================================================
-- 3.3 Load marts.mart_stores (derived from marts.mart_sales)
-- ==============================================================

TRUNCATE TABLE marts.mart_stores;

WITH base AS (
  SELECT *
  FROM marts.mart_sales
  WHERE channel_type = 'store' AND store_id IS NOT NULL
),
agg AS (
  SELECT
    store_id,
    MIN(sales_date) AS first_sale_date,
    MAX(sales_date) AS last_sale_date,
    COUNT(DISTINCT sales_date)::int AS active_days,
    COUNT(DISTINCT transaction_id)::int AS orders,
    COUNT(DISTINCT customer_id)::int AS unique_customers,
    SUM(quantity)::bigint AS units,
    SUM(gross_line_amount)::double precision AS gross_sales,
    SUM(discount_amount)::double precision AS discount_amount,
    SUM(net_line_amount)::double precision AS net_sales,
    SUM(refund_amount)::double precision AS refund_amount,
    COUNT(DISTINCT CASE WHEN is_returned THEN transaction_id END)::int AS returned_orders
  FROM base
  GROUP BY store_id
)
INSERT INTO marts.mart_stores
SELECT
  a.store_id,
  s.store_name,
  s.store_type,
  s.city,
  s.region,

  a.first_sale_date,
  a.last_sale_date,
  a.active_days,
  a.orders,
  a.unique_customers,
  a.units,
  a.gross_sales,
  a.discount_amount,
  a.net_sales,
  CASE WHEN a.orders = 0 THEN 0 ELSE (a.net_sales / a.orders) END AS avg_order_value,

  a.refund_amount,
  CASE WHEN a.net_sales = 0 THEN 0 ELSE (a.refund_amount / a.net_sales) END AS return_amount_rate,
  CASE WHEN a.orders = 0 THEN 0 ELSE (a.returned_orders::double precision / a.orders) END AS return_txn_rate
FROM agg a
JOIN silkroute.stores s
  ON s.store_id = a.store_id;


-- ----------------------------------------------------------------
-- 4) Optional grants (uncomment if FE reads marts via authenticated role)
-- ----------------------------------------------------------------
-- GRANT USAGE ON SCHEMA marts TO authenticated;
-- GRANT SELECT ON ALL TABLES IN SCHEMA marts TO authenticated;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO authenticated;


-- ----------------------------------------------------------------
-- 4) Optional permissions (enable if you want non-service roles to read marts)
-- ----------------------------------------------------------------
-- Uncomment as needed:
-- GRANT USAGE ON SCHEMA marts TO anon, authenticated;
-- GRANT SELECT ON ALL TABLES IN SCHEMA marts TO anon, authenticated;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO anon, authenticated;

COMMIT;
