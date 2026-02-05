# strict_alias_streamlit.py
import streamlit as st
import pandas as pd
import re
from typing import Dict, List, Optional, Tuple

st.set_page_config(page_title="Strict Alias Schema Mapper", layout="wide")

# -----------------------
# Canonical schema
# -----------------------
CANONICAL = [
    "order_id","opportunity_id","customer_id","order_date","lead_date",
    "close_date","first_purchase_date","revenue","units","product_id",
    "product_name","category","salesperson","region","country","city",
    "stage","channel","is_returning","aov","sales_cycle_days"
]

# -----------------------
# Expanded alias dictionary — many common variants
# (Add more entries as you discover new variants — this list is intentionally large)
# Keys should be normalized variants; values must be canonical.
# -----------------------
DEFAULT_ALIAS = {
    # order_id
    "orderno": "order_id", "order_no": "order_id", "order_id": "order_id",
    "order id": "order_id", "order#": "order_id", "order-number": "order_id",
    "order_number": "order_id", "order": "order_id", "id_order": "order_id",
    "id_ord": "order_id", "id_ordr": "order_id", "orderref": "order_id", "order_ref": "order_id",

    # opportunity_id
    "opportunity_id": "opportunity_id", "oppid": "opportunity_id", "opp_id": "opportunity_id",
    "opportunity": "opportunity_id", "opp": "opportunity_id", "op_no": "opportunity_id",
    "opp_no": "opportunity_id", "opportunity_number": "opportunity_id", "opp_ref": "opportunity_id",

    # customer_id
    "cust_id": "customer_id", "customer_id": "customer_id", "client_id": "customer_id",
    "customer": "customer_id", "cust": "customer_id", "client": "customer_id", "customer_no": "customer_id",
    "clientno": "customer_id", "customer_ref": "customer_id",

    # order_date variants
    "order_date": "order_date", "orderdate": "order_date", "date_of_order": "order_date",
    "purchase_date": "order_date", "date": "order_date", "created_at": "order_date",
    "order_dt": "order_date", "order_time": "order_date", "fecha_pedido": "order_date",  # spanish
    "fecha": "order_date",

    # lead_date
    "lead_date": "lead_date", "lead_date_time": "lead_date", "lead_dt": "lead_date",
    "lead": "lead_date", "lead_generated_on": "lead_date",

    # close_date
    "close_date": "close_date", "closed_on": "close_date", "closed_date": "close_date",
    "closedate": "close_date", "date_closed": "close_date", "closed_at": "close_date",

    # first_purchase_date
    "first_purchase_date": "first_purchase_date", "first_purchase": "first_purchase_date",
    "first_order_date": "first_purchase_date", "first_order": "first_purchase_date",
    "firstbuy": "first_purchase_date", "first_buy": "first_purchase_date",

    # revenue
    "revenue": "revenue", "rev": "revenue", "amount": "revenue", "total": "revenue",
    "total_amount": "revenue", "total_amt": "revenue", "amt": "revenue", "sale_amount": "revenue",
    "sales": "revenue", "sales_amount": "revenue", "rev_usd": "revenue", "rev_gbp": "revenue",
    "rev_eur": "revenue", "amount_usd": "revenue", "revusd": "revenue", "totalusd": "revenue",

    # units
    "units": "units", "qty": "units", "quantity": "units", "unit_count": "units",
    "qnty": "units", "qty_sold": "units", "sold_qty": "units",

    # product_id
    "product_id": "product_id", "prod_id": "product_id", "sku": "product_id", "productcode": "product_id",
    "product_code": "product_id", "item_code": "product_id", "prod#": "product_id", "prdid": "product_id",

    # product_name
    "product_name": "product_name", "prod_name": "product_name", "item_name": "product_name",
    "product": "product_name", "producttitle": "product_name", "itemtitle": "product_name",
    "prod_label": "product_name", "prod_descr": "product_name",

    # category
    "category": "category", "cat": "category", "category_name": "category",
    "cat_name": "category", "grpcat": "category", "group": "category", "categorygroup": "category",
    "catg": "category", "categoria": "category",  # spanish

    # salesperson
    "salesperson": "salesperson", "rep": "salesperson", "sales_rep": "salesperson",
    "salesperson_name": "salesperson", "account_manager": "salesperson", "owner": "salesperson",
    "srsp": "salesperson", "srep": "salesperson", "seller": "salesperson",

    # region
    "region": "region", "region_name": "region", "territory": "region", "territory_area": "region",
    "geo": "region", "regioncode": "region", "area": "region", "zone": "region",

    # country
    "country": "country", "country_code": "country", "pais": "country", "cnty": "country", "countryname": "country",

    # city
    "city": "city", "city_name": "city", "town": "city", "cty": "city", "city_loc": "city",

    # stage
    "stage": "stage", "deal_stage": "stage", "pipeline_stage": "stage", "pipeline": "stage",
    "pipeline_state": "stage", "stg": "stage",

    # channel
    "channel": "channel", "sales_channel": "channel", "sales_channel_name": "channel", "ch": "channel",
    "sales_stream": "channel", "distribution_channel": "channel",

    # is_returning
    "is_returning": "is_returning", "returning": "is_returning", "repeat_flag": "is_returning",
    "repeat_customer": "is_returning", "is_repeat": "is_returning", "is_returning_customer": "is_returning",

    # aov
    "aov": "aov", "avg_order_value": "aov", "avg_order": "aov", "mean_ticket": "aov",
    "average_order_value": "aov", "mean_order_value": "aov", "avg_ticket": "aov",

    # sales_cycle_days
    "sales_cycle_days": "sales_cycle_days", "deal_days": "sales_cycle_days", "cycle_len": "sales_cycle_days",
    "days_to_close": "sales_cycle_days", "cycle_days": "sales_cycle_days", "salescycle": "sales_cycle_days",
}

