"""
Fix ETL - Regenerate correct regions.csv and fix data import
"""
import pandas as pd
import csv

# Step 1: Create correct Regions table (only 4 regions)
regions_data = {
    'region_id': [1, 2, 3, 4],
    'region_name': ['Central', 'East', 'South', 'West']
}

regions_df = pd.DataFrame(regions_data)
regions_df.to_csv('data/processed/regions.csv', index=False, quoting=csv.QUOTE_NONNUMERIC)
print("✅ Created correct regions.csv with 4 regions")

# Step 2: Verify other CSV files
print("\n📊 Verifying CSV file record counts:")
for filename in ['products.csv', 'customers.csv', 'salesreps.csv', 'sales_transactions_enriched.csv', 'opportunities.csv']:
    try:
        df = pd.read_csv(f'data/processed/{filename}')
        print(f"  {filename}: {len(df)} records")
    except Exception as e:
        print(f"  {filename}: ERROR - {e}")

print("\n✅ Fix complete! Re-run the import script now.")
