"""
Main profiler orchestrator - combines base profiling, stats, and LLM enrichment
Generates final JSON matching meta.json template structure
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.profiling.base_profiler import profile_dataset_base
from services.profiling.stats_calculator import enrich_column_with_stats
from services.profiling.llm_enricher import enrich_all_columns_batch, enrich_dataset_level

DATABASE_URL = "postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"

def profile_mart(schema_name: str, table_name: str, output_path: str = None):
    """
    Complete profiling workflow:
    1. Base profiling (no LLM)
    2. Stats calculation (type-specific)
    3. LLM enrichment (batched, 2 calls total)
    4. Save to JSON
    """
    print(f"\n{'='*60}")
    print(f"Profiling: {schema_name}.{table_name}")
    print(f"{'='*60}\n")
    
    # Step 1: Base profiling
    print("[1/4] Base profiling (metadata extraction)...")
    base_profile = profile_dataset_base(schema_name, table_name)
    print(f"  ✓ Profiled {base_profile['column_count']} columns, {base_profile['row_count']:,} rows\n")
    
    # Step 2: Stats calculation
    print("[2/4] Calculating type-specific statistics...")
    engine = create_engine(DATABASE_URL)
    enriched_columns = []
    for col in base_profile['columns']:
        enriched = enrich_column_with_stats(col, schema_name, table_name, engine)
        enriched_columns.append(enriched)
    base_profile['columns'] = enriched_columns
    print(f"  ✓ Added stats for {len(enriched_columns)} columns\n")
    
    # Step 3: LLM enrichment (BATCHED)
    print("[3/4] LLM enrichment (2 API calls total)...")
    
    # Call 1: Enrich all columns in one batch
    base_profile['columns'] = enrich_all_columns_batch(base_profile['columns'])
    
    # Call 2: Dataset-level insights
    final_profile = enrich_dataset_level(base_profile)
    
    print(f"  ✓ LLM enrichment complete\n")
    
    # Step 4: Save output
    print("[4/4] Saving final JSON...")
    
    if output_path is None:
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{table_name}_profile.json"
    
    with open(output_path, 'w') as f:
        json.dump(final_profile, f, indent=2, default=str)
    
    print(f"  ✓ Saved to: {output_path}")
    print(f"\n{'='*60}")
    print(f"Profiling complete!")
    print(f"  - Columns: {final_profile['column_count']}")
    print(f"  - Rows: {final_profile['row_count']:,}")
    print(f"  - LLM calls: 2 (optimized batch mode)")
    print(f"{'='*60}\n")
    
    return final_profile

if __name__ == "__main__":
    # Profile mart_sales
    profile_mart("marts", "mart_sales")
    
    # Uncomment to profile other marts
    # profile_mart("marts", "mart_customers")
    # profile_mart("marts", "mart_stores")
