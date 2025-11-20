# Fuzzy Schema Mapping — R&D Summary

I tested a fuzzy-string-matching approach to map arbitrary CSV column names to our canonical sales schema. The approach uses fuzzy similarity (RapidFuzz when available, or difflib fallback) between canonical labels and user-provided headers, with a small type-aware score boost derived from sampling column values.

## What I implemented
- Normalize headers (lowercase, whitespace/punctuation collapsed).
- Compute fuzzy similarity scores for each canonical → each user column.
- Infer simple column types (date, numeric, id, string) from a small sample and boost matches where types align.
- Select the best candidate per canonical and resolve conflicts by preferring the highest total score.
- Expose a threshold control so the operator can tune sensitivity.

## Pros
- **Flexible to many naming variants** — catches typos, punctuation differences, and many common naming variations without manual alias lists.
- **Low-maintenance** — no need to curate huge alias dictionaries.
- **Fast & local** — no external API calls required; can run offline.
- **Transparent scoring** — provides base and total scores so you can inspect confidence and tune thresholds.

## Cons / Failure modes
- **Lacks semantic understanding** — fuzzy matching is textual: it cannot know that `sales` and `revenue` represent the same financial concept if their surface forms differ significantly or if they are semantically distant.
- **Ambiguity & false positives** — ambiguous short names like `sales`, `amount`, `total` may match multiple canonicals; resolution heuristics can still pick the wrong one.
- **Type heuristics are limited** — sampling-based type detection helps but will fail on small samples, formatted values, or mixed-type columns.
- **Still brittle for weird headers** — very terse or multilingual headers may be mis-scored if they lack clear lexical overlap.
- **No deep reasoning** — fuzzy matching cannot split combined fields (e.g., `location` containing "City, Country") or parse `sales_info` columns that embed multiple pieces of information.

## Example problematic cases observed
- `sales` vs `revenue`: fuzzy may give moderate scores to both depending on dataset and vocabulary; without semantics it can map `sales` to `channel` or `revenue` incorrectly.
- `region` vs `country` vs `city`: short geographical tokens or codes (e.g., `GB`, `UK`) are better resolved with sample values rather than header similarity.
- `product` vs `product_id` vs `product_name`: fuzzy sees similar tokens but can't determine whether the column holds IDs or names without strong value-sample signals.

## Conclusion
Fuzzy matching is a **useful component** — it is substantially better than a strict alias dictionary alone because it generalizes to many unseen variants and reduces manual maintenance. However, **it is not sufficient by itself** for the kind of robust, production-grade mapping we require for this project.

Key reason: fuzzy matching is surface-level and does not capture semantics. It often confuses conceptually different fields that share lexical overlap or short tokens. For user-generated CSVs with heterogeneous formats, we will still see incorrect mappings or missed mappings that could break downstream analytics.

**Final decision:** Do **not** rely exclusively on fuzzy matching for mapping in production. Instead, adopt a hybrid approach:
1. Strict alias mapping as a fast first pass (deterministic),
2. Fuzzy matching to capture close lexical variants,
3. Value-based heuristics (type inference, sample-driven rules),
4. LLM-assisted mapping for tough/semantic cases,
5. Human verification UI and caching of accepted mappings.
