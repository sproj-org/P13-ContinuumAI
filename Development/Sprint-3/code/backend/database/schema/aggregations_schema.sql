-- ================================================================
-- AGGREGATIONS SCHEMA (Analytical / Denormalized Layer)
-- 3 tables | 3 PKs | 8 FKs | 11 Indexes
-- Built on top of silkroute schema (source of truth)
-- ================================================================

CREATE SCHEMA IF NOT EXISTS aggregations;

-- ================================================================
-- 1. SALES DETAILED
-- Granularity: Transaction Line (item level)
-- Rows: 29,924
-- Joins: transaction_lines + transactions + product_variants_skus
--        + products + returns
-- Purpose: Profit margin analysis, returns detection,
--          price & discount impact
-- ================================================================

CREATE TABLE aggregations.sales_detailed (
    -- Identifiers
    line_id             VARCHAR(50) NOT NULL PRIMARY KEY,
    transaction_id      VARCHAR(50),
    transaction_ts      TIMESTAMP,           -- cast from text for trend analysis
    channel_type        VARCHAR(20),         -- 'online' | 'store'
    store_id            VARCHAR(50),         -- NULL for online orders (31.5%)
    customer_id         VARCHAR(50),
    sku_id              VARCHAR(50),

    -- Product metadata (denormalized from products)
    product_name        VARCHAR(255),
    brand               VARCHAR(100),
    category            VARCHAR(100),
    subcategory         VARCHAR(100),

    -- Pricing
    quantity            INTEGER,
    unit_price          NUMERIC(12, 2),
    discount            NUMERIC(12, 2),      -- percentage (0.00 – 0.45)
    base_price          NUMERIC(12, 2),      -- from product_variants_skus
    margin              NUMERIC(12, 2),      -- (line_total / quantity) - base_price

    -- Returns
    is_returned         BOOLEAN DEFAULT FALSE,
    return_reason       TEXT,                -- NULL for non-returned items (95.7%)

    -- Foreign Keys → silkroute
    CONSTRAINT fk_sd_line
        FOREIGN KEY (line_id) REFERENCES silkroute.transaction_lines(line_id),
    CONSTRAINT fk_sd_transaction
        FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id),
    CONSTRAINT fk_sd_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id),
    CONSTRAINT fk_sd_customer
        FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id),
    CONSTRAINT fk_sd_channel
        FOREIGN KEY (channel_type) REFERENCES silkroute.channels(channel_type),
    CONSTRAINT fk_sd_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id)
);


-- ================================================================
-- 2. STORE DAILY PERFORMANCE
-- Granularity: Store × Day
-- Rows: 2,096
-- Joins: transactions + stores + inventory_snapshots
-- Purpose: Store benchmarking, stock-out risk, underperformance
-- Note: stock_on_hand_eod is NULL 85.8% (inventory snapshots
--       don't cover every store-day)
-- ================================================================

CREATE TABLE aggregations.store_daily_performance (
    calendar_date       DATE         NOT NULL,
    store_id            VARCHAR(50)  NOT NULL,
    store_name          VARCHAR(100),
    city                VARCHAR(100),
    region              VARCHAR(100),

    -- Metrics
    daily_revenue       NUMERIC(15, 2),
    transaction_count   INTEGER,
    units_sold_count    INTEGER,
    avg_basket_value    NUMERIC(12, 2),
    stock_on_hand_eod   INTEGER,             -- NULL when no inventory snapshot

    -- Keys
    PRIMARY KEY (calendar_date, store_id),
    CONSTRAINT fk_sdp_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id)
);


-- ================================================================
-- 3. CUSTOMER 360
-- Granularity: Unique Customer
-- Rows: 2,500
-- Joins: customers + transactions + returns + transaction_lines
-- Purpose: RFM segmentation, return risk, churn analysis
-- Note: 80 customers (3.2%) have no transactions → NULLs in
--       spend/order/category/return fields
-- ================================================================

CREATE TABLE aggregations.customer_360 (
    customer_id             VARCHAR(50) NOT NULL PRIMARY KEY,
    segment                 VARCHAR(50),         -- from customers table
    city                    VARCHAR(100),
    first_purchase_date     DATE,
    last_purchase_date      DATE,
    total_lifetime_spend    NUMERIC(15, 2),
    total_order_count       INTEGER,
    preferred_category      VARCHAR(100),        -- most purchased category
    return_rate_pct         NUMERIC(5, 2),       -- (returned txns / total txns) * 100

    -- Foreign Key → silkroute
    CONSTRAINT fk_c360_customer
        FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id)
);


-- ================================================================
-- INDEXES (query performance)
-- ================================================================

-- sales_detailed
CREATE INDEX idx_sd_transaction   ON aggregations.sales_detailed(transaction_id);
CREATE INDEX idx_sd_sku           ON aggregations.sales_detailed(sku_id);
CREATE INDEX idx_sd_customer      ON aggregations.sales_detailed(customer_id);
CREATE INDEX idx_sd_store         ON aggregations.sales_detailed(store_id);
CREATE INDEX idx_sd_channel       ON aggregations.sales_detailed(channel_type);
CREATE INDEX idx_sd_category      ON aggregations.sales_detailed(category);
CREATE INDEX idx_sd_ts            ON aggregations.sales_detailed(transaction_ts);
CREATE INDEX idx_sd_returned      ON aggregations.sales_detailed(is_returned)
                                  WHERE is_returned = TRUE;   -- partial index

-- store_daily_performance
CREATE INDEX idx_sdp_store        ON aggregations.store_daily_performance(store_id);
CREATE INDEX idx_sdp_date         ON aggregations.store_daily_performance(calendar_date);

-- customer_360
CREATE INDEX idx_c360_segment     ON aggregations.customer_360(segment);
