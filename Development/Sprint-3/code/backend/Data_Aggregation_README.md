# Data Aggregations

This plan outlines the creation of an **Analytical Layer** within the `aggregations` schema. These three denormalized tables transform raw data into insight-ready formats, catering to the descriptive, diagnostic, and predictive use cases defined in the ContinuumAI document.

---

### 1. Table: `sales_detailed`

* **Granularity:** Transaction Line (Item Level)
* 
**Source Tables Joined:** `Transaction Lines`, `Transaction`, `Product Variant`, `Product`, `Returns`.


* **Purpose & Use Cases:**
* Calculates **Profit Margin** by subtracting base price and discounts from the unit price.


* Flags returned items to support **High Returns Detection** and **Returns Overview**.


* Enables **Price & Discount Impact** analysis by linking line-level pricing to product metadata.





### 2. Table: `store_daily_performance`

* **Granularity:** Store per Day
* 
**Source Tables Joined:** `Store`, `Transaction`, `Inventory Snapshot`.


* **Purpose & Use Cases:**
* Aggregates daily revenue and footfall for **Store Performance** benchmarking.


* Combines sales velocity with inventory levels to detect **Stock-out Risk**.


* Supports **Store Underperformance** diagnostics by tracking conversion and volume trends over time.





### 3. Table: `customer_360`

* **Granularity:** Unique Customer Profile
* 
**Source Tables Joined:** `Customer`, `Transaction`, `Returns`, `Transaction Lines`.


* **Purpose & Use Cases:**
* Consolidates lifetime spend, frequency, and recency for **Customer Segmentation** (RFM analysis).


* Calculates return rates to identify high-risk behaviors for **Return Risk Prediction**.


* Identifies preferred categories to support **Customer Overview** and churn analysis.





---

### SQL Implementation

#### Part 1: Schema & Table Creation (DDL)

```sql
-- Create the dedicated schema for analytical tables
CREATE SCHEMA IF NOT EXISTS aggregations;

-- (1) Sales Detailed Table: Item-level grain
CREATE TABLE aggregations.sales_detailed (
    line_id VARCHAR(50) PRIMARY KEY,
    transaction_id VARCHAR(50),
    transaction_ts TIMESTAMP, -- Converted from string for trend analysis
    channel_type VARCHAR(20),  
    store_id VARCHAR(50),      
    customer_id VARCHAR(50),
    sku_id VARCHAR(50),
    product_name VARCHAR(255),
    brand VARCHAR(100),
    category VARCHAR(100),     
    subcategory VARCHAR(100),
    quantity INTEGER,
    unit_price DECIMAL(12, 2),
    discount DECIMAL(12, 2),
    base_price DECIMAL(12, 2), 
    margin DECIMAL(12, 2),     -- Calculated as (unit_price - discount) - base_price
    is_returned BOOLEAN DEFAULT FALSE,
    return_reason TEXT
);

-- (2) Store Daily Performance: Store-Day grain
-- Note: No Primary Key to allow historical logging; uniqueness is (store_id + calendar_date)
CREATE TABLE aggregations.store_daily_performance (
    calendar_date DATE,        
    store_id VARCHAR(50),
    store_name VARCHAR(100),
    city VARCHAR(100),         
    region VARCHAR(100),
    daily_revenue DECIMAL(15, 2),
    transaction_count INTEGER,
    units_sold_count INTEGER,
    avg_basket_value DECIMAL(12, 2),
    stock_on_hand_eod INTEGER  
);

-- (3) Customer 360: Customer-level grain
CREATE TABLE aggregations.customer_360 (
    customer_id VARCHAR(50) PRIMARY KEY,
    segment VARCHAR(50),       
    city VARCHAR(100),
    first_purchase_date DATE,  
    last_purchase_date DATE,
    total_lifetime_spend DECIMAL(15, 2),
    total_order_count INTEGER,
    preferred_category VARCHAR(100),
    return_rate_pct DECIMAL(5, 2) 
);

```

#### Part 2: Data Population (DML)

