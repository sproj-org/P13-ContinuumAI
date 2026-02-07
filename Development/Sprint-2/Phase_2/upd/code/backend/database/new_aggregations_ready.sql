-- ================================================================================
-- PRODUCTION-READY AGGREGATIONS SCHEMA (6 TABLES)
-- ================================================================================
-- This script creates the complete aggregations schema with:
--   • 3 metadata tables for auto-discovery (dataset_registry, dataset_fields, dataset_refresh_log)
--   • 3 data mart tables (mart_sales, mart_customers, mart_stores)
--   • All data loading from silkroute
--   • All foreign keys, check constraints, and indexes
-- ================================================================================

CREATE SCHEMA IF NOT EXISTS aggregations;

-- ================================================================================
-- TABLE 1: Dataset Registry (metadata for auto-discovery)
-- ================================================================================
CREATE TABLE IF NOT EXISTS aggregations.dataset_registry (
    dataset_key VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    grain_description TEXT,
    refresh_cadence VARCHAR(20) CHECK (refresh_cadence IN ('real-time', 'hourly', 'daily', 'weekly', 'monthly')),
    last_refreshed_at TIMESTAMPTZ,
    row_count_approx BIGINT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================================
-- TABLE 2: Dataset Fields (column metadata with semantic roles)
-- ================================================================================
CREATE TABLE IF NOT EXISTS aggregations.dataset_fields (
    field_id SERIAL PRIMARY KEY,
    dataset_key VARCHAR(50) REFERENCES aggregations.dataset_registry(dataset_key) ON DELETE CASCADE,
    column_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    semantic_role VARCHAR(20) CHECK (semantic_role IN ('dimension', 'measure', 'temporal', 'identifier')),
    data_type VARCHAR(50),
    description TEXT,
    is_visible BOOLEAN DEFAULT TRUE,
    sort_order INT,
    UNIQUE (dataset_key, column_name)
);

-- ================================================================================
-- TABLE 3: Dataset Refresh Log (ETL tracking)
-- ================================================================================
CREATE TABLE IF NOT EXISTS aggregations.dataset_refresh_log (
    run_id SERIAL PRIMARY KEY,
    dataset_key VARCHAR(50) REFERENCES aggregations.dataset_registry(dataset_key) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) CHECK (status IN ('running', 'success', 'failed')),
    rows_inserted BIGINT,
    rows_updated BIGINT,
    rows_deleted BIGINT,
    error_message TEXT
);

-- ================================================================================
-- TABLE 4: Mart Sales (line-level sales with promotions, returns, denormalized dims)
-- ================================================================================
CREATE TABLE IF NOT EXISTS aggregations.mart_sales (
    order_id VARCHAR(50),
    row_id BIGINT,
    order_date DATE,
    ship_date DATE,
    ship_mode VARCHAR(50),
    customer_id VARCHAR(50),
    customer_name VARCHAR(200),
    segment VARCHAR(50),
    country VARCHAR(100),
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    region VARCHAR(50),
    product_id VARCHAR(50),
    category VARCHAR(100),
    sub_category VARCHAR(100),
    product_name VARCHAR(500),
    sales NUMERIC(15, 4),
    quantity INT,
    discount NUMERIC(5, 4),
    profit NUMERIC(15, 4),
    -- Calculated fields
    discount_amount NUMERIC(15, 4),
    discounted_price NUMERIC(15, 4),
    cost_of_goods NUMERIC(15, 4),
    profit_margin NUMERIC(7, 4),
    is_returned BOOLEAN,
    PRIMARY KEY (order_id, row_id)
);

-- ================================================================================
-- TABLE 5: Mart Customers (lifetime customer metrics with RFM)
-- ================================================================================
CREATE TABLE IF NOT EXISTS aggregations.mart_customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(200),
    segment VARCHAR(50),
    country VARCHAR(100),
    city VARCHAR(100),
    state VARCHAR(100),
    region VARCHAR(50),
    -- Lifetime metrics
    first_order_date DATE,
    last_order_date DATE,
    total_orders INT,
    total_sales NUMERIC(15, 4),
    total_profit NUMERIC(15, 4),
    total_quantity INT,
    avg_order_value NUMERIC(15, 4),
    avg_profit_per_order NUMERIC(15, 4),
    lifetime_discount_pct NUMERIC(7, 4),
    -- RFM
    days_since_last_order INT,
    -- Product preferences
    top_category VARCHAR(100),
    top_sub_category VARCHAR(100),
    favorite_ship_mode VARCHAR(50),
    -- Returns
    return_count INT,
    return_rate NUMERIC(5, 4)
);

