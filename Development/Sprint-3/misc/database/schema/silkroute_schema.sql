-- ================================================================
-- SILKROUTE SCHEMA (Universal / Source-of-Truth Layer)
-- 13 tables | 10 PKs | 3 UNIQUEs | 12 FKs | 14 Indexes
-- Source: SilkRoute case study "Core Business Entities"
-- ================================================================

CREATE SCHEMA IF NOT EXISTS silkroute;

-- ================================================================
-- DIMENSION TABLES
-- ================================================================

-- Channels: Sales channel types (online / store)
-- Rows: 2
CREATE TABLE silkroute.channels (
    channel_type    TEXT NOT NULL PRIMARY KEY,   -- 'online' | 'store'
    channel_name    TEXT
);

-- Stores: Physical retail locations + DC pseudo-store S000
-- Rows: 7 (6 stores + 1 distribution center S000)
CREATE TABLE silkroute.stores (
    store_id        TEXT NOT NULL PRIMARY KEY,   -- e.g. 'S001', 'S000' (DC)
    store_name      TEXT,
    city            TEXT,
    region          TEXT,
    store_type      TEXT                         -- 'flagship', 'mall', 'distribution_center', etc.
);

-- Customers: Customer profiles
-- Rows: 2,500
CREATE TABLE silkroute.customers (
    customer_id         TEXT NOT NULL PRIMARY KEY,   -- e.g. 'C0001'
    segment             TEXT,                        -- 'Regular', 'Premium', 'New'
    city                TEXT,
    region              TEXT,
    first_purchase_date TEXT                          -- stored as text, cast to DATE when needed
);

-- Salespeople: Store sales staff
-- Rows: 26
CREATE TABLE silkroute.salespeople (
    salesperson_id  TEXT NOT NULL PRIMARY KEY,
    name            TEXT,
    role            TEXT,
    store_id        TEXT,

    CONSTRAINT fk_sp_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id)
);

-- Products: Product catalog (brand/category level)
-- Rows: 90
CREATE TABLE silkroute.products (
    product_id      TEXT NOT NULL PRIMARY KEY,
    product_name    TEXT,
    brand           TEXT,
    category        TEXT,
    subcategory     TEXT,
    status          TEXT                         -- 'active', 'discontinued'
);

-- Product Variants / SKUs: Size-color combinations of products
-- Rows: 150
CREATE TABLE silkroute.product_variants_skus (
    sku_id          TEXT NOT NULL PRIMARY KEY,
    product_id      TEXT,
    size            TEXT,
    color           TEXT,
    base_price      DOUBLE PRECISION,
    active_flag     BOOLEAN,

    CONSTRAINT fk_sku_product
        FOREIGN KEY (product_id) REFERENCES silkroute.products(product_id)
);

-- Variant Attributes: Flexible key-value attributes per SKU
-- Rows: 246
-- No PK per spec; composite UNIQUE enforced
CREATE TABLE silkroute.variant_attributes (
    sku_id              TEXT,
    attribute_name      TEXT,
    attribute_value     TEXT,
    attribute_type      TEXT,

    CONSTRAINT uq_variant_attr UNIQUE (sku_id, attribute_name),
    CONSTRAINT fk_attr_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id)
);

-- Category Attribute Definitions: Which attributes are expected per category
-- Rows: 11
-- No PK per spec; composite UNIQUE enforced
CREATE TABLE silkroute.category_attribute_definitions (
    category            TEXT,
    attribute_name      TEXT,
    attribute_type      TEXT,
    required_flag       BOOLEAN,

    CONSTRAINT uq_cat_attr_def UNIQUE (category, attribute_name)
);

-- Promotions: Product-level promotional campaigns
-- Rows: 12
CREATE TABLE silkroute.promotions (
    promo_id        TEXT NOT NULL PRIMARY KEY,
    product_id      TEXT,
    promo_type      TEXT,
    start_date      TEXT,
    end_date        TEXT,
    discount_type   TEXT,

    CONSTRAINT fk_promo_product
        FOREIGN KEY (product_id) REFERENCES silkroute.products(product_id)
);


