# Chat Smoke Report

- Generated: 2026-02-19 03:13:45 UTC
- Mode: stub

| mart | prompt | response_type | steps_to_converge | notes |
| --- | --- | --- | --- | --- |
| gold_sales_daily | Show avg_order_value by channel_type | chart | 1 | success |
| gold_sales_daily | Top 10 channel_type by avg_order_value | chart | 1 | success |
| gold_sales_daily | Trend of avg_order_value by month using sales_date | chart | 2 | success |
| gold_sales_daily | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_sales_daily | Show performance | chart | 2 | success |
| gold_sales_daily | Show customer age distribution | clarify | 3 | success |
| gold_store_sku_daily | Show discount_amount by sku_id | chart | 1 | success |
| gold_store_sku_daily | Top 10 sku_id by discount_amount | chart | 1 | success |
| gold_store_sku_daily | Trend of discount_amount by month using sales_date | chart | 2 | success |
| gold_store_sku_daily | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_store_sku_daily | Show performance | chart | 2 | success |
| gold_store_sku_daily | Show customer age distribution | clarify | 3 | success |
| gold_store_360 | Show active_days by city | chart | 1 | success |
| gold_store_360 | Top 10 city by active_days | chart | 1 | success |
| gold_store_360 | Trend of active_days by month using first_date | chart | 2 | success |
| gold_store_360 | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_store_360 | Show performance | chart | 2 | success |
| gold_store_360 | Show customer age distribution | clarify | 3 | success |
| gold_product_360 | Show active_months by brand | chart | 1 | success |
| gold_product_360 | Top 10 brand by active_months | chart | 1 | success |
| gold_product_360 | Trend of active_months by month using first_tx_date | chart | 2 | success |
| gold_product_360 | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_product_360 | Show performance | chart | 2 | success |
| gold_product_360 | Show customer age distribution | clarify | 3 | success |
| gold_customer_360 | Show avg_order_value by active_months | chart | 1 | success |
| gold_customer_360 | Top 10 active_months by avg_order_value | chart | 1 | success |
| gold_customer_360 | Trend of avg_order_value by month using first_purchase_date | chart | 2 | success |
| gold_customer_360 | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_customer_360 | Show performance | chart | 2 | success |
| gold_customer_360 | Show customer age distribution | clarify | 3 | success |
| gold_employee_360 | Show active_days by home_store_id | chart | 1 | success |
| gold_employee_360 | Top 10 home_store_id by active_days | chart | 1 | success |
| gold_employee_360 | Trend of active_days by month using first_tx_date | chart | 2 | success |
| gold_employee_360 | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_employee_360 | Show performance | chart | 2 | success |
| gold_employee_360 | Show customer age distribution | clarify | 3 | success |
| gold_inventory_health_daily | Show adj_avg_daily_units by overstock_flag | chart | 1 | success |
| gold_inventory_health_daily | Top 10 overstock_flag by adj_avg_daily_units | chart | 1 | success |
| gold_inventory_health_daily | Trend of adj_avg_daily_units by month using snapshot_date | chart | 2 | success |
| gold_inventory_health_daily | Explain what this mart represents and what KPIs it supports | explain | 1 | success |
| gold_inventory_health_daily | Show performance | chart | 2 | success |
| gold_inventory_health_daily | Show customer age distribution | clarify | 3 | success |

## Summary
- charts: 28
- explains: 7
- clarifies: 7
- refuses: 0
- failures: 0
- avg steps (all prompts): 1.67
- avg steps to converge (in-scope prompts): 1.33

## Clarify Rate By Mart
- gold_customer_360: 0.17
- gold_employee_360: 0.17
- gold_inventory_health_daily: 0.17
- gold_product_360: 0.17
- gold_sales_daily: 0.17
- gold_store_360: 0.17
- gold_store_sku_daily: 0.17