-- ================================================================================
-- TABLE 6: Mart Stores (lifetime store summary, not daily)
-- ================================================================================
CREATE TABLE IF NOT EXISTS aggregations.mart_stores (
    store_id VARCHAR(50) PRIMARY KEY,
    store_name VARCHAR(200),
    region VARCHAR(50),
    -- Lifetime metrics
    first_transaction_date DATE,
    last_transaction_date DATE,
    total_transactions INT,
    total_units_sold BIGINT,
    total_revenue NUMERIC(15, 4),
    avg_units_per_transaction NUMERIC(10, 2),
    avg_revenue_per_transaction NUMERIC(15, 4),
    -- Inventory health
    current_stock_value NUMERIC(15, 4),
    current_sku_count INT,
    days_since_last_inventory DATE
);

-- ================================================================================
-- DATA LOADING: mart_sales
-- ================================================================================
TRUNCATE TABLE aggregations.mart_sales;

INSERT INTO aggregations.mart_sales (
    order_id, row_id, order_date, ship_date, ship_mode,
    customer_id, customer_name, segment,
    country, city, state, postal_code, region,
    product_id, category, sub_category, product_name,
    sales, quantity, discount, profit,
    discount_amount, discounted_price, cost_of_goods, profit_margin, is_returned
)
SELECT 
    o.order_id,
    oi.row_id,
    o.order_date,
    o.ship_date,
    o.ship_mode,
    c.customer_id,
    c.customer_name,
    c.segment,
    l.country,
    l.city,
    l.state,
    l.postal_code,
    l.region,
    p.product_id,
    p.category,
    p.sub_category,
    p.product_name,
    oi.sales,
    oi.quantity,
    oi.discount,
    oi.profit,
    ROUND(oi.sales * oi.discount, 4) AS discount_amount,
    ROUND(oi.sales * (1 - oi.discount), 4) AS discounted_price,
    ROUND(oi.sales - oi.profit, 4) AS cost_of_goods,
    CASE WHEN oi.sales > 0 THEN ROUND(oi.profit / oi.sales, 4) ELSE 0 END AS profit_margin,
    COALESCE(r.returned, 'No') = 'Yes' AS is_returned
FROM silkroute.order_items oi
JOIN silkroute.orders o ON oi.order_id = o.order_id
JOIN silkroute.customers c ON o.customer_id = c.customer_id
JOIN silkroute.locations l ON c.location_id = l.location_id
JOIN silkroute.products p ON oi.product_id = p.product_id
LEFT JOIN silkroute.returns r ON oi.order_id = r.order_id AND oi.product_id = r.product_id;

-- ================================================================================
-- DATA LOADING: mart_customers
-- ================================================================================
TRUNCATE TABLE aggregations.mart_customers;

