"""
API tests that will only be able to run when the environment is set to testing in the env file
"""

import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv


# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Load environment variables from .env file (this only loads from current and parent dir so env must be there)
load_dotenv()

# Check environment before proceeding
if os.environ.get("ENVIRONMENT") != "testing":
    print("❌ TESTS WILL NOT RUN: Environment must be set to 'testing' in .env file")
    print(f"Current environment: {os.environ.get('ENVIRONMENT', 'None')}")
    exit(1)

# Configuration
BASE_URL = "http://localhost:8000"
DEMO_CSV_PATH = "../../data/demo_sales.csv"  # Adjust path from tests folder


def test_health():
    """Test if API is running"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("❌ API is not running. Start with: python main.py")
        return False


def test_upload_csv():
    """Test CSV upload"""
    print("\n📤 Testing CSV upload...")

    # Check if demo file exists
    if not os.path.exists(DEMO_CSV_PATH):
        print(f"❌ Demo CSV not found at: {DEMO_CSV_PATH}")
        return None

    try:
        with open(DEMO_CSV_PATH, "rb") as f:
            files = {"file": ("demo_sales.csv", f, "text/csv")}
            data = {"dataset_name": "Demo Sales Data"}

            response = requests.post(
                f"{BASE_URL}/data/upload-csv/", files=files, data=data
            )

        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        if response.status_code == 200:
            return result.get("dataset_id")
        return None

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


def test_list_datasets():
    """Test listing datasets"""
    print("\n📋 Testing list datasets...")
    try:
        response = requests.get(f"{BASE_URL}/data/datasets/")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Datasets: {json.dumps(result, indent=2)}")
        return result.get("datasets", [])
    except Exception as e:
        print(f"❌ List datasets failed: {e}")
        return []


def test_analyze_dataset(dataset_id):
    """Test dataset analysis"""
    print(f"\n📊 Testing dataset analysis for ID: {dataset_id}...")
    try:
        response = requests.get(f"{BASE_URL}/data/datasets/{dataset_id}/analyze")
        print(f"Status: {response.status_code}")
        result = response.json()

        if response.status_code == 200:
            print("✅ Analysis successful!")
            print(f"KPIs: {json.dumps(result.get('kpis', {}), indent=2)}")
            print(f"Total records: {result.get('total_records')}")
            print(f"Columns: {result.get('columns')}")
        else:
            print(f"❌ Analysis failed: {result}")

        return result
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return None


def main():
    """Run all tests"""
    print("🚀 Starting ContinuumAI API Tests")
    print(f"🔧 Environment set to: {os.environ.get('ENVIRONMENT')}")
    print("=" * 50)
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ API health check failed. Make sure the API is running.")
        return

    # Test 2: Upload CSV
    dataset_id = test_upload_csv()
    if not dataset_id:
        print("\n❌ CSV upload failed. Cannot continue with other tests.")
        return

    # Test 3: List datasets
    datasets = test_list_datasets()

    # Test 4: Analyze dataset
    if dataset_id:
        test_analyze_dataset(dataset_id)

    print("\n✅ All tests completed!")
    print(f"📁 Test database file: ./test_continuum.db")


if __name__ == "__main__":
    main()
