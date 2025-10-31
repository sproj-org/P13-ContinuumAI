import pandas as pd
import numpy as np
import os
import shutil
from datetime import datetime, timedelta
import random

# Set random seed for reproducible results
np.random.seed(42)
random.seed(42)

print("🚀 ContinuumAI ETL Pipeline Starting...")
print("=" * 60)

# ============================================================================
# 1️⃣ LOAD DATASET
# ============================================================================
print("📥 1️⃣ Loading dataset...")
input_file = "database/data/SampleSuperstore.csv"
df = pd.read_csv(input_file, encoding="latin1")
print(f"   ✅ Loaded {len(df):,} records from SampleSuperstore.csv")

# ============================================================================
# SETUP OUTPUT DIRECTORY
# ============================================================================
output_dir = "database/data/processed"
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir, exist_ok=True)
print(f"   📁 Created clean output directory: {output_dir}")

# ============================================================================
# 2️⃣ GENERATE DIMENSION CSVS
# ============================================================================
print("\n📊 2️⃣ Generating dimension tables...")

# Products Table
print("   🏷️  Creating products.csv...")
products = df[["Product ID", "Product Name", "Category", "Sub-Category"]].drop_duplicates()
products.columns = ["product_id", "product_name", "category", "sub_category"]
products = products.reset_index(drop=True)
products.to_csv(f"{output_dir}/products.csv", index=False)
print(f"      ✅ {len(products):,} unique products")

# Customers Table
print("   👥 Creating customers.csv...")
customers = df[["Customer ID", "Customer Name", "Segment"]].drop_duplicates()
customers.columns = ["customer_id", "customer_name", "segment"]
customers = customers.reset_index(drop=True)
customers.to_csv(f"{output_dir}/customers.csv", index=False)
print(f"      ✅ {len(customers):,} unique customers")

# Regions Table
print("   🌍 Creating regions.csv...")
# Only create 4 regions - Central, East, South, West
unique_regions = df["Region"].unique()
regions = pd.DataFrame({
    "region_id": range(1, len(unique_regions) + 1),
    "region_name": sorted(unique_regions)
})
regions.to_csv(f"{output_dir}/regions.csv", index=False)
print(f"      ✅ {len(regions):,} unique regions")

# ============================================================================
# 3️⃣ CREATE SYNTHETIC SALESREPS
# ============================================================================
print("\n👨‍💼 3️⃣ Creating synthetic SalesReps...")

# Get unique regions for balanced distribution
unique_regions = regions['region_name'].unique()
region_mapping = dict(zip(unique_regions, range(1, len(unique_regions) + 1)))

# Create exactly 6 reps
rep_names = [
    "John Smith", "Sarah Johnson", "Mike Chen", 
    "Emma Wilson", "David Rodriguez", "Lisa Wang"
]

titles = ["Sales Executive", "Account Manager", "Regional Lead"]

# Generate hire dates between 2021-01-01 and 2023-12-31
start_date = datetime(2021, 1, 1)
end_date = datetime(2023, 12, 31)
date_range = (end_date - start_date).days

salesreps_data = []
for i in range(6):
    # Assign regions in a balanced way
    region_name = list(unique_regions)[i % len(unique_regions)]
    region_id = region_mapping[region_name]
    
    # Generate random hire date
    random_days = random.randint(0, date_range)
    hire_date = start_date + timedelta(days=random_days)
    
    # Generate quota between 400000 and 1200000
    quota = round(random.uniform(400000, 1200000), 2)
    
    salesreps_data.append({
        "rep_id": i + 1,
        "rep_name": rep_names[i],
        "region_id": region_id,
        "quota": quota,
        "title": titles[i % len(titles)],
        "hire_date": hire_date.strftime("%Y-%m-%d")
    })

salesreps = pd.DataFrame(salesreps_data)
salesreps.to_csv(f"{output_dir}/salesreps.csv", index=False)
print(f"      ✅ {len(salesreps):,} sales representatives created")

# ============================================================================
# 4️⃣ ENRICH SALES TRANSACTIONS
# ============================================================================
print("\n💰 4️⃣ Enriching sales transactions...")

# Rename columns
sales = df[[
    "Order ID", "Order Date", "Sales", "Quantity", "Discount",
    "Product ID", "Customer ID", "Region", "Ship Mode"
]].copy()

sales.columns = [
    "transaction_id", "order_date", "sales_amount", "quantity", "discount",
    "product_id", "customer_id", "region_name", "ship_mode"
]

# Join with regions to get region_id
sales_enriched = sales.merge(
    regions[["region_id", "region_name"]], 
    on="region_name", 
    how="left"
)

# Drop the region_name column as we only need region_id
sales_enriched = sales_enriched.drop(columns=['region_name'])

# Create region-to-rep mapping (balanced assignment)
region_rep_mapping = {}
for idx, region_id in enumerate(regions['region_id'].unique()):
    rep_id = (idx % 6) + 1  # Cycle through 6 reps
    region_rep_mapping[region_id] = rep_id

