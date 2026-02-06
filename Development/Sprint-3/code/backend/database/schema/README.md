# Database Schema Reference

These SQL files document the **complete database schema** as enforced on the PostgreSQL server. You can read them to understand the structure without needing to connect to the database.

## Schemas

### 1. `silkroute` — Source of Truth (Universal Layer)

**File:** [`silkroute_schema.sql`](silkroute_schema.sql)

13 tables containing the raw SilkRoute benchmark dataset.

| Table | Rows | PK | FKs | Description |
| ----- | ----: | :--: | :---: | ----------- |
| `channels` | 2 | `channel_type` | — | online / store |
| `stores` | 7 | `store_id` | — | 6 stores + DC (S000) |
| `customers` | 2,500 | `customer_id` | — | Customer profiles |
| `salespeople` | 26 | `salesperson_id` | → stores | Store staff |
| `products` | 90 | `product_id` | — | Product catalog |
| `product_variants_skus` | 150 | `sku_id` | → products | Size/color variants |
| `variant_attributes` | 246 | UQ(sku_id, attr_name) | → product_variants_skus | Flexible attributes |
| `category_attribute_definitions` | 11 | UQ(category, attr_name) | — | Expected attributes per category |
| `promotions` | 12 | `promo_id` | → products | Promo campaigns |
| `transactions` | 11,402 | `transaction_id` | → channels, customers | Purchase events |
| `transaction_lines` | 29,924 | `line_id` | → transactions, product_variants_skus | Items per transaction |
| `inventory_snapshots` | 55,650 | UQ(date, store, sku) | → product_variants_skus, stores | Daily stock levels |
| `returns` | 1,287 | `return_id` | → transactions, product_variants_skus | Returned items |

**Totals:** 10 PKs, 3 UNIQUE constraints, 12 FKs, 14 indexes

---

### 2. `aggregations` — Analytical (Denormalized Layer)

**File:** [`aggregations_schema.sql`](aggregations_schema.sql)

3 denormalized tables built on top of `silkroute` for analytics.

| Table | Rows | PK | FKs | Granularity |
| ----- | ----: | :--: | :---: | ----------- |
| `sales_detailed` | 29,924 | `line_id` | 6 → silkroute | Transaction line (item) |
| `store_daily_performance` | 2,096 | `(calendar_date, store_id)` | 1 → silkroute | Store × Day |
| `customer_360` | 2,500 | `customer_id` | 1 → silkroute | Unique customer |

**Totals:** 3 PKs, 8 FKs, 11 indexes

---

## ER Diagram (simplified)

```text
silkroute.channels ←── silkroute.transactions ──→ silkroute.customers
                              │  ↑                        ↑
                              │  │                        │
                              ▼  │                        │
                  silkroute.stores              aggregations.customer_360
                       ↑    ↑
                       │    │
    silkroute.salespeople   silkroute.inventory_snapshots
                                       │
                                       ▼
silkroute.products ←── silkroute.product_variants_skus
       ↑                    ↑        ↑
       │                    │        │
silkroute.promotions   silkroute.variant_attributes
                            │        │
              silkroute.transaction_lines ──→ aggregations.sales_detailed
                            │
                      silkroute.returns
```

## How to Use

- **Just reading?** Open the `.sql` files — they have full DDL with comments.
- **Fresh setup?** Run `silkroute_schema.sql` first, then `aggregations_schema.sql`.
- **Enforcing on existing data?** Use the migration scripts in `database/`:
  - `migrate_silkroute_constraints.sql`
  - `migrate_aggregations_constraints.sql`
