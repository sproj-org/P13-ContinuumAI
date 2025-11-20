import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.append(str(BASE))

from app import _normalize_filters, _filter_data
from data_layer import load_sales_data

regions, categories = _normalize_filters('Show services in the west branch')
print('filters', regions, categories)

df = load_sales_data()
filtered = _filter_data(df, regions, categories)
print('counts', len(df), len(filtered))
