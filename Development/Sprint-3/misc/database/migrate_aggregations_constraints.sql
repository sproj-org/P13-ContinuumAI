-- ================================================================
-- MIGRATION: Enforce constraints on aggregations schema
-- Now that silkroute has PKs, we can reference them via FKs
-- ================================================================

BEGIN;

-- ================================================================
-- PHASE 1: PRIMARY KEY for store_daily_performance
-- ================================================================
ALTER TABLE aggregations.store_daily_performance
    ADD PRIMARY KEY (calendar_date, store_id);


-- ================================================================
-- PHASE 2: FOREIGN KEYS → silkroute (source of truth)
-- ================================================================

-- sales_detailed FKs
ALTER TABLE aggregations.sales_detailed
    ADD CONSTRAINT fk_sd_line
        FOREIGN KEY (line_id) REFERENCES silkroute.transaction_lines(line_id);

ALTER TABLE aggregations.sales_detailed
    ADD CONSTRAINT fk_sd_transaction
        FOREIGN KEY (transaction_id) REFERENCES silkroute.transactions(transaction_id);

ALTER TABLE aggregations.sales_detailed
    ADD CONSTRAINT fk_sd_sku
        FOREIGN KEY (sku_id) REFERENCES silkroute.product_variants_skus(sku_id);

ALTER TABLE aggregations.sales_detailed
    ADD CONSTRAINT fk_sd_customer
        FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id);

ALTER TABLE aggregations.sales_detailed
    ADD CONSTRAINT fk_sd_channel
        FOREIGN KEY (channel_type) REFERENCES silkroute.channels(channel_type);

-- store_id is NULL for online orders → no FK (would fail on NULLs check)
-- But PostgreSQL FKs allow NULLs by default, so we CAN add it:
ALTER TABLE aggregations.sales_detailed
    ADD CONSTRAINT fk_sd_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id);

-- store_daily_performance FKs
ALTER TABLE aggregations.store_daily_performance
    ADD CONSTRAINT fk_sdp_store
        FOREIGN KEY (store_id) REFERENCES silkroute.stores(store_id);

-- customer_360 FKs
ALTER TABLE aggregations.customer_360
    ADD CONSTRAINT fk_c360_customer
        FOREIGN KEY (customer_id) REFERENCES silkroute.customers(customer_id);


-- ================================================================
-- PHASE 3: INDEXES for query performance
-- ================================================================

-- sales_detailed indexes
CREATE INDEX idx_sd_transaction   ON aggregations.sales_detailed(transaction_id);
CREATE INDEX idx_sd_sku           ON aggregations.sales_detailed(sku_id);
CREATE INDEX idx_sd_customer      ON aggregations.sales_detailed(customer_id);
CREATE INDEX idx_sd_store         ON aggregations.sales_detailed(store_id);
CREATE INDEX idx_sd_channel       ON aggregations.sales_detailed(channel_type);
CREATE INDEX idx_sd_category      ON aggregations.sales_detailed(category);
CREATE INDEX idx_sd_ts            ON aggregations.sales_detailed(transaction_ts);
CREATE INDEX idx_sd_returned      ON aggregations.sales_detailed(is_returned) WHERE is_returned = TRUE;

-- store_daily_performance indexes
CREATE INDEX idx_sdp_store        ON aggregations.store_daily_performance(store_id);
CREATE INDEX idx_sdp_date         ON aggregations.store_daily_performance(calendar_date);

-- customer_360 indexes
CREATE INDEX idx_c360_segment     ON aggregations.customer_360(segment);

COMMIT;
