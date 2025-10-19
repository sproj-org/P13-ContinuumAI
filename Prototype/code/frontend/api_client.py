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
    
    