-- ================================================================
-- FACT TABLES
-- ================================================================

-- Transactions: One row per purchase event
-- Rows: 11,402
-- NOTE: store_id & salesperson_id are NULL for online transactions
--       (conditional nullability — no FK enforced on these columns)
CREATE TABLE silkroute.transactions (
    transaction_id  TEXT NOT NULL PRIMARY KEY,
    transaction_ts  TEXT,                        -- timestamp stored as text
    channel_type    TEXT,                         -- 'online' | 'store'
    store_id        TEXT,                         -- NULL for online orders
    customer_id     TEXT,
    salesperson_id  TEXT,                         -- NULL for online orders
    payment_method  TEXT,
    total_amount    DOUBLE PRECISION,

    CONSTRAINT fk_txn_channel
        FOREIGN KEY (channel_type) REFERENCES silkroute.channels(channel_type),
    CONSTRAINT fk_txn_customer
        FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id)
);

-- Transaction Lines: One row per item in a transaction
-- Rows: 29,924
CREATE TABLE silkroute.transaction_lines (
    line_id         TEXT NOT NULL PRIMARY KEY,
    transaction_id  TEXT,
    sku_id          TEXT,
    quantity        BIGINT,
    unit_price      DOUBLE PRECISION,
    discount        DOUBLE PRECISION,            -- percentage (0.00 – 0.45)
    line_total      DOUBLE PRECISION,

    CONSTRAINT fk_line_txn
        FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id),
    CONSTRAINT fk_line_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id)
);

-- Inventory Snapshots: Daily stock levels per store per SKU
-- Rows: 55,650
-- No PK per spec; composite UNIQUE enforced
-- store_id includes DC pseudo-store 'S000'
CREATE TABLE silkroute.inventory_snapshots (
    snapshot_date   TEXT,
    store_id        TEXT,
    sku_id          TEXT,
    stock_on_hand   BIGINT,
    stock_on_order  BIGINT,

    CONSTRAINT uq_inv_snapshot UNIQUE (snapshot_date, store_id, sku_id),
    CONSTRAINT fk_inv_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id),
    CONSTRAINT fk_inv_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id)
);

-- Returns: Returned items linked to original transaction + SKU
-- Rows: 1,287
CREATE TABLE silkroute.returns (
    return_id       TEXT NOT NULL PRIMARY KEY,
    transaction_id  TEXT,
    sku_id          TEXT,
    return_reason   TEXT,
    refund_amount   DOUBLE PRECISION,

    CONSTRAINT fk_ret_txn
        FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id),
    CONSTRAINT fk_ret_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id)
);


-- ================================================================
-- INDEXES (query performance)
-- ================================================================

CREATE INDEX idx_txn_customer     ON silkroute.transactions(customer_id);
CREATE INDEX idx_txn_store        ON silkroute.transactions(store_id);
CREATE INDEX idx_txn_date         ON silkroute.transactions(transaction_ts);
CREATE INDEX idx_txn_channel      ON silkroute.transactions(channel_type);
CREATE INDEX idx_txn_salesperson  ON silkroute.transactions(salesperson_id);

CREATE INDEX idx_lines_txn        ON silkroute.transaction_lines(transaction_id);
CREATE INDEX idx_lines_sku        ON silkroute.transaction_lines(sku_id);

CREATE INDEX idx_ret_txn          ON silkroute.returns(transaction_id);
CREATE INDEX idx_ret_sku          ON silkroute.returns(sku_id);

CREATE INDEX idx_inv_sku          ON silkroute.inventory_snapshots(sku_id);
CREATE INDEX idx_inv_store        ON silkroute.inventory_snapshots(store_id);

CREATE INDEX idx_sku_product      ON silkroute.product_variants_skus(product_id);
CREATE INDEX idx_sp_store         ON silkroute.salespeople(store_id);
CREATE INDEX idx_promo_product    ON silkroute.promotions(product_id);