# Assign rep_id based on region_id
sales_enriched['rep_id'] = sales_enriched['region_id'].map(region_rep_mapping)

# Select final columns
sales_enriched = sales_enriched[[
    "transaction_id", "order_date", "sales_amount", "quantity", "discount",
    "product_id", "customer_id", "region_id", "rep_id", "ship_mode"
]]

sales_enriched.to_csv(f"{output_dir}/sales_transactions_enriched.csv", index=False)
print(f"      ✅ {len(sales_enriched):,} enriched sales transactions")

# ============================================================================
# 5️⃣ GENERATE SYNTHETIC OPPORTUNITIES
# ============================================================================
print("\n🎯 5️⃣ Generating synthetic opportunities...")

# Calculate 60% of unique customers
unique_customers = customers['customer_id'].unique()
opportunity_customers = np.random.choice(
    unique_customers, 
    size=int(len(unique_customers) * 0.6), 
    replace=False
)

# Calculate average sales per customer for deal_amount calculation
customer_avg_sales = sales_enriched.groupby('customer_id')['sales_amount'].mean().to_dict()

opportunities_data = []
deal_stages = ['Won', 'Lost', 'Pending']
stage_probabilities = [0.4, 0.4, 0.2]

for i, customer_id in enumerate(opportunity_customers):
    # Random product
    product_id = np.random.choice(products['product_id'])
    
    # Calculate deal amount based on customer's avg sales
    avg_sales = customer_avg_sales.get(customer_id, 1000)  # Default if no sales history
    deal_amount = round(avg_sales * random.uniform(0.5, 2.0), 2)
    
    # Assign deal stage based on probabilities
    deal_stage = np.random.choice(deal_stages, p=stage_probabilities)
    
    # Set probability based on stage
    if deal_stage == 'Won':
        probability = 90.0
    elif deal_stage == 'Pending':
        probability = 50.0
    else:  # Lost
        probability = 10.0
    
    # Generate created_date (random date in 2024)
    created_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 300))
    
    # Generate close_date
    if deal_stage == 'Pending':
        close_date = None
    else:
        days_to_close = random.randint(10, 90)
        close_date = created_date + timedelta(days=days_to_close)
    
    # Get customer's region to assign rep
    customer_sales = sales_enriched[sales_enriched['customer_id'] == customer_id]
    if not customer_sales.empty:
        rep_id = customer_sales['rep_id'].iloc[0]
    else:
        rep_id = random.randint(1, 6)  # Fallback random rep
    
    opportunities_data.append({
        "opportunity_id": i + 1,
        "created_date": created_date.strftime("%Y-%m-%d"),
        "close_date": close_date.strftime("%Y-%m-%d") if close_date else None,
        "deal_stage": deal_stage,
        "deal_amount": deal_amount,
        "rep_id": rep_id,
        "customer_id": customer_id,
        "product_id": product_id,
        "probability": probability,
        "notes": None
    })

opportunities = pd.DataFrame(opportunities_data)
opportunities.to_csv(f"{output_dir}/opportunities.csv", index=False)
print(f"      ✅ {len(opportunities):,} synthetic opportunities created")

# ============================================================================
# 7️⃣ PRINT SUMMARY
# ============================================================================
print("\n📋 7️⃣ ETL PIPELINE SUMMARY")
print("=" * 60)
print(f"📊 Products:              {len(products):,}")
print(f"👥 Customers:             {len(customers):,}")
print(f"🌍 Regions:               {len(regions):,}")
print(f"👨‍💼 Sales Reps:            {len(salesreps):,}")
print(f"💰 Sales Transactions:    {len(sales_enriched):,}")
print(f"🎯 Opportunities:         {len(opportunities):,}")
print(f"\n📁 Output Directory:      {output_dir}")

print("\n🎯 DEAL STAGE BREAKDOWN:")
stage_counts = opportunities['deal_stage'].value_counts()
for stage, count in stage_counts.items():
    percentage = (count / len(opportunities)) * 100
    print(f"   {stage}: {count:,} ({percentage:.1f}%)")

print("\n💼 SALES REP ASSIGNMENT:")
rep_counts = sales_enriched['rep_id'].value_counts().sort_index()
for rep_id, count in rep_counts.items():
    rep_name = salesreps[salesreps['rep_id'] == rep_id]['rep_name'].iloc[0]
    print(f"   Rep {rep_id} ({rep_name}): {count:,} transactions")

print("\n✅ ETL PIPELINE COMPLETED SUCCESSFULLY!")
print("🔄 Ready for MySQL import...")
print("=" * 60)

# List all created files
print("\n📁 Generated Files:")
for file in os.listdir(output_dir):
    file_path = os.path.join(output_dir, file)
    file_size = os.path.getsize(file_path)
    print(f"   • {file} ({file_size:,} bytes)")

print(f"\n🚀 All files saved to: {output_dir}")
print("💡 Run the MySQL import script next to load this data into your Railway database.")