```sql
-- Populate Sales Detailed
INSERT INTO aggregations.sales_detailed (
    line_id, transaction_id, transaction_ts, channel_type, store_id, 
    customer_id, sku_id, product_name, brand, category, subcategory, 
    quantity, unit_price, discount, base_price, margin, is_returned, return_reason
)
SELECT 
    tl.line_id,
    tl.transaction_id,
    CAST(t.transaction_ts AS TIMESTAMP),
    t.channel_type,
    t.store_id,
    t.customer_id,
    tl.sku_id,
    p.product_name,
    p.brand,
    p.category,
    p.subcategory,
    CAST(tl.quantity AS INTEGER),
    CAST(tl.unit_price AS DECIMAL(12, 2)),
    CAST(tl.discount AS DECIMAL(12, 2)),
    CAST(pv.base_price AS DECIMAL(12, 2)),
    (CAST(tl.unit_price AS DECIMAL(12, 2)) * (1 - CAST(tl.discount AS DECIMAL(12, 2)))) - CAST(pv.base_price AS DECIMAL(12, 2)),
    CASE WHEN r.return_id IS NOT NULL THEN TRUE ELSE FALSE END,
    r.return_reason
FROM silkroute.transaction_lines tl
JOIN silkroute.transactions t ON tl.transaction_id = t.transaction_id
JOIN silkroute.product_variants_skus pv ON tl.sku_id = pv.sku_id
JOIN silkroute.products p ON pv.product_id = p.product_id
LEFT JOIN silkroute.returns r ON tl.transaction_id = r.transaction_id AND tl.sku_id = r.sku_id;

-- Populate Store Daily Performance
INSERT INTO aggregations.store_daily_performance (
    calendar_date, store_id, store_name, city, region, 
    daily_revenue, transaction_count, units_sold_count, 
    avg_basket_value, stock_on_hand_eod
)
WITH daily_sales AS (
    SELECT 
        CAST(transaction_ts AS DATE) as d,
        store_id,
        SUM(total_amount) as rev,
        COUNT(DISTINCT transaction_id) as txns
    FROM silkroute.transactions
    WHERE store_id IS NOT NULL
    GROUP BY 1, 2
),
daily_inventory AS (
    SELECT 
        CAST(snapshot_date AS DATE) as d,
        store_id,
        SUM(stock_on_hand) as total_stock
    FROM silkroute.inventory_snapshots
    GROUP BY 1, 2
)
SELECT 
    ds.d,
    ds.store_id,
    s.store_name,
    s.city,
    s.region,
    ds.rev,
    ds.txns,
    (SELECT SUM(quantity) FROM silkroute.transaction_lines tl 
     JOIN silkroute.transactions t ON tl.transaction_id = t.transaction_id 
     WHERE t.store_id = ds.store_id AND CAST(t.transaction_ts AS DATE) = ds.d) as units,
    ds.rev / ds.txns as abv,
    di.total_stock
FROM daily_sales ds
JOIN silkroute.stores s ON ds.store_id = s.store_id
LEFT JOIN daily_inventory di ON ds.d = di.d AND ds.store_id = di.store_id;

-- Populate Customer 360
INSERT INTO aggregations.customer_360 (
    customer_id, segment, city, first_purchase_date, 
    last_purchase_date, total_lifetime_spend, 
    total_order_count, preferred_category, return_rate_pct
)
SELECT 
    c.customer_id,
    c.segment,
    c.city,
    CAST(c.first_purchase_date AS DATE),
    MAX(CAST(t.transaction_ts AS DATE)),
    SUM(CAST(t.total_amount AS DECIMAL(15, 2))),
    COUNT(DISTINCT t.transaction_id),
    (SELECT p.category 
     FROM silkroute.transaction_lines tl 
     JOIN silkroute.transactions t2 ON tl.transaction_id = t2.transaction_id
     JOIN silkroute.product_variants_skus pv ON tl.sku_id = pv.sku_id
     JOIN silkroute.products p ON pv.product_id = p.product_id
     WHERE t2.customer_id = c.customer_id 
     GROUP BY p.category ORDER BY COUNT(*) DESC LIMIT 1),
    (COUNT(DISTINCT r.transaction_id)::DECIMAL / NULLIF(COUNT(DISTINCT t.transaction_id), 0)) * 100
FROM silkroute.customers c
LEFT JOIN silkroute.transactions t ON c.customer_id = t.customer_id
LEFT JOIN silkroute.returns r ON t.transaction_id = r.transaction_id
GROUP BY c.customer_id, c.segment, c.city, c.first_purchase_date;

```