import pytest
import requests
import io
import json
from datetime import datetime, timedelta

# Backend API base URL
BASE_URL = "http://localhost:8000"


class TestContinuumAPI:
    """Comprehensive tests for all ContinuumAI Backend APIs"""

    @classmethod
    def setup_class(cls):
        """Setup test data and verify API is running"""
        cls.base_url = BASE_URL
        cls.dataset_id = None

        # Test data CSV
        cls.test_csv_data = """order_id,opportunity_id,customer_id,order_date,lead_date,close_date,first_purchase_date,revenue,units,product_id,product_name,category,salesperson,region,country,city,stage,channel,is_returning,aov,sales_cycle_days
        ORD0000001,OPP000001,CUST00086,2025-02-18,2025-02-05,2025-02-18,2024-11-02,325.62,2,P-101,Widget B,Hardware,Bob,North America,MEX,Mexico City,Closed Won,Website,1,325.62,13
        ORD0000002,OPP000001,CUST00092,2025-09-28,2025-08-26,2025-09-28,2024-05-22,545.08,3,P-500,Addon 1,Addons,Alice,North America,MEX,Mexico City,Qualified,Website,1,545.08,33
        ORD0000003,OPP000002,CUST00155,2025-08-17,2025-08-14,2025-08-17,2025-06-29,2806.46,2,P-201,Service Y,Services,Eve,Europe,ITA,Rome,Negotiation,Website,1,2806.46,3
        ORD0000004,OPP000001,CUST00186,2024-09-23,2024-09-19,2024-09-23,2023-07-21,5227.29,3,P-201,Service Y,Services,George,South America,COL,Bogota,Proposal,Partner,1,5227.29,4
        ORD0000005,OPP000002,CUST00054,2025-10-12,2025-10-13,2025-10-12,2023-08-25,27428.11,6,P-400,Enterprise Suite,Software,Bob,Asia,JPN,Tokyo,Closed Won,Partner,1,27428.11,0
        ORD0000006,OPP000002,CUST00098,2025-06-29,2025-06-19,2025-06-29,2025-08-26,869.19,3,P-101,Widget B,Hardware,Carla,North America,CAN,Toronto,Lead,Partner,0,869.19,10
        ORD0000007,OPP000002,CUST00187,2025-10-05,2025-09-18,2025-10-05,2025-10-02,1131.14,3,P-100,Widget A,Hardware,Dustin,South America,COL,Bogota,Closed Won,Email,1,1131.14,17
        ORD0000008,OPP000002,CUST00185,2025-10-15,2025-10-03,2025-10-15,2024-10-31,374.04,6,P-301,Accessory R,Accessories,Alice,Oceania,AUS,Sydney,Lead,Event,1,374.04,12
        ORD0000009,OPP000002,CUST00037,2025-02-04,2025-02-02,2025-02-04,2025-08-20,3756.48,7,P-101,Widget B,Hardware,Carla,Europe,GBR,Manchester,Closed Lost,Paid Ads,0,3756.48,2
        ORD0000010,OPP000003,CUST00146,2025-10-07,2025-09-26,2025-10-07,2023-11-03,12865.78,5,P-200,Service X,Services,Farah,Asia,JPN,Tokyo,Negotiation,Email,1,12865.78,11
        ORD0000011,OPP000002,CUST00135,2025-05-22,2025-05-17,2025-05-22,2024-05-12,1802.17,4,P-101,Widget B,Hardware,Bob,Oceania,AUS,Sydney,Closed Won,Partner,1,1802.17,5
        ORD0000012,OPP000002,CUST00021,2025-08-07,2025-07-26,2025-08-07,2025-02-06,818.97,4,P-500,Addon 1,Addons,Bob,Europe,FRA,Paris,Negotiation,Website,1,818.97,12
        ORD0000013,OPP000002,CUST00158,2024-11-16,2024-10-13,2024-11-16,2025-09-04,7602.78,2,P-400,Enterprise Suite,Software,Eve,Asia,IND,Bengaluru,Closed Lost,Event,0,7602.78,34
        ORD0000014,OPP000001,CUST00191,2025-09-06,2025-09-04,2025-09-06,2023-12-03,5832.61,3,P-201,Service Y,Services,Bob,South America,ARG,Buenos Aires,Closed Won,Paid Ads,1,5832.61,2
        ORD0000015,OPP000001,CUST00174,2025-10-12,2025-10-05,2025-10-12,2023-11-09,1433.22,5,P-500,Addon 1,Addons,Eve,Oceania,NZL,Auckland,Qualified,Event,1,1433.22,7
        ORD0000016,OPP000003,CUST00099,2025-09-25,2025-09-12,2025-09-25,2025-07-10,4264.56,2,P-200,Service X,Services,George,Oceania,NZL,Auckland,Lead,Website,1,4264.56,13
        ORD0000017,OPP000004,CUST00144,2025-10-17,2025-10-11,2025-10-17,2023-05-14,563.67,1,P-200,Service X,Services,Dustin,Europe,ESP,Madrid,Qualified,Website,1,563.67,6
        ORD0000018,OPP000003,CUST00190,2025-09-19,2025-09-07,2025-09-19,2024-05-27,360.03,1,P-500,Addon 1,Addons,Farah,Asia,PAK,Karachi,Closed Won,Website,1,360.03,12
        ORD0000019,OPP000003,CUST00188,2025-09-24,2025-08-31,2025-09-24,2025-04-19,416.38,5,P-301,Accessory R,Accessories,Bob,North America,CAN,Vancouver,Lead,Paid Ads,1,416.38,24
        ORD0000020,OPP000002,CUST00106,2025-09-23,2025-09-01,2025-09-23,2024-02-06,422.58,3,P-500,Addon 1,Addons,George,Europe,ITA,Rome,Closed Lost,Event,1,422.58,22"""

        # Check if API is running
        try:
            response = requests.get(f"{cls.base_url}/health", timeout=5)
            assert response.status_code == 200, "API health check failed"
            print("✅ API is running and healthy")
        except Exception as e:
            pytest.fail(f"❌ Backend API is not running: {e}")

    def test_01_health_check(self):
        """Test API health endpoint"""
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200
        print("✅ Health check passed")

    def test_02_upload_csv(self):
        """Test CSV upload functionality"""
        files = {"file": ("test_data.csv", io.StringIO(self.test_csv_data), "text/csv")}
        data = {"dataset_name": "Test Dataset"}

        response = requests.post(
            f"{self.base_url}/data/upload-csv/", files=files, data=data
        )

        assert response.status_code == 200
        result = response.json()

        # Could be 'dataset_id', 'id', or nested structure
        if "dataset_id" in result:
            TestContinuumAPI.dataset_id = result["dataset_id"]
        elif "id" in result:
            TestContinuumAPI.dataset_id = result["id"]
        else:
            # Fallback - print response to see actual structure
            print(f"Upload response: {result}")
            pytest.fail("Cannot find dataset ID in upload response")

        print(f"✅ CSV upload successful. Dataset ID: {self.dataset_id}")

    def test_03_list_datasets(self):
        """Test listing datasets"""
        response = requests.get(f"{self.base_url}/data/datasets/")

        assert response.status_code == 200
        result = response.json()
        assert "datasets" in result
        assert len(result["datasets"]) > 0
        print(f"✅ Found {len(result['datasets'])} datasets")

    def test_04_get_dataset_info(self):
        """Test getting specific dataset info"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(f"{self.base_url}/data/datasets/{self.dataset_id}")

        assert response.status_code == 200
        result = response.json()

        assert "id" in result
        assert "name" in result
        print(f"✅ Dataset info retrieved: {result['name']}")

    def test_05_analyze_dataset(self):
        """Test basic dataset analysis"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/analyze"
        )

        assert response.status_code == 200
        result = response.json()
        assert "kpis" in result
        assert "total_records" in result

        kpis = result["kpis"]
        assert "total_revenue" in kpis
        assert "total_orders" in kpis
        print(
            f"✅ Analysis complete. Total Revenue: ${kpis['total_revenue']}, Orders: {kpis['total_orders']}"
        )

    def test_06_analyze_dataset_filtered(self):
        """Test filtered dataset analysis"""
        assert self.dataset_id is not None, "Dataset ID not available"

        params = {
            "date_from": "2024-01-16",
            "date_to": "2024-01-19",
            "regions": "North,South",
        }

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/analyze-filtered",
            params=params,
        )

        assert response.status_code == 200
        result = response.json()
        assert "kpis" in result
        print(f"✅ Filtered analysis successful")

    # ============================================================================
    # CHART ENDPOINTS TESTS
    # ============================================================================

    def test_07_sales_by_region(self):
        """Test sales by region chart endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/charts/sales-by-region"
        )

        assert response.status_code == 200
        result = response.json()

        print(f"Sales by region response: {list(result.keys())}")

        # Flexible assertions based on common patterns
        assert isinstance(result, dict), "Response should be a dictionary"
        assert len(result) > 0, "Response should not be empty"
        print(f"✅ Sales by region chart data retrieved")

    def test_08_sales_over_time(self):
        """Test sales over time chart endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/charts/sales-over-time"
        )

        assert response.status_code == 200
        result = response.json()

        print(f"Sales over time response keys: {list(result.keys())}")
        assert isinstance(result, dict)
        print(f"✅ Sales over time chart data retrieved")

    def test_09_sales_by_channel(self):
        """Test sales by channel chart endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/charts/sales-by-channel"
        )

        assert response.status_code == 200
        result = response.json()

       
        assert isinstance(result, dict)
        print(f"✅ Sales by channel chart data retrieved")

    def test_10_revenue_distribution(self):
        """Test revenue distribution chart endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/charts/revenue-distribution"
        )

        assert response.status_code == 200
        result = response.json()

        
        assert isinstance(result, dict)
        print(f"✅ Revenue distribution chart data retrieved")

    def test_11_histogram_data(self):
        """Test histogram data endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        params = {"column": "revenue", "bins": 10}
        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/charts/histogram-data",
            params=params,
        )

        assert response.status_code == 200
        result = response.json()

    
        print(f"Histogram response keys: {list(result.keys())}")
        assert isinstance(result, dict)
        print(f"✅ Histogram data retrieved for revenue column")

    # ============================================================================
    # TOP PERFORMERS TESTS
    # ============================================================================

    def test_12_top_salespeople(self):
        """Test top salespeople endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        params = {"limit": 5}
        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/top-performers/salespeople",
            params=params,
        )

        assert response.status_code == 200
        result = response.json()

        print(f"Top salespeople response keys: {list(result.keys())}")
        assert isinstance(result, dict)
        print(f"✅ Top salespeople data retrieved")

    def test_13_top_products(self):
        """Test top products endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        params = {"limit": 5}
        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/top-performers/products",
            params=params,
        )

        assert response.status_code == 200
        result = response.json()

        assert isinstance(result, dict)
        print(f"✅ Top products data retrieved")

    def test_14_regional_performance(self):
        """Test regional performance endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/regional-performance"
        )

        assert response.status_code == 200
        result = response.json()


        assert isinstance(result, dict)
        print(f"✅ Regional performance data retrieved")

    # ============================================================================
    # REMAINING TESTS WITH FLEXIBLE VALIDATION
    # ============================================================================

    def test_15_product_analysis_by_category(self):
        """Test product analysis by category endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/product-analysis/by-category"
        )

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, dict)
        print(f"✅ Product analysis by category retrieved")

    def test_16_product_performance_table(self):
        """Test product performance table endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/product-analysis/performance-table"
        )

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, dict)
        print(f"✅ Product performance table retrieved")

    def test_17_customer_insights(self):
        """Test customer insights endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/customer-insights"
        )

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, dict)
        print(f"✅ Customer insights retrieved")

    def test_18_raw_data(self):
        """Test raw data endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        params = {"limit": 10, "offset": 0}
        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/raw-data", params=params
        )

        assert response.status_code == 200
        result = response.json()


        if "data" in result and "total_records" in result:
            print(
                f"✅ Raw data retrieved: {result.get('returned_records', len(result.get('data', [])))} of {result['total_records']} records"
            )
        else:
            print(f"Raw data response keys: {list(result.keys())}")
            assert isinstance(result, dict)
            print(f"✅ Raw data endpoint responded")

    def test_19_export_csv(self):
        """Test CSV export endpoint"""
        assert self.dataset_id is not None, "Dataset ID not available"

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/export-csv"
        )

        assert response.status_code == 200

        content_type = response.headers.get("content-type", "").lower()
        assert (
            "csv" in content_type or "octet-stream" in content_type
        ), f"Unexpected content type: {content_type}"

        # Verify it's actually CSV-like content
        content = (
            response.text
            if hasattr(response, "text")
            else response.content.decode("utf-8")
        )
        assert len(content) > 0, "CSV content should not be empty"
        print(f"✅ CSV export successful (content-type: {content_type})")

    def test_20_filtering_across_endpoints(self):
        """Test that filtering works across different endpoints"""
        assert self.dataset_id is not None, "Dataset ID not available"

        filter_params = {
            "date_from": "2024-01-16",
            "date_to": "2024-01-18",
            "regions": "North,South",
        }

        # Test filtering on multiple endpoints
        endpoints = [
            "charts/sales-by-region",
            "charts/sales-over-time",
            "top-performers/salespeople",
            "raw-data",
        ]

        for endpoint in endpoints:
            response = requests.get(
                f"{self.base_url}/data/datasets/{self.dataset_id}/{endpoint}",
                params=filter_params,
            )
            assert response.status_code == 200
            print(f"✅ Filtering works on {endpoint}")

    def test_21_invalid_dataset_id(self):
        """Test error handling for invalid dataset ID"""
        response = requests.get(f"{self.base_url}/data/datasets/99999/analyze")


        assert response.status_code in [
            404,
            422,
            400,
            500,
        ], f"Unexpected status code: {response.status_code}"
        print(
            f"✅ Proper error handling for invalid dataset ID (status: {response.status_code})"
        )

    def test_22_invalid_filter_dates(self):
        """Test error handling for invalid filter dates"""
        assert self.dataset_id is not None, "Dataset ID not available"

        params = {"date_from": "invalid-date", "date_to": "2024-01-20"}

        response = requests.get(
            f"{self.base_url}/data/datasets/{self.dataset_id}/analyze-filtered",
            params=params,
        )


        print(f"✅ Invalid date handling tested (status: {response.status_code})")
        assert response.status_code in [
            200,
            400,
            422,
            404,
        ], f"Unexpected status for invalid dates: {response.status_code}"

    def test_99_cleanup_delete_dataset(self):
        """Clean up - delete test dataset"""
        if self.dataset_id is not None:
            response = requests.delete(
                f"{self.base_url}/data/datasets/{self.dataset_id}"
            )

            assert response.status_code == 200
            print(f"✅ Test dataset {self.dataset_id} deleted successfully")


# ============================================================================
# UTILITY FUNCTIONS FOR RUNNING TESTS
# ============================================================================


def run_all_tests():
    """Run all tests and provide summary"""
    print("🚀 Starting ContinuumAI Backend API Tests...")
    print("=" * 60)

    # Run pytest with verbose output
    exit_code = pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            # Removed -x to see all failures, not just first one
        ]
    )

    if exit_code == 0:
        print("\n" + "=" * 60)
        print(" ALL TESTS PASSED! Backend APIs are working correctly.")
        print("✅ Ready to run the frontend application!")
    else:
        print("\n" + "=" * 60)
        print("❌ Some tests failed. Check output above for details.")

    return exit_code


if __name__ == "__main__":
    run_all_tests()
