from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import sys
import os
from io import BytesIO
from datetime import datetime

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import data_logic

app = Flask(__name__)
# Configure CORS properly
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Store current dataset in memory (in production, use proper session management)
current_data = {}

def prepare_chart_data(df):
    """Prepare all chart data for the frontend"""
    chart_data = {}
    
    # Sales by Region
    if "region" in df.columns and "revenue" in df.columns:
        sales_by_region = df.groupby('region')['revenue'].sum().reset_index()
        chart_data['sales_by_region'] = sales_by_region.to_dict('records')
    else:
        chart_data['sales_by_region'] = []
    
    # Sales over Time
    if "order_date" in df.columns and "revenue" in df.columns:
        sales_over_time = df.set_index('order_date')['revenue'].resample('ME').sum().reset_index()
        sales_over_time['date'] = sales_over_time['order_date'].dt.strftime('%Y-%m')
        chart_data['sales_over_time'] = sales_over_time[['date', 'revenue']].to_dict('records')
    else:
        chart_data['sales_over_time'] = []
    
    # Sales by Channel
    if "channel" in df.columns and "revenue" in df.columns:
        sales_by_channel = df.groupby('channel')['revenue'].sum().reset_index()
        chart_data['sales_by_channel'] = sales_by_channel.to_dict('records')
    else:
        chart_data['sales_by_channel'] = []
    
    # Revenue Distribution
    if "revenue" in df.columns and len(df) > 0:
        hist_values, bin_edges = np.histogram(df['revenue'], bins=20)
        revenue_dist = []
        for i in range(len(hist_values)):
            revenue_dist.append({
                'range': f"${bin_edges[i]:.0f}-${bin_edges[i+1]:.0f}",
                'count': int(hist_values[i])
            })
        chart_data['revenue_distribution'] = revenue_dist
    else:
        chart_data['revenue_distribution'] = []
    
    # Top Salespeople
    if "salesperson" in df.columns and "revenue" in df.columns:
        top_sales = df.groupby('salesperson')['revenue'].sum().sort_values(ascending=False).head(10).reset_index()
        chart_data['top_salespeople'] = top_sales.to_dict('records')
    else:
        chart_data['top_salespeople'] = []
    
    # Top Products
    if "product_name" in df.columns and "revenue" in df.columns:
        top_products = df.groupby('product_name')['revenue'].sum().sort_values(ascending=False).head(10).reset_index()
        top_products.columns = ['product', 'revenue']
        chart_data['top_products'] = top_products.to_dict('records')
    else:
        chart_data['top_products'] = []
    
    # Salesperson Leaderboard
    if "salesperson" in df.columns and "revenue" in df.columns:
        leaderboard = df.groupby('salesperson').agg({
            'revenue': 'sum',
            'order_id': 'count'
        }).sort_values('revenue', ascending=False).head(10).reset_index()
        leaderboard.columns = ['salesperson', 'revenue', 'orders']
        leaderboard['total_revenue'] = leaderboard['revenue'].apply(lambda x: f"${x:,.2f}")
        leaderboard['total_orders'] = leaderboard['orders']
        chart_data['salesperson_leaderboard'] = leaderboard[['salesperson', 'total_revenue', 'total_orders']].to_dict('records')
    else:
        chart_data['salesperson_leaderboard'] = []
    
    # Regional Performance
    if "region" in df.columns and "revenue" in df.columns:
        regional_perf = df.groupby('region').agg({
            'revenue': 'sum',
            'order_id': 'count',
            'customer_id': 'nunique'
        }).sort_values('revenue', ascending=False).reset_index()
        regional_perf.columns = ['region', 'revenue', 'orders', 'customers']
        regional_perf['total_revenue'] = regional_perf['revenue'].apply(lambda x: f"${x:,.2f}")
        regional_perf['total_orders'] = regional_perf['orders']
        regional_perf['unique_customers'] = regional_perf['customers']
        chart_data['regional_performance'] = regional_perf[['region', 'total_revenue', 'total_orders', 'unique_customers']].to_dict('records')
    else:
        chart_data['regional_performance'] = []
    
    # Sales by Category
    if "category" in df.columns and "revenue" in df.columns:
        cat_sales = df.groupby('category')['revenue'].sum().reset_index()
        chart_data['sales_by_category'] = cat_sales.to_dict('records')
    else:
        chart_data['sales_by_category'] = []
    
    # Units by Category
    if "category" in df.columns and "units" in df.columns:
        cat_units = df.groupby('category')['units'].sum().reset_index()
        chart_data['units_by_category'] = cat_units.to_dict('records')
    else:
        chart_data['units_by_category'] = []
    
    # Product Performance Table
    if "product_name" in df.columns and "revenue" in df.columns:
        product_analysis = df.groupby('product_name').agg({
            'revenue': 'sum',
            'units': 'sum',
            'order_id': 'count'
        }).sort_values('revenue', ascending=False).reset_index()
        product_analysis.columns = ['product_name', 'revenue', 'units', 'orders']
        product_analysis['avg_revenue'] = product_analysis['revenue'] / product_analysis['orders']
        product_analysis['total_revenue'] = product_analysis['revenue'].apply(lambda x: f"${x:,.2f}")
        product_analysis['units_sold'] = product_analysis['units'].astype(int)
        product_analysis['num_orders'] = product_analysis['orders'].astype(int)
        product_analysis['avg_revenue_per_order'] = product_analysis['avg_revenue'].apply(lambda x: f"${x:,.2f}")
        chart_data['product_performance'] = product_analysis[['product_name', 'total_revenue', 'units_sold', 'num_orders', 'avg_revenue_per_order']].to_dict('records')
    else:
        chart_data['product_performance'] = []
    
    # Customer Type
    if "is_returning" in df.columns:
        customer_type = df.groupby('is_returning')['customer_id'].nunique().reset_index()
        customer_type['type'] = customer_type['is_returning'].map({0: 'New', 1: 'Returning'})
        customer_type.columns = ['is_returning', 'count', 'type']
        chart_data['customer_type'] = customer_type[['type', 'count']].to_dict('records')
    else:
        chart_data['customer_type'] = []
    
    # AOV by Type
    if "is_returning" in df.columns and "aov" in df.columns:
        aov_by_type = df.groupby('is_returning')['aov'].mean().reset_index()
        aov_by_type['type'] = aov_by_type['is_returning'].map({0: 'New', 1: 'Returning'})
        aov_by_type.columns = ['is_returning', 'aov', 'type']
        chart_data['aov_by_type'] = aov_by_type[['type', 'aov']].to_dict('records')
    else:
        chart_data['aov_by_type'] = []
    
    # Top Customers
    if "customer_id" in df.columns and "revenue" in df.columns:
        top_customers = df.groupby('customer_id')['revenue'].sum().sort_values(ascending=False).head(10).reset_index()
        # Format customer names nicely
        top_customers['customer'] = top_customers['customer_id'].apply(lambda x: f"Customer {str(x)[:8]}")
        chart_data['top_customers'] = top_customers[['customer', 'revenue']].to_dict('records')
    else:
        chart_data['top_customers'] = []
    
    # Order Frequency
    if "customer_id" in df.columns:
        order_freq = df.groupby('customer_id')['order_id'].count().value_counts().sort_index().reset_index()
        order_freq.columns = ['num_orders', 'count']
        order_freq['orders'] = order_freq['num_orders'].astype(str) + ' orders'
        chart_data['order_frequency'] = order_freq[['orders', 'count']].to_dict('records')
    else:
        chart_data['order_frequency'] = []
    
    return chart_data

