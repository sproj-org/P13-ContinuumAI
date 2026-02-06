"""
Base profiler - extracts metadata without LLM calls
Optimized for speed and minimal queries
"""

from sqlalchemy import create_engine, text, inspect
from typing import Dict, List, Any
import os

DATABASE_URL = "postgresql://postgres.mffusogkupczpxchfjtt:missionSPROJ098@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"

def get_column_metadata(schema: str, table: str, db_engine) -> List[Dict]:
    """Get all columns with physical types from information_schema"""
    query = text(f"""
        SELECT 
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = :schema
        AND table_name = :table
        ORDER BY ordinal_position
    """)
    
    result = db_engine.connect().execute(query, {"schema": schema, "table": table})
    
    columns = []
    for row in result:
        columns.append({
            "column_name": row[0],
            "physical_type": map_pg_type_to_simple(row[1]),
            "is_nullable": row[2] == 'YES'
        })
    
    return columns

def map_pg_type_to_simple(pg_type: str) -> str:
    """Map PostgreSQL types to simple types matching meta.json"""
    type_map = {
        'text': 'string',
        'character varying': 'string',
        'integer': 'int',
        'bigint': 'int',
        'double precision': 'float',
        'numeric': 'float',
        'boolean': 'boolean',
        'date': 'datetime',
        'timestamp without time zone': 'datetime',
        'timestamp with time zone': 'datetime'
    }
    return type_map.get(pg_type.lower(), 'string')

def detect_logical_type(physical_type: str) -> str:
    """Detect logical type from physical type"""
    if physical_type in ['int', 'float']:
        return 'numeric'
    elif physical_type == 'datetime':
        return 'datetime'
    elif physical_type == 'boolean':
        return 'boolean'
    else:
        return 'categorical'

def detect_base_role(column_name: str, logical_type: str, cardinality_ratio: float, distinct_count: int) -> str:
    """Rule-based role detection (NO LLM)"""
    col_lower = column_name.lower()
    
    # ID detection
    if '_id' in col_lower or col_lower.endswith('id') or col_lower == 'id':
        return 'dimension'
    
    # Temporal
    if 'date' in col_lower or 'time' in col_lower or logical_type == 'datetime':
        return 'time_dimension'
    
    # Boolean
    if logical_type == 'boolean' or (col_lower.startswith('is_') or col_lower.startswith('has_')):
        return 'dimension'
    
    # Numeric with high cardinality = measure
    if logical_type == 'numeric' and cardinality_ratio > 0.3:
        # Check if it's likely an amount/price/quantity
        measure_keywords = ['amount', 'price', 'sales', 'revenue', 'cost', 'margin', 'quantity', 'units', 'count', 'total', 'avg', 'pct', 'rate', 'discount']
        if any(kw in col_lower for kw in measure_keywords):
            return 'measure'
        # High cardinality numeric but not clear measure keyword
        if cardinality_ratio > 0.8:
            return 'dimension'  # Likely an ID
        return 'measure'
    
    # Low cardinality = dimension
    if cardinality_ratio < 0.05 or distinct_count < 100:
        return 'dimension'
    
    # Default
    return 'dimension' if logical_type == 'categorical' else 'measure'

def get_cardinality_bucket(cardinality_ratio: float) -> str:
    """Classify cardinality"""
    if cardinality_ratio > 0.9:
        return 'high'
    elif cardinality_ratio < 0.02:
        return 'low'
    else:
        return 'medium'

def profile_column_base(schema: str, table: str, column_name: str, 
                       physical_type: str, is_nullable: bool, 
                       total_rows: int, db_engine) -> Dict:
    """
    Base profiling for a single column (no LLM)
    Returns metadata matching meta.json structure
    """
    table_fqn = f"{schema}.{table}"
    
    # Quick stats query
    stats_query = text(f"""
        SELECT 
            COUNT(DISTINCT {column_name}) as distinct_count,
            COUNT(*) - COUNT({column_name}) as null_count
        FROM {table_fqn}
    """)
    
    conn = db_engine.connect()
    result = conn.execute(stats_query).fetchone()
    
    distinct_count = result[0] or 0
    null_count = result[1] or 0
    null_fraction = null_count / total_rows if total_rows > 0 else 0
    cardinality_ratio = distinct_count / total_rows if total_rows > 0 else 0
    
    # Detect types and roles
    logical_type = detect_logical_type(physical_type)
    base_role = detect_base_role(column_name, logical_type, cardinality_ratio, distinct_count)
    cardinality_bucket = get_cardinality_bucket(cardinality_ratio)
    
    # Sample values (3 random)
    sample_query = text(f"""
        SELECT {column_name}
        FROM {table_fqn}
        WHERE {column_name} IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 3
    """)
    samples = [str(row[0]) for row in conn.execute(sample_query).fetchall()]
    
    # Build base profile
    profile = {
        "name": column_name,
        "physical_type": physical_type,
        "logical_type": logical_type,
        "base_role": base_role,
        "row_count": total_rows,
        "distinct_count": distinct_count,
        "null_fraction": round(null_fraction, 4),
        "cardinality_bucket": cardinality_bucket,
        "sample_values": samples,
        "stats": {},
        "is_unique": (distinct_count == total_rows),
        "base_needs_review": False,
        "base_issues": []
    }
    
    conn.close()
    
    return profile

def profile_dataset_base(schema: str, table: str) -> Dict:
    """
    Base dataset profiling (no LLM)
    Returns structure matching meta.json
    """
    engine = create_engine(DATABASE_URL)
    table_fqn = f"{schema}.{table}"
    
    # Get row count
    conn = engine.connect()
    row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_fqn}")).scalar()
    
    # Get columns
    columns_meta = get_column_metadata(schema, table, engine)
    column_count = len(columns_meta)
    
    # Profile each column
    column_profiles = []
    for i, col_meta in enumerate(columns_meta):
        print(f"  Profiling column {i+1}/{column_count}: {col_meta['column_name']}...")
        
        profile = profile_column_base(
            schema=schema,
            table=table,
            column_name=col_meta['column_name'],
            physical_type=col_meta['physical_type'],
            is_nullable=col_meta['is_nullable'],
            total_rows=row_count,
            db_engine=engine
        )
        
        column_profiles.append(profile)
    
    conn.close()
    
    from datetime import datetime
    
    return {
        "dataset_name": table.replace('mart_', ''),
        "row_count": row_count,
        "column_count": column_count,
        "profiled_at": datetime.utcnow().isoformat() + "Z",
        "columns": column_profiles
    }
