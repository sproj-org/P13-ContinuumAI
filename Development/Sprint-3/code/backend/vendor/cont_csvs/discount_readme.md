# Discount Semantics (MVP)

## 1) Discovered Semantics
- In this synthetic dataset, `transaction_lines.discount` represents a **percent**, not a currency amount.
- Example: `discount = 0.025` means **2.5%** off.

## 2) Formula Used in GOLD Builders
- `gross_line = unit_price * quantity`  
  (or `gross_line_amount` when present in a denormalized `sales.csv`)
- `discount_amount_line = gross_line * discount_pct`
- `line_total` is treated as net line amount (already after discount).

## 3) Recommended Source Data Fix (Future)
- Make discount semantics explicit in SILVER:
1. Rename to `discount_pct` and store percent consistently (recommended range: `0-1`), or
2. Store explicit `discount_amount` in currency.
- Better: include `discount_type` (`percent|amount`) or keep both columns:
  `discount_pct` and `discount_amount`.

## 4) Auto-Detection (Temporary MVP Behavior)
- GOLD scripts include discount auto-detection only to handle mixed synthetic inputs quickly.
- Auto-detection is heuristic and should be considered temporary.
- For production-quality data contracts, use explicit discount fields and remove heuristics.

## 5) Example
- `unit_price = 100`
- `quantity = 2`
- `discount = 0.10` (10%)
- `gross_line = 100 * 2 = 200`
- `discount_amount_line = 200 * 0.10 = 20`
- `line_total = 180`