WITH customer_orders AS (
    SELECT 
        c.customer_id,
        c.customer_name,
        c.segment,
        l.country,
        l.city,
        l.state,
        l.region,
        MIN(o.order_date) AS first_order_date,
        MAX(o.order_date) AS last_order_date,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(oi.sales) AS total_sales,
        SUM(oi.profit) AS total_profit,
        SUM(oi.quantity) AS total_quantity,
        AVG(oi.sales) AS avg_order_value,
        AVG(oi.profit) AS avg_profit_per_order,
        CASE WHEN SUM(oi.sales) > 0 THEN SUM(oi.sales * oi.discount) / SUM(oi.sales) ELSE 0 END AS lifetime_discount_pct
    FROM silkroute.customers c
    JOIN silkroute.locations l ON c.location_id = l.location_id
    LEFT JOIN silkroute.orders o ON c.customer_id = o.customer_id
    LEFT JOIN silkroute.order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_id, c.customer_name, c.segment, l.country, l.city, l.state, l.region
),
customer_preferences AS (
    SELECT 
        c.customer_id,
        (SELECT p.category 
         FROM silkroute.order_items oi2
         JOIN silkroute.orders o2 ON oi2.order_id = o2.order_id
         JOIN silkroute.products p ON oi2.product_id = p.product_id
         WHERE o2.customer_id = c.customer_id
         GROUP BY p.category
         ORDER BY SUM(oi2.quantity) DESC
         LIMIT 1) AS top_category,
        (SELECT p.sub_category 
         FROM silkroute.order_items oi2
         JOIN silkroute.orders o2 ON oi2.order_id = o2.order_id
         JOIN silkroute.products p ON oi2.product_id = p.product_id
         WHERE o2.customer_id = c.customer_id
         GROUP BY p.sub_category
         ORDER BY SUM(oi2.quantity) DESC
         LIMIT 1) AS top_sub_category,
        (SELECT o2.ship_mode 
         FROM silkroute.orders o2
         WHERE o2.customer_id = c.customer_id
         GROUP BY o2.ship_mode
         ORDER BY COUNT(*) DESC
         LIMIT 1) AS favorite_ship_mode
    FROM silkroute.customers c
),
customer_returns AS (
    SELECT 
        o.customer_id,
        COUNT(*) AS return_count,
        COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT o.order_id), 0) AS return_rate
    FROM silkroute.returns r
    JOIN silkroute.orders o ON r.order_id = o.order_id
    GROUP BY o.customer_id
)
INSERT INTO aggregations.mart_customers (
    customer_id, customer_name, segment, country, city, state, region,
    first_order_date, last_order_date, total_orders, total_sales, total_profit, total_quantity,
    avg_order_value, avg_profit_per_order, lifetime_discount_pct, days_since_last_order,
    top_category, top_sub_category, favorite_ship_mode, return_count, return_rate
)
SELECT 
    co.customer_id,
    co.customer_name,
    co.segment,
    co.country,
    co.city,
    co.state,
    co.region,
    co.first_order_date,
    co.last_order_date,
    co.total_orders,
    ROUND(co.total_sales, 4),
    ROUND(co.total_profit, 4),
    co.total_quantity,
    ROUND(co.avg_order_value, 4),
    ROUND(co.avg_profit_per_order, 4),
    ROUND(co.lifetime_discount_pct, 4),
    CURRENT_DATE - co.last_order_date AS days_since_last_order,
    cp.top_category,
    cp.top_sub_category,
    cp.favorite_ship_mode,
    COALESCE(cr.return_count, 0),
    ROUND(COALESCE(cr.return_rate, 0), 4)
FROM customer_orders co
LEFT JOIN customer_preferences cp ON co.customer_id = cp.customer_id
LEFT JOIN customer_returns cr ON co.customer_id = cr.customer_id;

-- ================================================================================
-- DATA LOADING: mart_stores
-- ================================================================================
TRUNCATE TABLE aggregations.mart_stores;

WITH store_transactions AS (
    SELECT 
        s.store_id,
        s.store_name,
        s.region,
        MIN(t.transaction_date) AS first_transaction_date,
        MAX(t.transaction_date) AS last_transaction_date,
        COUNT(*) AS total_transactions,
        SUM(t.quantity_sold) AS total_units_sold,
        SUM(t.sale_price) AS total_revenue,
        AVG(t.quantity_sold) AS avg_units_per_transaction,
        AVG(t.sale_price) AS avg_revenue_per_transaction
    FROM silkroute.stores s
    LEFT JOIN silkroute.transactions t ON s.store_id = t.store_id
    GROUP BY s.store_id, s.store_name, s.region
),
store_inventory AS (
    SELECT 
        store_id,
        SUM(units_available * unit_cost) AS current_stock_value,
        COUNT(DISTINCT product_id) AS current_sku_count,
        MAX(snapshot_date) AS days_since_last_inventory
    FROM silkroute.inventory_snapshots
    GROUP BY store_id
)
INSERT INTO aggregations.mart_stores (
    store_id, store_name, region,
    first_transaction_date, last_transaction_date, total_transactions,
    total_units_sold, total_revenue, avg_units_per_transaction, avg_revenue_per_transaction,
    current_stock_value, current_sku_count, days_since_last_inventory
)
SELECT 
    st.store_id,
    st.store_name,
    st.region,
    st.first_transaction_date,
    st.last_transaction_date,
    st.total_transactions,
    st.total_units_sold,
    ROUND(st.total_revenue, 4),
    ROUND(st.avg_units_per_transaction, 2),
    ROUND(st.avg_revenue_per_transaction, 4),
    ROUND(COALESCE(si.current_stock_value, 0), 4),
    COALESCE(si.current_sku_count, 0),
    si.days_since_last_inventory
