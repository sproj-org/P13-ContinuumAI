#api_client.py

"""
API client to interact with ContinuumAI backend
"""
import requests
import pandas as pd
import streamlit as st
from typing import Optional, Dict, Any, List
import io

class ContinuumAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    def upload_csv(self, file_data, filename: str, dataset_name: str = None) -> Optional[int]:
        """Upload CSV file to backend and return dataset_id"""
        try:
            files = {'file': (filename, file_data, 'text/csv')}
            data = {'dataset_name': dataset_name or filename.replace('.csv', '')}
            
            response = requests.post(
                f"{self.base_url}/data/upload-csv/", 
                files=files, 
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('dataset_id')
            else:
                st.error(f"Upload failed: {response.json().get('detail', 'Unknown error')}")
                return None
                
        except Exception as e:
            st.error(f"Error uploading CSV: {e}")
            return None
    
    def get_datasets(self) -> List[Dict]:
        """Get list of all datasets"""
        try:
            response = requests.get(f"{self.base_url}/data/datasets/", timeout=10)
            if response.status_code == 200:
                return response.json().get('datasets', [])
            return []
        except Exception as e:
            st.error(f"Error fetching datasets: {e}")
            return []
    
    def analyze_dataset(self, dataset_id: int) -> Optional[Dict]:
        """Get KPIs and analysis for a dataset"""
        try:
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/analyze", 
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Analysis failed: {response.json().get('detail', 'Unknown error')}")
                return None
        except Exception as e:
            st.error(f"Error analyzing dataset: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if API is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
        
    def delete_dataset(self, dataset_id: int) -> bool:
        """Delete a dataset"""
        try:
            response = requests.delete(
                f"{self.base_url}/data/datasets/{dataset_id}",
                timeout=10
            )
            if response.status_code == 200:
                return True
            else:
                st.error(f"Delete failed: {response.json().get('detail', 'Unknown error')}")
                return False
        except Exception as e:
            st.error(f"Error deleting dataset: {e}")
            return False

    def analyze_dataset_filtered(self, dataset_id: int, date_from=None, date_to=None, 
                            regions=None, reps=None, categories=None) -> Optional[Dict]:
        """Get filtered KPIs and analysis for a dataset"""
        try:
            params = self._build_filter_params(date_from, date_to, regions, reps, categories)
            
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/analyze-filtered",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Filtered analysis failed: {response.json().get('detail', 'Unknown error')}")
                return None
        except Exception as e:
            st.error(f"Error analyzing filtered dataset: {e}")
            return None
        
    def get_filter_options(self, dataset_id: int) -> Dict[str, List]:
        """Get available filter options for a dataset"""
        try:
            # Get basic analysis to extract filter options
            analysis = self.analyze_dataset(dataset_id)
            if analysis and 'data_preview' in analysis:
                df = pd.DataFrame(analysis['data_preview'])
                
                # Extract unique values for filters
                options = {}
                if 'region' in df.columns:
                    options['regions'] = df['region'].dropna().unique().tolist()
                if 'salesperson' in df.columns:
                    options['reps'] = df['salesperson'].dropna().unique().tolist()
                if 'category' in df.columns:
                    options['categories'] = df['category'].dropna().unique().tolist()
                
                return options
            return {}
        except Exception as e:
            st.error(f"Error getting filter options: {e}")
            return {}

    def get_dataframe_from_analysis(self, analysis_result: Dict) -> pd.DataFrame:
        """Convert API analysis result back to DataFrame for compatibility"""
        if analysis_result and 'data_preview' in analysis_result:
            # Use the preview data or extend API to return full dataset
            return pd.DataFrame(analysis_result['data_preview'])
        return pd.DataFrame()
    

   # ============================================================================
    # CHART DATA METHODS - All support filtering
    # ============================================================================
    
    def _build_filter_params(self, date_from=None, date_to=None, regions=None, reps=None, categories=None):
        """Helper to build filter parameters"""
        params = {}
        if date_from:
            params['date_from'] = date_from.strftime('%Y-%m-%d') if hasattr(date_from, 'strftime') else str(date_from)
        if date_to:
            params['date_to'] = date_to.strftime('%Y-%m-%d') if hasattr(date_to, 'strftime') else str(date_to)
        if regions:
            params['regions'] = ','.join(regions) if isinstance(regions, list) else str(regions)
        if reps:
            params['reps'] = ','.join(reps) if isinstance(reps, list) else str(reps)
        if categories:
            params['categories'] = ','.join(categories) if isinstance(categories, list) else str(categories)
        return params

    def get_sales_by_region(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get sales by region chart data"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/charts/sales-by-region",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching sales by region: {e}")
            return None

    def get_sales_over_time(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get sales over time chart data"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/charts/sales-over-time",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching sales over time: {e}")
            return None

    def get_sales_by_channel(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get sales by channel chart data"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/charts/sales-by-channel",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching sales by channel: {e}")
            return None

    def get_revenue_distribution(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get revenue distribution histogram data"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/charts/revenue-distribution",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching revenue distribution: {e}")
            return None

    def get_histogram_data(self, dataset_id: int, column: str = "revenue", bins: int = 20, **filters) -> Optional[Dict]:
        """Get histogram data for any column"""
        try:
            params = self._build_filter_params(**filters)
            params.update({"column": column, "bins": bins})
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/charts/histogram-data",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching histogram data: {e}")
            return None

    # ============================================================================
    # TOP PERFORMERS METHODS
    # ============================================================================

    def get_top_salespeople(self, dataset_id: int, limit: int = 10, **filters) -> Optional[Dict]:
        """Get top salespeople data"""
        try:
            params = self._build_filter_params(**filters)
            params['limit'] = limit
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/top-performers/salespeople",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching top salespeople: {e}")
            return None

    def get_top_products(self, dataset_id: int, limit: int = 10, **filters) -> Optional[Dict]:
        """Get top products data"""
        try:
            params = self._build_filter_params(**filters)
            params['limit'] = limit
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/top-performers/products",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching top products: {e}")
            return None

    def get_regional_performance(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get regional performance data"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/regional-performance",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching regional performance: {e}")
            return None

    # ============================================================================
    # PRODUCT ANALYSIS METHODS
    # ============================================================================

    def get_product_analysis_by_category(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get product analysis by category"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/product-analysis/by-category",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching product analysis by category: {e}")
            return None

    def get_product_performance_table(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get product performance table"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/product-analysis/performance-table",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching product performance table: {e}")
            return None

    # ============================================================================
    # CUSTOMER INSIGHTS METHODS
    # ============================================================================

    def get_customer_insights(self, dataset_id: int, **filters) -> Optional[Dict]:
        """Get comprehensive customer insights"""
        try:
            params = self._build_filter_params(**filters)
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/customer-insights",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching customer insights: {e}")
            return None

    # ============================================================================
    # DATA EXPORT & RAW DATA METHODS
    # ============================================================================

    def export_filtered_csv(self, dataset_id: int, date_from=None, date_to=None, 
                        regions=None, reps=None, categories=None) -> Optional[bytes]:
        """Export filtered data as CSV"""

        try:
            params = self._build_filter_params(date_from, date_to, regions, reps, categories)

            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/export-csv",
                params=params,
                timeout=30
            )
            return response.content if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error exporting CSV: {e}")
            return None

    def get_raw_data(self, dataset_id: int, limit: Optional[int] = None, offset: int = 0, 
                    date_from=None, date_to=None, regions=None, reps=None, categories=None) -> Optional[Dict]:
        """Get raw filtered data for display"""
        try:
            params = self._build_filter_params(date_from, date_to, regions, reps, categories)
            if limit:
                params['limit'] = limit
            if offset:
                params['offset'] = offset
            
            response = requests.get(
                f"{self.base_url}/data/datasets/{dataset_id}/raw-data",
                params=params,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            st.error(f"Error fetching raw data: {e}")
            return None