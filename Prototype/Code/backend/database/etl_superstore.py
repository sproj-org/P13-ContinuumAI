import pandas as pd
import os

input_file = "database/data/SampleSuperstore.csv"

print("📥 Loading dataset...")
df = pd.read_csv(input_file, encoding="latin1")

output_dir = "database/data"
os.makedirs(output_dir, exist_ok=True)

# ✅ Products
df_products = df[["Product ID", "Product Name", "Category", "Sub-Category"]] \
    .drop_duplicates() \
    .rename(columns={
        "Product ID": "product_id",
        "Product Name": "product_name",
        "Sub-Category": "sub_category"
    })

df_products.to_csv(f"{output_dir}/products.csv", index=False)

# ✅ Customers
df_customers = df[["Customer ID", "Customer Name", "Segment"]] \
    .drop_duplicates() \
    .rename(columns={
        "Customer ID": "customer_id",
        "Customer Name": "customer_name"
    })

df_customers.to_csv(f"{output_dir}/customers.csv", index=False)

# ✅ Regions
df_regions = df[["Region", "State", "City"]] \
    .drop_duplicates() \
    .reset_index(drop=True)

df_regions.insert(0, "region_id", df_regions.index + 1)

df_regions.rename(columns={
    "Region": "region_name",
}) \
.to_csv(f"{output_dir}/regions.csv", index=False)

# ✅ Sales Transactions
df_sales = df[[
    "Order ID", "Order Date", "Sales", "Quantity", "Discount",
    "Product ID", "Customer ID", "Region", "Ship Mode"
]].rename(columns={
    "Order ID": "transaction_id",
    "Order Date": "order_date",
    "Sales": "sales_amount",
    "Discount": "discount",
    "Region": "region_name",
    "Ship Mode": "ship_mode"
})

df_sales.to_csv(f"{output_dir}/sales_transactions.csv", index=False)

print("\n✅ Processed CSV files created successfully!")
print(f"📂 Output directory: {output_dir}")