FROM store_transactions st
LEFT JOIN store_inventory si ON st.store_id = si.store_id;

-- ================================================================================
-- METADATA POPULATION
-- ================================================================================
INSERT INTO aggregations.dataset_registry (dataset_key, display_name, grain_description, refresh_cadence, last_refreshed_at, row_count_approx) VALUES
('sales', 'Sales Transactions', 'One row per order line (order_id + row_id)', 'daily', NOW(), (SELECT COUNT(*) FROM aggregations.mart_sales)),
('customers', 'Customer Lifetime Metrics', 'One row per customer with lifetime aggregates', 'daily', NOW(), (SELECT COUNT(*) FROM aggregations.mart_customers)),
('stores', 'Store Lifetime Summary', 'One row per store with lifetime metrics', 'daily', NOW(), (SELECT COUNT(*) FROM aggregations.mart_stores));

INSERT INTO aggregations.dataset_fields (dataset_key, column_name, display_name, semantic_role, data_type, is_visible, sort_order) VALUES
-- Sales dataset fields
('sales', 'order_date', 'Order Date', 'temporal', 'DATE', TRUE, 1),
('sales', 'customer_name', 'Customer', 'dimension', 'VARCHAR', TRUE, 2),
('sales', 'product_name', 'Product', 'dimension', 'VARCHAR', TRUE, 3),
('sales', 'category', 'Category', 'dimension', 'VARCHAR', TRUE, 4),
('sales', 'region', 'Region', 'dimension', 'VARCHAR', TRUE, 5),
('sales', 'sales', 'Sales Amount', 'measure', 'NUMERIC', TRUE, 6),
('sales', 'profit', 'Profit', 'measure', 'NUMERIC', TRUE, 7),
('sales', 'quantity', 'Quantity', 'measure', 'INT', TRUE, 8),
('sales', 'discount', 'Discount %', 'measure', 'NUMERIC', TRUE, 9),
('sales', 'profit_margin', 'Profit Margin', 'measure', 'NUMERIC', TRUE, 10),
('sales', 'is_returned', 'Is Returned', 'dimension', 'BOOLEAN', TRUE, 11),

-- Customers dataset fields
('customers', 'customer_name', 'Customer Name', 'dimension', 'VARCHAR', TRUE, 1),
('customers', 'segment', 'Segment', 'dimension', 'VARCHAR', TRUE, 2),
('customers', 'region', 'Region', 'dimension', 'VARCHAR', TRUE, 3),
('customers', 'total_sales', 'Lifetime Sales', 'measure', 'NUMERIC', TRUE, 4),
('customers', 'total_profit', 'Lifetime Profit', 'measure', 'NUMERIC', TRUE, 5),
('customers', 'total_orders', 'Total Orders', 'measure', 'INT', TRUE, 6),
('customers', 'avg_order_value', 'Avg Order Value', 'measure', 'NUMERIC', TRUE, 7),
('customers', 'first_order_date', 'First Order', 'temporal', 'DATE', TRUE, 8),
('customers', 'last_order_date', 'Last Order', 'temporal', 'DATE', TRUE, 9),
('customers', 'days_since_last_order', 'Days Since Last Order', 'measure', 'INT', TRUE, 10),

