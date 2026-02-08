---

# ContinuumAI – Data Aggregation & Datamart Design

## Overview

The data aggregation layer in ContinuumAI is responsible for transforming the **universal SilkRoute benchmark schema** into a small number of **purpose-built analytical datamarts**.

These datamarts:

* act as the **primary datasets** exposed to profiling, chart builder, and agents
* replace raw-table selection with **use-case aligned datasets**
* mirror the “gold layer” concept from modern analytics architectures (e.g. Databricks medallion)

The goal is **clarity, relevance, and explainability**, not maximal normalization or minimal storage.

---

## Design Rationale

### Why datamarts instead of raw tables?

The raw SilkRoute schema is intentionally rich and normalized:

* transactions, customers, stores, products, promotions, etc.
* suitable for data generation and integrity testing
* **not suitable for direct analytical interaction**

If agents or users operate directly on raw tables:

* context is fragmented
* joins become implicit and error-prone
* profiling and visualization become noisy
* decision intelligence degrades into SQL gymnastics

Datamarts solve this by:

* pre-joining relevant entities
* aligning datasets to **decision domains**
* embedding business semantics directly into the schema

---

## Guiding Principles

1. **Domain-oriented datasets**

   * Each mart maps to a clear analytical domain:

     * Sales
     * Customers
     * Stores

2. **Single dataset per decision surface**

   * One mart = one primary context for profiling, charts, and agents
   * No dataset picker full of low-level tables

3. **No pre-aggregation by time**

   * No daily / weekly / monthly rollups
   * Temporal aggregation is a **query concern**, not a data model concern

4. **Preserve analytical flexibility**

   * All relevant dimensions are retained
   * Measures remain atomic (line-level where appropriate)

5. **Explainable joins**

   * All joins follow explicit relationships from the universal schema
   * No hidden logic or inference at query time

---

## Universal Schema → Datamarts

The SilkRoute universal schema includes entities such as:

* transactions
* transaction_lines
* customers
* stores
* products
* promotions
* salespeople
* returns

Datamarts are **derived views over this schema**, not independent models.

All relationships in datamarts:

* respect original primary/foreign keys
* maintain referential meaning
* avoid denormalization that breaks traceability

---

## Datamart Definitions

### 1. `mart_sales` – Transactional Sales Analytics

#### Purpose

Designed for:

* revenue analysis
* discount and refund analysis
* sales performance by product, store, customer, promotion
* time-based trend analysis

This is the **primary analytical mart**.

#### Grain

**One row per transaction line**

This ensures:

* atomic revenue and quantity measures
* flexible aggregation at any level
* correct handling of refunds and discounts

#### Key Measures

* gross_line_amount
* net_line_amount
* discount_amount
* refund_amount
* quantity
* unit_price

#### Key Dimensions

* transaction date / timestamp
* product (category, subcategory, brand)
* customer (segment, region)
* store (store_id, city, region)
* promotion (promo_type, discount_type)
* channel / payment method

#### Why this design?

* Line-level grain avoids double counting
* All slicing dimensions are present
* No joins required downstream

---

### 2. `mart_customers` – Customer-Centric Analytics

#### Purpose

Designed for:

* customer segmentation
* behavioral analysis
* lifetime value style analysis
* churn / retention indicators

#### Grain

**One row per customer**

This mart collapses transactional history into **customer-level features**.

#### Key Measures

* orders
* returned_orders
* total_spend
* average_order_value
* tenure_days
* recency_days

#### Key Dimensions

* customer segment
* region / city
* acquisition channel
* demographic attributes (if present)

#### Why this design?

* Enables customer profiling without joins
* Suitable for cohort analysis and clustering
* Clean separation from transaction noise

---

### 3. `mart_stores` – Store-Level Performance Analytics

#### Purpose

Designed for:

* store performance comparison
* footprint and utilization analysis
* regional rollups
* operational decision-making

#### Grain

**One row per store**

This mart is intentionally small.

#### Key Measures

* orders
* unique_customers
* active_days
* total_revenue
* average_daily_revenue

#### Key Dimensions

* store type
* city / region
* opening date
* store size (if applicable)

#### Why this design?

* Supports executive dashboards
* Works well with small row counts
* Stable context for agents and profiling

---

## Physical Storage Strategy

### Physical tables (current)

Datamarts are stored as **physical tables** under the `marts` schema:

```
marts.mart_sales
marts.mart_customers
marts.mart_stores
```

#### Why physical tables?

* faster profiling
* stable query performance
* predictable behavior for agents
* simpler mental model during MVP phase

Views can be introduced later if needed.

---

## Relationship to Profiling

Each datamart is:

* profiled independently
* produces a uniform profile JSON
* adheres to the same profiling contract

This guarantees:

* frontend components can switch marts seamlessly
* agents can reason over any mart using the same logic
* no dataset-specific code paths

---

## Relationship to Chart Builder & VizAgent

Because datamarts:

* embed joins
* align to decision domains
* preserve clean measures vs dimensions

The chart builder can:

* suggest sensible defaults
* avoid invalid aggregations
* generate explainable visualizations

VizAgent can:

* reason over schema safely
* generate charts and summaries without guessing joins
* focus on decisions, not plumbing

---

## Extensibility & Future Directions

### Future enhancements

* LLM-assisted aggregation generation
* dynamic datamart definition from use cases
* incremental refresh strategies
* feature marts for ML use cases

### What will *not* change

* domain-driven mart design
* separation between raw schema and analytical context
* use of datamarts as the primary decision surface

---

## Summary

The data aggregation layer is **not just ETL**.

It is:

* a semantic boundary
* a decision-alignment layer
* the foundation that makes profiling, visualization, and agents viable

By defining **Sales, Customers, and Stores** datamarts explicitly, ContinuumAI ensures that:

* analytics are explainable
* interfaces are intuitive
* agents operate on meaning, not mechanics

This layer, together with profiling, forms the **core intelligence substrate** of ContinuumAI.
