
---

# ContinuumAI – Data Profiling Pipeline

## Overview

The ContinuumAI profiling pipeline is responsible for **introspecting analytical datasets (datamarts)** and producing a **validated, uniform, machine-consumable profile** describing:

* dataset structure and scale
* column semantics (role, type, cardinality)
* statistical properties appropriate to each column’s role
* safe metadata for downstream systems (UI, chart builder, agents)

The output of this pipeline forms a **foundational contract** for:

* dataset exploration & profiling UI
* chart builder and visualization agents (VizAgent)
* future LLM-based semantic enrichment
* decision intelligence workflows

The profiling process is **deterministic, explainable, and schema-validated**.
LLM involvement is explicitly optional and layered *after* core facts are established.

---

## Design Principles

The profiling system is built around the following principles:

1. **Contract-first**
   Every profile must validate against a strict Pydantic schema.

2. **Semantics over heuristics**
   Column roles are inferred using semantic rules, not just cardinality.

3. **Role-aware statistics**
   Different column roles require different summaries.

4. **Dataset-agnostic consumers**
   All datasets (sales, customers, stores, etc.) produce the same structure.

5. **Explainability**
   All decisions (roles, stats) are rule-based and auditable.

---

## Supported Datasets

The current pipeline profiles the following datamarts:

* `marts.mart_sales`
* `marts.mart_customers`
* `marts.mart_stores`

Each produces an independent profile JSON, all adhering to the same schema.

---

## High-Level Pipeline Flow

```
Postgres (Supabase)
        ↓
Schema Reflection
        ↓
Batch Structural Stats
(row count, nulls, distincts)
        ↓
Sampling
        ↓
Role Inference
        ↓
Role-Aware Statistics
        ↓
Pydantic Validation
        ↓
Profile JSON Output
```

---

## Step-by-Step Pipeline Description

### 1. Database Connection & Reflection

* The profiler connects to PostgreSQL using `DATABASE_URL`
* Tables are reflected using SQLAlchemy with explicit schema selection
* Column metadata is collected:

  * name
  * physical type
  * nullability

This stage establishes the **structural ground truth**.

---

### 2. Batch Structural Statistics (Dataset-Level)

To avoid redundant queries, the profiler computes core stats in batches:

* Total row count (once per dataset)
* For every column (in a single query):

  * `null_count`
  * `distinct_count`

These values are used later for:

* cardinality assessment
* uniqueness checks
* role inference fallbacks

---

### 3. Sampling

A lightweight sample of rows is collected:

* Primary method: `TABLESAMPLE SYSTEM`
* Fallback: `LIMIT N` if sampling yields no rows

From this:

* `sample_values` are extracted per column
* No random ordering or per-column sampling is used

Sampling is **informational**, not statistical.

---

### 4. Column Role Inference

Each column is assigned a **semantic role** using deterministic rules.

#### Supported Roles

* `id`
* `dimension`
* `measure`
* `datetime`
* `boolean`
* `text` (optional freeform)

#### Role Inference Rules (in order)

1. **Datetime**

   * Datetime/date type
   * Column name contains `date`, `time`, `ts`, `timestamp`

2. **ID**

   * Name ends with `_id`
   * Known identifiers (transaction_id, customer_id, store_id, etc.)

3. **Boolean**

   * Boolean type
   * Name starts with `is_` or `has_`

4. **Measure**

   * Numeric + semantic keywords:

     * amount, revenue, sales, price, cost
     * orders, count, units, days, customers
     * discount, refund, margin, rate, pct

5. **Numeric fallback**

   * Numeric columns default to `measure`
   * Cardinality-based dimension fallback is disabled for small tables

6. **Categorical fallback**

   * Strings / enums → `dimension`

This ensures:

* KPIs are never misclassified as categories
* IDs are never aggregated
* Small datasets (e.g., stores) are handled correctly

---

### 5. Role-Aware Statistics

Statistics are computed **based on role and data type**, not a single global rule.

#### Measures (numeric)

* min / max / mean / stddev
* p05 / p50 / p95
* zero_count

#### Dimensions (categorical)

* distinct_count
* top-K value distributions

#### Datetime

* min / max
* distinct_days

#### Boolean

* true_count
* false_count
* null_count

#### IDs

* distinct_count
* uniqueness flag
* samples only

This ensures every column yields **useful information**, even if its role changes later.

---

### 6. Schema Validation (Pydantic)

Before any profile is written:

* The entire dataset profile is validated against `DatasetProfile`
* All columns validate against `ColumnProfile`
* Enums enforce allowed roles and types
* Stats objects must match the column role

If validation fails, the dataset profile is rejected.

This makes profiling a **safe system boundary**, not best-effort output.

---

### 7. Output Generation

For each dataset, the profiler writes:

```
out/
 ├── mart_sales_profile.json
 ├── mart_customers_profile.json
 └── mart_stores_profile.json
```

Each file contains:

* dataset identifiers
* row and column counts
* profiled timestamp
* a uniform list of column profiles

---

## Output Structure (Conceptual)

```json
{
  "schema_name": "marts",
  "table_name": "mart_sales",
  "row_count": 29924,
  "column_count": 44,
  "profiled_at": "...",
  "dataset_meta": {},
  "columns": [
    {
      "name": "refund_amount",
      "physical_type": "float",
      "logical_type": "numeric",
      "base_role": "measure",
      "effective_role": "measure",
      "distinct_count": 132,
      "null_count": 0,
      "null_fraction": 0.0,
      "cardinality_bucket": "medium",
      "sample_values": [...],
      "stats": {
        "kind": "numeric",
        "min": 0.0,
        "max": 240.5,
        "mean": 12.7,
        "p05": 0.0,
        "p50": 5.0,
        "p95": 80.0,
        "zero_count": 12400
      },
      "agent_meta": {},
      "llm_meta": {},
      "effective_meta": {}
    }
  ]
}
```

All marts follow this structure exactly.

---

## How This Enables Future Functionality

### Frontend (Profiling UI)

* uniform column cards
* nulls, uniqueness, distributions
* role-aware rendering

### Chart Builder

* dimensions vs measures vs time axis
* safe aggregation rules
* default chart suggestions

### VizAgent / LLMs

* clean schema context
* sample values and distributions
* guardrails against invalid queries

### Future Enrichment

* `agent_meta`, `llm_meta`, `effective_meta` act as extension points
* semantic descriptions and relationships can be layered later

---

## Key Improvements Over the Original Experiment

* deterministic, validated output
* correct semantic roles across all marts
* role-aware stats (not measure-only)
* robust handling of small datasets
* frontend-ready, mart-agnostic structure
* clean separation of facts vs enrichment

---

## Summary

The profiling pipeline is no longer an experiment — it is a **core system component**.

It provides:

* trustworthy metadata
* stable contracts
* scalable architecture
* and a clean foundation for decision intelligence

All future ContinuumAI features build on this layer.