-- Stores dataset fields
('stores', 'store_name', 'Store Name', 'dimension', 'VARCHAR', TRUE, 1),
('stores', 'region', 'Region', 'dimension', 'VARCHAR', TRUE, 2),
('stores', 'total_revenue', 'Total Revenue', 'measure', 'NUMERIC', TRUE, 3),
('stores', 'total_units_sold', 'Total Units Sold', 'measure', 'BIGINT', TRUE, 4),
('stores', 'current_stock_value', 'Current Inventory Value', 'measure', 'NUMERIC', TRUE, 5);

-- ================================================================================
-- FOREIGN KEY CONSTRAINTS
-- ================================================================================
-- mart_sales foreign keys
ALTER TABLE aggregations.mart_sales
ADD CONSTRAINT fk_mart_sales_customer FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id),
ADD CONSTRAINT fk_mart_sales_product FOREIGN KEY (product_id) REFERENCES silkroute.products(product_id);

-- mart_customers foreign keys
ALTER TABLE aggregations.mart_customers
ADD CONSTRAINT fk_mart_customers_customer FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id);

-- mart_stores foreign keys
ALTER TABLE aggregations.mart_stores
ADD CONSTRAINT fk_mart_stores_store FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id);

-- ================================================================================
-- CHECK CONSTRAINTS (data quality)
-- ================================================================================
ALTER TABLE aggregations.mart_sales
ADD CONSTRAINT chk_sales_positive CHECK (sales >= 0),
ADD CONSTRAINT chk_quantity_positive CHECK (quantity >= 0),
ADD CONSTRAINT chk_discount_range CHECK (discount BETWEEN 0 AND 1);

ALTER TABLE aggregations.mart_customers
ADD CONSTRAINT chk_total_orders_positive CHECK (total_orders >= 0),
ADD CONSTRAINT chk_lifetime_sales_positive CHECK (total_sales >= 0);

ALTER TABLE aggregations.mart_stores
ADD CONSTRAINT chk_store_revenue_positive CHECK (total_revenue >= 0),
ADD CONSTRAINT chk_store_units_positive CHECK (total_units_sold >= 0);

-- ================================================================================
-- PERFORMANCE INDEXES
-- ================================================================================
-- mart_sales indexes
CREATE INDEX IF NOT EXISTS idx_mart_sales_order_date ON aggregations.mart_sales(order_date);
CREATE INDEX IF NOT EXISTS idx_mart_sales_customer ON aggregations.mart_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_mart_sales_product ON aggregations.mart_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_mart_sales_category ON aggregations.mart_sales(category);
CREATE INDEX IF NOT EXISTS idx_mart_sales_region ON aggregations.mart_sales(region);
CREATE INDEX IF NOT EXISTS idx_mart_sales_is_returned ON aggregations.mart_sales(is_returned);

-- mart_customers indexes
CREATE INDEX IF NOT EXISTS idx_mart_customers_segment ON aggregations.mart_customers(segment);
CREATE INDEX IF NOT EXISTS idx_mart_customers_region ON aggregations.mart_customers(region);
CREATE INDEX IF NOT EXISTS idx_mart_customers_total_sales ON aggregations.mart_customers(total_sales DESC);

-- mart_stores indexes
CREATE INDEX IF NOT EXISTS idx_mart_stores_region ON aggregations.mart_stores(region);
CREATE INDEX IF NOT EXISTS idx_mart_stores_revenue ON aggregations.mart_stores(total_revenue DESC);

-- ================================================================================
-- COMPLETION MESSAGE
-- ================================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ Aggregations schema created successfully with 6 tables:';
    RAISE NOTICE '   • dataset_registry (% rows)', (SELECT COUNT(*) FROM aggregations.dataset_registry);
    RAISE NOTICE '   • dataset_fields (% rows)', (SELECT COUNT(*) FROM aggregations.dataset_fields);
    RAISE NOTICE '   • dataset_refresh_log (% rows)', (SELECT COUNT(*) FROM aggregations.dataset_refresh_log);
    RAISE NOTICE '   • mart_sales (% rows)', (SELECT COUNT(*) FROM aggregations.mart_sales);
    RAISE NOTICE '   • mart_customers (% rows)', (SELECT COUNT(*) FROM aggregations.mart_customers);
    RAISE NOTICE '   • mart_stores (% rows)', (SELECT COUNT(*) FROM aggregations.mart_stores);
END $$;
