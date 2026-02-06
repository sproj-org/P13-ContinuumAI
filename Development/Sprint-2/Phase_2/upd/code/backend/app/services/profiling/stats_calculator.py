"""
Type-specific statistics calculator
Computes detailed stats for numeric, categorical, and datetime columns
"""

from sqlalchemy import text
from typing import Dict, Any, List

def get_numeric_stats(schema: str, table: str, column_name: str, db_engine) -> Dict[str, Any]:
    """
    Calculate statistics for numeric columns
    Returns: min, max, mean, five_number_summary
    """
    table_fqn = f"{schema}.{table}"
    
    query = text(f"""
        SELECT 
            MIN({column_name})::float as min_val,
            MAX({column_name})::float as max_val,
            AVG({column_name})::float as mean_val,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {column_name})::float as q1,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY {column_name})::float as median,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {column_name})::float as q3
        FROM {table_fqn}
        WHERE {column_name} IS NOT NULL
    """)
    
    conn = db_engine.connect()
    result = conn.execute(query).fetchone()
    conn.close()
    
    if not result or result[0] is None:
        return {}
    
    return {
        "min": round(result[0], 2),
        "max": round(result[1], 2),
        "mean": round(result[2], 2),
        "five_number_summary": {
            "min": round(result[0], 2),
            "q1": round(result[3], 2),
            "median": round(result[4], 2),
            "q3": round(result[5], 2),
            "max": round(result[1], 2)
        }
    }

def get_categorical_frequencies(schema: str, table: str, column_name: str, 
                                db_engine, limit: int = 10) -> Dict[str, Any]:
    """
    Calculate frequency distribution for categorical columns
    Returns top N values with counts and percentages
    """
    table_fqn = f"{schema}.{table}"
    
    # Get total count for percentage calculation
    total_query = text(f"""
        SELECT COUNT(*) FROM {table_fqn} WHERE {column_name} IS NOT NULL
    """)
    
    conn = db_engine.connect()
    total_count = conn.execute(total_query).scalar()
    
    if total_count == 0:
        conn.close()
        return {"class_frequencies": []}
    
    # Get top frequencies
    freq_query = text(f"""
        SELECT 
            {column_name} as value,
            COUNT(*) as count
        FROM {table_fqn}
        WHERE {column_name} IS NOT NULL
        GROUP BY {column_name}
        ORDER BY count DESC
        LIMIT {limit}
    """)
    
    result = conn.execute(freq_query).fetchall()
    conn.close()
    
    frequencies = []
    for row in result:
        frequencies.append({
            "value": str(row[0]),
            "count": row[1],
            "percent": round(row[1] / total_count, 4)
        })
    
    return {"class_frequencies": frequencies}

def get_datetime_range(schema: str, table: str, column_name: str, db_engine) -> Dict[str, Any]:
    """
    Calculate min/max for datetime columns
    """
    table_fqn = f"{schema}.{table}"
    
    query = text(f"""
        SELECT 
            MIN({column_name})::text as min_date,
            MAX({column_name})::text as max_date
        FROM {table_fqn}
        WHERE {column_name} IS NOT NULL
    """)
    
    conn = db_engine.connect()
    result = conn.execute(query).fetchone()
    conn.close()
    
    if not result or result[0] is None:
        return {}
    
    return {
        "min": result[0],
        "max": result[1]
    }

def enrich_column_with_stats(column_profile: Dict, schema: str, table: str, db_engine) -> Dict:
    """
    Add type-specific statistics to column profile
    """
    logical_type = column_profile['logical_type']
    base_role = column_profile['base_role']
    column_name = column_profile['name']
    
    # Only compute expensive stats for measures
    if logical_type == 'numeric' and base_role == 'measure':
        stats = get_numeric_stats(schema, table, column_name, db_engine)
        column_profile['stats'] = stats
    
    # Frequency distribution for low-cardinality categoricals
    elif logical_type == 'categorical' and column_profile['cardinality_bucket'] == 'low':
        stats = get_categorical_frequencies(schema, table, column_name, db_engine, limit=10)
        column_profile['stats'] = stats
    
    # Date range for temporal columns
    elif logical_type == 'datetime':
        stats = get_datetime_range(schema, table, column_name, db_engine)
        column_profile['stats'] = stats
    
    return column_profile
