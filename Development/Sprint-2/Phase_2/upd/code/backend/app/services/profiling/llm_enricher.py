"""
LLM enrichment layer - OPTIMIZED for minimal API calls
Uses batched prompting to process all columns in 2 LLM calls total
"""

import openai
import json
from typing import Dict, List, Any

# Set API key
openai.api_key = "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"

def enrich_all_columns_batch(column_profiles: List[Dict]) -> List[Dict]:
    """
    OPTIMIZED: Single LLM call to enrich ALL columns at once
    Returns enriched column profiles with agent_* and llm_* fields
    """
    
    # Build compact summary of all columns for LLM
    columns_summary = []
    for col in column_profiles:
        summary = {
            "name": col['name'],
            "type": f"{col['physical_type']} ({col['logical_type']})",
            "role": col['base_role'],
            "distinct": col['distinct_count'],
            "nulls": f"{col['null_fraction']*100:.1f}%",
            "cardinality": col['cardinality_bucket'],
            "samples": col['sample_values'][:3],
            "stats": col.get('stats', {})
        }
        columns_summary.append(summary)
    
    prompt = f"""You are a data profiling expert. Analyze these {len(column_profiles)} columns from a sales transaction dataset and provide enriched metadata for EACH column.

Dataset context: This is a transactional sales dataset with line-item grain (one row per product sold in each transaction).

Columns to analyze:
{json.dumps(columns_summary, indent=2)}

For EACH column, provide a JSON object with these fields:
{{
  "name": "column_name",
  "agent_semantic_type": "age_years|currency_usd|full_name|date|percentage|quantity|identifier|null",
  "agent_display_name": "Human-readable name",
  "agent_description": "1-2 sentence description with notable stats and usage",
  "llm_analytical_uses": ["segmentation", "filtering", "grouping", "aggregation"],
  "llm_not_suitable_for": ["sum", "average"],
  "llm_operation_constraints": {{
    "allowed": [{{"operation": "AVG", "reason": "why applicable"}}],
    "blocked": [{{"operation": "SUM", "reason": "why not applicable"}}]
  }},
  "llm_suggested_visualizations": [{{"chart": "bar|line|pie|histogram|scatter", "why": "reason"}}],
  "llm_kpi_ideas": [{{"kpi": "metric name", "how": "calculation description"}}],
  "llm_relationship_hints": [{{"with_column": "other_column", "why": "reason"}}],
  "llm_quality_signals": {{
    "missingness_note": "assessment of missing values",
    "dominance_note": "note about value distribution",
    "rare_values_note": "note about rare values if applicable"
  }},
  "llm_confidence": "high|medium|low",
  "llm_confidence_reason": "why this confidence level"
}}

Return a JSON array of objects, one per column, in the same order as input.
Focus on practical business insights for a sales analytics platform.
"""

    print("  Calling LLM for batch column enrichment...")
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a data profiling expert. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        
        # Parse response - expecting {"columns": [...]}
        try:
            llm_data = json.loads(content)
            if "columns" in llm_data:
                enrichments = llm_data["columns"]
            elif isinstance(llm_data, list):
                enrichments = llm_data
            else:
                # Try to extract array from response
                enrichments = list(llm_data.values())[0] if llm_data else []
        except:
            print("  Warning: Could not parse LLM response, using defaults")
            enrichments = []
        
        # Merge enrichments with base profiles
        enriched_columns = []
        for i, col in enumerate(column_profiles):
            enriched = col.copy()
            
            # Find matching enrichment
            llm_enrich = None
            for enrich in enrichments:
                if enrich.get('name') == col['name']:
                    llm_enrich = enrich
                    break
            
            if llm_enrich:
                # Add LLM fields
                enriched.update({
                    "agent_semantic_type": llm_enrich.get("agent_semantic_type"),
                    "agent_display_name": llm_enrich.get("agent_display_name", col['name']),
                    "agent_description": llm_enrich.get("agent_description", ""),
                    "agent_suggested_role": None,
                    "agent_suggested_logical_type": None,
                    "agent_needs_review": False,
                    "agent_issues": [],
                    "llm_description": llm_enrich.get("agent_description", ""),
                    "llm_analytical_uses": llm_enrich.get("llm_analytical_uses", []),
                    "llm_not_suitable_for": llm_enrich.get("llm_not_suitable_for", []),
                    "llm_operation_constraints": llm_enrich.get("llm_operation_constraints", {"allowed": [], "blocked": []}),
                    "llm_suggested_visualizations": llm_enrich.get("llm_suggested_visualizations", []),
                    "llm_kpi_ideas": llm_enrich.get("llm_kpi_ideas", []),
                    "llm_relationship_hints": llm_enrich.get("llm_relationship_hints", []),
                    "llm_quality_signals": llm_enrich.get("llm_quality_signals", {}),
                    "llm_confidence": llm_enrich.get("llm_confidence", "medium"),
                    "llm_confidence_reason": llm_enrich.get("llm_confidence_reason", "")
                })
            else:
                # Fallback if no enrichment found
                enriched.update({
                    "agent_semantic_type": None,
                    "agent_display_name": col['name'],
                    "agent_description": "",
                    "agent_suggested_role": None,
                    "agent_suggested_logical_type": None,
                    "agent_needs_review": False,
                    "agent_issues": [],
                    "llm_description": "",
                    "llm_analytical_uses": [],
                    "llm_not_suitable_for": [],
                    "llm_operation_constraints": {"allowed": [], "blocked": []},
                    "llm_suggested_visualizations": [],
                    "llm_kpi_ideas": [],
                    "llm_relationship_hints": [],
                    "llm_quality_signals": {},
                    "llm_confidence": "low",
                    "llm_confidence_reason": "LLM enrichment not available"
                })
            
            # Add effective fields
            enriched["effective_role"] = enriched.get("agent_suggested_role") or enriched["base_role"]
            enriched["effective_logical_type"] = enriched.get("agent_suggested_logical_type") or enriched["logical_type"]
            enriched["effective_semantic_type"] = enriched.get("agent_semantic_type")
            enriched["effective_display_name"] = enriched.get("agent_display_name")
            enriched["effective_description"] = enriched.get("agent_description")
            enriched["needs_review"] = False
            enriched["issues"] = []
            
            enriched_columns.append(enriched)
        
        print(f"  ✓ Enriched {len(enriched_columns)} columns")
        return enriched_columns
        
    except Exception as e:
        print(f"  ✗ LLM call failed: {e}")
        # Return base profiles without enrichment
        return [add_default_enrichment(col) for col in column_profiles]

