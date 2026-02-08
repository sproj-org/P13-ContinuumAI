-- ================================================================
-- MIGRATION: Enforce Constraints on silkroute (Universal Schema)
-- Aligned with TARGET_SCHEMAS from 00_schema_validation.ipynb
-- Run this BEFORE populating aggregations
-- ================================================================

BEGIN;

-- ================================================================
-- PHASE 0: DATA FIXES (prerequisites for constraint enforcement)
-- ================================================================

-- Insert DC pseudo-store 'S000' so inventory_snapshots FK is valid.
-- The notebook spec notes: "store_id can include DC pseudo-store S000"
INSERT INTO silkroute.stores (store_id, store_name, city, region, store_type)
VALUES ('S000', 'Distribution Center', 'N/A', 'N/A', 'distribution_center')
ON CONFLICT DO NOTHING;


-- ================================================================
-- PHASE 1: PRIMARY KEYS
-- (from TARGET_SCHEMAS — only tables with explicit primary_key)
-- ================================================================

-- Dimension Tables
ALTER TABLE silkroute.channels          ADD PRIMARY KEY (channel_type);
ALTER TABLE silkroute.stores            ADD PRIMARY KEY (store_id);
ALTER TABLE silkroute.customers         ADD PRIMARY KEY (customer_id);
ALTER TABLE silkroute.salespeople       ADD PRIMARY KEY (salesperson_id);
ALTER TABLE silkroute.products          ADD PRIMARY KEY (product_id);
ALTER TABLE silkroute.product_variants_skus ADD PRIMARY KEY (sku_id);
ALTER TABLE silkroute.promotions        ADD PRIMARY KEY (promo_id);

-- Fact Tables
ALTER TABLE silkroute.transactions      ADD PRIMARY KEY (transaction_id);
ALTER TABLE silkroute.transaction_lines  ADD PRIMARY KEY (line_id);
ALTER TABLE silkroute.returns           ADD PRIMARY KEY (return_id);

-- Tables with primary_key: None in spec but typical composite keys:
--   variant_attributes: (sku_id, attribute_name) typical but not required by doc
--   category_attribute_definitions: (category, attribute_name) typical
--   inventory_snapshots: (snapshot_date, store_id, sku_id) typical
-- Adding these as UNIQUE constraints (data is clean, enforces integrity
-- without claiming doc-level PK status):
ALTER TABLE silkroute.variant_attributes
    ADD CONSTRAINT uq_variant_attr UNIQUE (sku_id, attribute_name);

ALTER TABLE silkroute.category_attribute_definitions
    ADD CONSTRAINT uq_cat_attr_def UNIQUE (category, attribute_name);

ALTER TABLE silkroute.inventory_snapshots
    ADD CONSTRAINT uq_inv_snapshot UNIQUE (snapshot_date, store_id, sku_id);


-- ================================================================
-- PHASE 2: FOREIGN KEYS
-- (exactly matching TARGET_SCHEMAS foreign_keys definitions)
-- ================================================================

-- salespeople.store_id → stores.store_id
ALTER TABLE silkroute.salespeople
    ADD CONSTRAINT fk_sp_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id);

-- product_variants_skus.product_id → products.product_id
ALTER TABLE silkroute.product_variants_skus
    ADD CONSTRAINT fk_sku_product
        FOREIGN KEY (product_id) REFERENCES silkroute.products(product_id);

-- variant_attributes.sku_id → product_variants_skus.sku_id
ALTER TABLE silkroute.variant_attributes
    ADD CONSTRAINT fk_attr_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id);

-- promotions.product_id → products.product_id
ALTER TABLE silkroute.promotions
    ADD CONSTRAINT fk_promo_product
        FOREIGN KEY (product_id) REFERENCES silkroute.products(product_id);

-- transactions.channel_type → channels.channel_type
ALTER TABLE silkroute.transactions
    ADD CONSTRAINT fk_txn_channel
        FOREIGN KEY (channel_type) REFERENCES silkroute.channels(channel_type);

-- transactions.customer_id → customers.customer_id
ALTER TABLE silkroute.transactions
    ADD CONSTRAINT fk_txn_customer
        FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id);

-- NOTE: transactions.store_id and transactions.salesperson_id are NOT FK-constrained
-- per the notebook spec (conditional nullability: NULL for online, required for store).
-- The spec comments them out of the foreign_keys list.

-- transaction_lines.transaction_id → transactions.transaction_id
ALTER TABLE silkroute.transaction_lines
    ADD CONSTRAINT fk_line_txn
        FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id);

-- transaction_lines.sku_id → product_variants_skus.sku_id
ALTER TABLE silkroute.transaction_lines
    ADD CONSTRAINT fk_line_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id);

-- inventory_snapshots.sku_id → product_variants_skus.sku_id
ALTER TABLE silkroute.inventory_snapshots
    ADD CONSTRAINT fk_inv_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id);

-- inventory_snapshots.store_id → stores.store_id
-- (Now valid after inserting S000 DC pseudo-store in Phase 0)
ALTER TABLE silkroute.inventory_snapshots
    ADD CONSTRAINT fk_inv_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id);

-- returns.transaction_id → transactions.transaction_id
ALTER TABLE silkroute.returns
    ADD CONSTRAINT fk_ret_txn
        FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id);

-- returns.sku_id → product_variants_skus.sku_id
ALTER TABLE silkroute.returns
    ADD CONSTRAINT fk_ret_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id);


-- ================================================================
-- PHASE 3: INDEXES (for query performance)
-- ================================================================

-- Transactions
CREATE INDEX idx_txn_customer     ON silkroute.transactions(customer_id);
CREATE INDEX idx_txn_store        ON silkroute.transactions(store_id);
CREATE INDEX idx_txn_date         ON silkroute.transactions(transaction_ts);
CREATE INDEX idx_txn_channel      ON silkroute.transactions(channel_type);
CREATE INDEX idx_txn_salesperson  ON silkroute.transactions(salesperson_id);

-- Transaction lines
CREATE INDEX idx_lines_txn  ON silkroute.transaction_lines(transaction_id);
CREATE INDEX idx_lines_sku  ON silkroute.transaction_lines(sku_id);

-- Returns
CREATE INDEX idx_ret_txn  ON silkroute.returns(transaction_id);
CREATE INDEX idx_ret_sku  ON silkroute.returns(sku_id);

-- Inventory snapshots
CREATE INDEX idx_inv_sku    ON silkroute.inventory_snapshots(sku_id);
CREATE INDEX idx_inv_store  ON silkroute.inventory_snapshots(store_id);

-- Product variants
CREATE INDEX idx_sku_product ON silkroute.product_variants_skus(product_id);

-- Salespeople
CREATE INDEX idx_sp_store ON silkroute.salespeople(store_id);

-- Promotions
CREATE INDEX idx_promo_product ON silkroute.promotions(product_id);

COMMIT;