@app.route('/api/demo-data', methods=['GET'])
def load_demo_data():
    """Load demo data"""
    try:
        demo_path = os.path.join(os.path.dirname(__file__), 'data', 'demo_sales.csv')
        if not os.path.exists(demo_path):
            return jsonify({'error': 'Demo data not found at: ' + demo_path}), 404
        
        df = data_logic.load_data_from_file(demo_path)
        current_data['df'] = df
        
        min_date = df["order_date"].min().date().isoformat() if not df["order_date"].isna().all() else None
        max_date = df["order_date"].max().date().isoformat() if not df["order_date"].isna().all() else None
        
        regions = sorted(df['region'].dropna().unique().tolist()) if 'region' in df.columns else []
        salespeople = sorted(df['salesperson'].dropna().unique().tolist()) if 'salesperson' in df.columns else []
        categories = sorted(df['category'].dropna().unique().tolist()) if 'category' in df.columns else []
        
        return jsonify({
            'success': True,
            'record_count': len(df),
            'min_date': min_date,
            'max_date': max_date,
            'regions': regions,
            'salespeople': salespeople,
            'categories': categories
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and process CSV file"""
    try:
        print("Upload endpoint hit")
        if 'file' not in request.files:
            print("No file in request")
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        print(f"File received: {file.filename}")
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        df = data_logic.load_data_from_buffer(file)
        print(f"Data loaded: {len(df)} rows")
        current_data['df'] = df
        
        min_date = df["order_date"].min().date().isoformat() if not df["order_date"].isna().all() else None
        max_date = df["order_date"].max().date().isoformat() if not df["order_date"].isna().all() else None
        
        regions = sorted(df['region'].dropna().unique().tolist()) if 'region' in df.columns else []
        salespeople = sorted(df['salesperson'].dropna().unique().tolist()) if 'salesperson' in df.columns else []
        categories = sorted(df['category'].dropna().unique().tolist()) if 'category' in df.columns else []
        
        print("Upload successful")
        return jsonify({
            'success': True,
            'record_count': len(df),
            'min_date': min_date,
            'max_date': max_date,
            'regions': regions,
            'salespeople': salespeople,
            'categories': categories
        })
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/filter', methods=['POST'])
def filter_data():
    """Apply filters and return filtered data with charts"""
    try:
        print("Filter endpoint hit")
        if 'df' not in current_data:
            print("No data loaded in current_data")
            return jsonify({'error': 'No data loaded'}), 400
        
        data = request.json
        print(f"Filter data received: {data}")
        
        date_from = pd.to_datetime(data.get('date_from')).date()
        date_to = pd.to_datetime(data.get('date_to')).date()
        regions = data.get('regions', [])
        salespeople = data.get('salespeople', [])
        categories = data.get('categories', [])
        
        print(f"Applying filters: dates={date_from} to {date_to}, regions={regions}, sales={salespeople}, cats={categories}")
        
        df_filtered = data_logic.apply_filters(
            current_data['df'],
            date_from,
            date_to,
            regions if regions else ['All'],
            salespeople if salespeople else ['All'],
            categories if categories else ['All']
        )
        
        print(f"Filtered data: {len(df_filtered)} rows")
        
        kpis = data_logic.compute_kpis(df_filtered)
        chart_data = prepare_chart_data(df_filtered)
        
        print("Filter completed successfully")
        return jsonify({
            'kpis': kpis,
            'filtered_data': chart_data
        })
    except Exception as e:
        print(f"Filter error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_filtered():
    """Download filtered data as CSV"""
    try:
        if 'df' not in current_data:
            return jsonify({'error': 'No data loaded'}), 400
        
        data = request.json
        date_from = pd.to_datetime(data.get('date_from')).date()
        date_to = pd.to_datetime(data.get('date_to')).date()
        regions = data.get('regions', [])
        salespeople = data.get('salespeople', [])
        categories = data.get('categories', [])
        
        df_filtered = data_logic.apply_filters(
            current_data['df'],
            date_from,
            date_to,
            regions if regions else ['All'],
            salespeople if salespeople else ['All'],
            categories if categories else ['All']
        )
        
        # Create CSV in memory
        output = BytesIO()
        df_filtered.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name='filtered_sales.csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