def enrich_dataset_level(dataset_profile: Dict) -> Dict:
    """
    OPTIMIZED: Single LLM call for dataset-level insights
    """
    
    # Summarize columns for context
    col_summary = "\n".join([
        f"- {c['name']}: {c['logical_type']} ({c['base_role']}), "
        f"{c['distinct_count']:,} distinct, {c['null_fraction']*100:.1f}% null"
        for c in dataset_profile['columns'][:20]  # First 20 columns
    ])
    
    if len(dataset_profile['columns']) > 20:
        col_summary += f"\n... and {len(dataset_profile['columns']) - 20} more columns"
    
    prompt = f"""Analyze this sales transaction dataset and provide high-level business insights.

Dataset: {dataset_profile['dataset_name']}
Rows: {dataset_profile['row_count']:,}
Columns: {dataset_profile['column_count']}

Key columns:
{col_summary}

Provide a JSON object with:
{{
  "dataset_llm_analytical_uses": ["use case 1", "use case 2", ...],
  "dataset_llm_kpi_ideas": [
    {{"kpi": "KPI name", "how": "How to calculate it"}},
    ...
  ],
  "dataset_llm_supported_questions": ["question 1", "question 2", ...],
  "dataset_llm_confidence": "high|medium|low",
  "dataset_llm_confidence_reason": "Why this confidence level"
}}

Focus on practical business questions for sales analytics.
"""

    print("  Calling LLM for dataset-level enrichment...")
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a business intelligence expert. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        llm_data = json.loads(response.choices[0].message.content)
        
        # Merge with dataset profile
        dataset_profile.update(llm_data)
        
        print(f"  ✓ Added dataset-level insights")
        return dataset_profile
        
    except Exception as e:
        print(f"  ✗ Dataset LLM call failed: {e}")
        # Add defaults
        dataset_profile.update({
            "dataset_llm_analytical_uses": [],
            "dataset_llm_kpi_ideas": [],
            "dataset_llm_supported_questions": [],
            "dataset_llm_confidence": "medium",
            "dataset_llm_confidence_reason": "LLM enrichment not available"
        })
        return dataset_profile

def add_default_enrichment(col: Dict) -> Dict:
    """Add default enrichment fields if LLM fails"""
    col.update({
        "agent_semantic_type": None,
        "agent_display_name": col['name'],
        "agent_description": "",
        "agent_suggested_role": None,
        "agent_suggested_logical_type": None,
        "agent_needs_review": False,
        "agent_issues": [],
        "llm_description": "",
        "llm_analytical_uses": [],
        "llm_not_suitable_for": [],
        "llm_operation_constraints": {"allowed": [], "blocked": []},
        "llm_suggested_visualizations": [],
        "llm_kpi_ideas": [],
        "llm_relationship_hints": [],
        "llm_quality_signals": {},
        "llm_confidence": "low",
        "llm_confidence_reason": "LLM enrichment not available",
        "effective_role": col["base_role"],
        "effective_logical_type": col["logical_type"],
        "effective_semantic_type": None,
        "effective_display_name": col['name'],
        "effective_description": "",
        "needs_review": False,
        "issues": []
    })
    return col