# -----------------------
# Helpers
# -----------------------
def _normalize_header(s: str) -> str:
    """Normalize to lower, replace non-alnum with underscore, remove stray underscores."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def build_normalized_alias(alias: Dict[str, str]) -> Dict[str, str]:
    return {_normalize_header(k): v for k, v in alias.items()}

# Strict mapping implementation (canonical -> user_col or None)
def strict_map_df(df: pd.DataFrame, canonical: List[str] = CANONICAL, alias_dict: Dict[str, str] = None) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    alias_dict = alias_dict or DEFAULT_ALIAS
    norm_alias = build_normalized_alias(alias_dict)

    user_cols = list(df.columns)
    norm_user_to_orig = {_normalize_header(c): c for c in user_cols}

    # prepare mapping
    mapping: Dict[str, Optional[str]] = {c: None for c in canonical}
    normalized_canonical = {_normalize_header(c): c for c in canonical}

    # exact normalized canonical match or alias match
    for ncol, orig in norm_user_to_orig.items():
        # exact canonical name
        if ncol in normalized_canonical:
            canonical_name = normalized_canonical[ncol]
            mapping[canonical_name] = orig
            continue
        # alias dict
        if ncol in norm_alias:
            cand = norm_alias[ncol]
            if cand in canonical:
                mapping[cand] = orig

    # create renamed df (only mapped columns renamed)
    rename_map = {v: k for k, v in mapping.items() if v is not None}
    mapped_df = df.rename(columns=rename_map)

    return mapped_df, mapping

# -----------------------
# Streamlit UI
# -----------------------
st.title("📋 Strict Alias Schema Mapper (Streamlit)")

st.markdown(
    """
Upload any CSV. The app uses a large **strict alias dictionary** to map user columns to our canonical sales schema.
This is deterministic and fast — no ML. It shows `canonical -> mapped column` and a preview of the renamed dataframe.
"""
)

uploaded = st.file_uploader("Upload CSV (any CSV)", type=["csv", "txt"])

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
    except Exception:
        # try with python engine fallback
        df = pd.read_csv(uploaded, engine="python")

    st.subheader("Preview (first 5 rows)")
    st.dataframe(df.head())

    st.write("Detected columns:", list(df.columns))

    if st.button("Run strict alias mapping"):
        with st.spinner("Mapping..."):
            mapped_df, mapping = strict_map_df(df)
        st.success("Mapping complete — showing results below.")

        # Show mapping as table
        mapping_df = pd.DataFrame([
            {"canonical": k, "mapped_to": (mapping[k] if mapping[k] is not None else "<no mapping>")}
            for k in CANONICAL
        ])
        st.subheader("Mapping (canonical → user column or `<no mapping>`)")
        st.dataframe(mapping_df)

        st.subheader("Renamed dataframe preview (after strict mapping)")
        st.dataframe(mapped_df.head())

        # optional: allow download
        csv_out = mapped_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download renamed CSV", data=csv_out, file_name="mapped_output.csv", mime="text/csv")
else:
    st.info("Upload a CSV to begin. The app will attempt strict alias mapping of columns.")
