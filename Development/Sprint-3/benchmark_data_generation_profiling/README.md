# SilkRoute Benchmark Dataset & Analysis

This directory contains the **synthetic benchmark dataset, generation pipeline, and analytical notebooks** used to validate and demonstrate the capabilities of **ContinuumAI / Trendata** using a fictitious retail company called **SilkRoute**.

The goal of this benchmark is **not realism for realism’s sake**, but to generate **controlled, explainable business patterns** that can be reliably discovered, diagnosed, predicted, and acted upon by agentic analytics systems.

---

## 1. Purpose & Design Philosophy

SilkRoute is a **fictional omnichannel retail company** designed to:

* Avoid NDA or client-specific bias
* Encode *intentional business behaviors* (good and bad)
* Act as a **reference implementation** for:

  * Data modeling
  * Profiling
  * Visual analytics
  * Predictive & prescriptive AI
* Provide a **ground-truth benchmark** for validating agent behavior

The dataset is **pattern-driven**, not random:

* Online channel grows steadily over time
* A small set of “hero SKUs” dominate revenue
* Some stores are structurally underperforming
* Discount-heavy behavior causes margin erosion
* A subset of SKUs and customers drive abnormal returns
* Inventory pressure and stockouts emerge for hero products

All of these patterns are **explicitly seeded** and recorded in a manifest for verification.

---

## 2. Project Structure

```
benchmark_data_generation_profiling/
  README.md
  requirements.txt
  src/
    silkroute/
      config.py
      catalogs.py
      io.py

      generators/
        dimensions.py
        products.py
        promotions.py
        transactions.py
        inventory.py
        returns.py

  scripts/
    generate_dataset.py

  notebooks/
    01_generation_sanity.ipynb
    02_sales_customer_store_insights.ipynb
    03_returns_inventory_stockouts.ipynb

  silkroute_benchmark_out/
    *.parquet
    *.csv
    seed_manifest.json
```

---

## 3. Dataset Overview

### Core Entities

The generated dataset includes:

* **Channels** (store / online)
* **Stores** (location, region, type)
* **Customers** (segments: loyal, price-sensitive, high-return, etc.)
* **Salespeople** (top performers, discount-heavy profiles)
* **Products**
* **SKUs / Variants** (size, color, attributes)
* **Promotions**
* **Transactions**
* **Transaction lines**
* **Returns**
* **Inventory snapshots** (store + DC)

All relationships are referentially consistent and validated in Notebook 01.

---

## 4. Pattern Ground Truth (Seed Manifest)

After generation, a `seed_manifest.json` file is written containing:

* Hero SKUs
* High-return SKUs
* Top-performing salespeople
* Discount-heavy salespeople
* Underperforming stores
* Discount-heavy stores
* Enforced online share by month
* Generation configuration parameters

This file enables:

* Deterministic verification
* Agent evaluation against known truths
* Repeatable experimentation

---

## 5. Installation

### Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .\.venv\Scripts\activate
```

### Install dependencies

For **generation only**:

```bash
pip install -r requirements-core.txt
```

For **generation + notebooks**:

```bash
pip install -r requirements-analysis.txt
```

### Make source importable

```bash
export PYTHONPATH="$PWD/src"
# Windows PowerShell:
# $env:PYTHONPATH="$PWD\src"
```

---

## 6. Dataset Generation

To generate the full SilkRoute benchmark dataset:

```bash
python scripts/generate_dataset.py
```

This will create:

```
silkroute_benchmark_out/
  channels.parquet
  stores.parquet
  customers.parquet
  salespeople.parquet
  products.parquet
  product_variants_skus.parquet
  variant_attributes.parquet
  category_attribute_definitions.parquet
  promotions.parquet
  transactions.parquet
  transaction_lines.parquet
  inventory_snapshots.parquet
  returns.parquet
  seed_manifest.json
```

Both **Parquet and CSV** versions are written for convenience.

---

## 7. Analysis Notebooks

### 01 — Generation Sanity & Core Patterns

**Purpose:** QA + benchmark validation

Covers:

* Row counts and scale targets
* Referential integrity
* Online revenue & share trend
* Discount long-tail and clearance tail
* SKU Pareto (hero concentration)
* Underperforming stores
* Discount vs margin erosion proxy
* Returns outliers and reasons
* Pass/fail heuristic checks

➡ This notebook answers: *“Did we generate what we intended?”*

---

### 02 — Sales, Customer & Store Insights

**Purpose:** Descriptive and diagnostic analytics

Covers:

* Basket size, AOV, discount by channel
* Category mix over time
* Customer segmentation behavior
* Monthly active customers
* Salesperson attach rate vs discount culture
* Store traffic vs AOV
* Hero vs non-hero SKU behavior
* Promotion window lift proxies

➡ This notebook answers: *“What is happening, and why?”*

---

### 03 — Returns, Inventory & Stockouts

**Purpose:** Operational stress and risk signals

Covers:

* Return rate by customer segment
* Return outlier SKUs (vs seeded ground truth)
* Return reasons by category
* Stockout rates (hero vs non-hero)
* Seasonal stockout pressure (Q4)
* Store vs DC stockout comparison
* Lost-sales proxy concepts

➡ This notebook answers: *“Where are the operational risks?”*

---

## 8. How This Is Used in ContinuumAI

This benchmark is intended to be used as:

* A **profiling reference** for agents
* A **visual analytics playground**
* A **predictive modeling testbed**
* A **prescriptive recommendation benchmark**
* A **demo narrative** for business stakeholders

It explicitly supports:

* Descriptive → Diagnostic → Predictive → Prescriptive flows
* Strategy-aware decision intelligence
* Agentic reasoning grounded in data + context

---

## 9. Extending the Benchmark

Common extensions:

* Add pricing elasticity models
* Inject supply chain disruptions
* Add marketing attribution signals
* Introduce region-specific seasonality
* Simulate fraud or abuse patterns

The modular generator design allows each of these to be added **without rewriting the pipeline**.

---


> This dataset is **not random synthetic data**.
> It is **intentionally biased synthetic data**, designed to teach, test, and validate intelligence.

