# README — Schema Mapping R&D (brief)

This repository contains R&D work and small apps for automatically mapping arbitrary CSV column headers to a canonical sales schema. Below is a short, high-level summary of what was tried, artifacts included, and recommended next steps.

---

## Canonical schema

The project maps incoming CSVs to this canonical set of fields:

`order_id`, `opportunity_id`, `customer_id`, `order_date`, `lead_date`, `close_date`,  
`first_purchase_date`, `revenue`, `units`, `product_id`, `product_name`, `category`,  
`salesperson`, `region`, `country`, `city`, `stage`, `channel`, `is_returning`, `aov`,  
`sales_cycle_days`

---

## Approaches explored (short)

### 1. Strict dictionary (alias) mapping
**Method:** normalize headers and lookup against a curated alias dictionary (`DEFAULT_ALIAS`).  
**Pros:** deterministic, fast, no external deps, auditable.  
**Cons:** brittle; requires massive ongoing maintenance; fails when a header variant is missing.  

### 2. Fuzzy string matching
**Method:** fuzzy similarity (RapidFuzz or difflib) between canonical labels and headers, plus light sample-based type boosts and conflict resolution.  
**Pros:** generalizes beyond explicit aliases, low maintenance, runs locally.  
**Cons:** surface-level only — lacks semantic understanding and can misassign short/ambiguous tokens.  

### 3. LLM-assisted mapping + human-in-the-loop
**Method:** prompt an LLM (Gemini) with canonical names and CSV columns (optionally sample values) to get a JSON mapping; display for user review and correction.  
**Pros:** best semantic flexibility; handles multilingual and terse names; minimal manual upkeep.  
**Cons:** nondeterministic at times, cost/availability, privacy concerns if sample values are sent; still requires UI verification.  

---

## Key findings (one-liners)

- **Strict dictionary:** fast and deterministic but not robust enough for user-generated CSVs.  
- **Fuzzy matching:** better generalization, but still surface-level — often confuses semantically different fields with lexical overlap.  
- **LLM + human verification:** best practical accuracy and flexibility; still imperfect and raises privacy/cost concerns if raw sample values are shared.
