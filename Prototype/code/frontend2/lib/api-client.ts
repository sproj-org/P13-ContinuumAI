// lib/api-client.ts

/**
 * API client to interact with ContinuumAI backend
 * TypeScript port of the Python api_client.py
 */

// import axios, { AxiosResponse } from 'axios';
import { axiosAuth } from './auth';
import type { AxiosResponse } from 'axios';

export interface Dataset {
  id: number;
  name: string;
  total_records: number;
}

export interface KPIs {
  total_revenue: number;
  total_orders: number;
  avg_aov: number;
  conversion_rate: number;
  new_count: number;
  returning_count: number;
}

export interface AnalysisResult {
  kpis: KPIs;
  total_records: number;
  data_preview: any[];
}

export interface ChartData {
  labels: string[];
  values: number[];
}

export interface FilterParams {
  date_from?: string;
  date_to?: string;
  regions?: string[];
  reps?: string[];
  categories?: string[];
}

export interface FilterOptions {
  regions: string[];
  reps: string[];
  categories: string[];
}

export class ContinuumAPIClient {
  private baseUrl: string;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl;
  }

  /**
   * Upload CSV file to backend and return dataset_id
   */
  async uploadCSV(file: File, datasetName?: string): Promise<number | null> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('dataset_name', datasetName || file.name.replace('.csv', ''));

      const response = await axiosAuth.post(
        `${this.baseUrl}/data/upload-csv/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 30000,
        }
      );

      if (response.status === 200) {
        return response.data.dataset_id;
      }
      throw new Error(response.data.detail || 'Unknown error');
    } catch (error: any) {
      throw new Error(`Error uploading CSV: ${error.message}`);
    }
  }

  /**
   * Upload demo CSV data as string
   */
  async uploadDemoCSV(csvData: string, filename: string = "demo_data.csv", datasetName: string = "Demo Sales Data"): Promise<number | null> {
    try {
      const blob = new Blob([csvData], { type: 'text/csv' });
      const file = new File([blob], filename, { type: 'text/csv' });
      return await this.uploadCSV(file, datasetName);
    } catch (error: any) {
      throw new Error(`Error uploading demo CSV: ${error.message}`);
    }
  }

  /**
   * Get list of all datasets
   */
  async getDatasets(): Promise<Dataset[]> {
    try {
      const response = await axiosAuth.get(`${this.baseUrl}/data/datasets/`, { timeout: 10000 });
      if (response.status === 200) {
        return response.data.datasets || [];
      }
      return [];
    } catch (error: any) {
      throw new Error(`Error fetching datasets: ${error.message}`);
    }
  }

  /**
   * Get KPIs and analysis for a dataset
   */
  async analyzeDataset(datasetId: number): Promise<AnalysisResult | null> {
    try {
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/analyze`,
        { timeout: 30000 }
      );
      if (response.status === 200) {
        return response.data;
      }
      throw new Error(response.data.detail || 'Unknown error');
    } catch (error: any) {
      throw new Error(`Error analyzing dataset: ${error.message}`);
    }
  }

  /**
   * Check if API is running
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await axiosAuth.get(`${this.baseUrl}/health`, { timeout: 5000 });
      return response.status === 200;
    } catch {
      return false;
    }
  }

  /**
   * Delete a dataset
   */
  async deleteDataset(datasetId: number): Promise<boolean> {
    try {
      const response = await axiosAuth.delete(
        `${this.baseUrl}/data/datasets/${datasetId}`,
        { timeout: 10000 }
      );
      if (response.status === 200) {
        return true;
      }
      throw new Error(response.data.detail || 'Unknown error');
    } catch (error: any) {
      throw new Error(`Error deleting dataset: ${error.message}`);
    }
  }

  /**
   * Get filtered KPIs and analysis for a dataset
   */
  async analyzeDatasetFiltered(datasetId: number, filters: FilterParams): Promise<AnalysisResult | null> {
    try {
      const params = this.buildFilterParams(filters);
      
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/analyze-filtered`,
        {
          params,
          timeout: 30000
        }
      );
      
      if (response.status === 200) {
        return response.data;
      }
      throw new Error(response.data.detail || 'Unknown error');
    } catch (error: any) {
      throw new Error(`Error analyzing filtered dataset: ${error.message}`);
    }
  }

  /**
   * Get available filter options for a dataset
   */
  async getFilterOptions(datasetId: number): Promise<FilterOptions> {
    try {
      // Get basic analysis to extract filter options
      const analysis = await this.analyzeDataset(datasetId);
      if (analysis && analysis.data_preview) {
        const options: FilterOptions = {
          regions: [],
          reps: [],
          categories: []
        };

        // Extract unique values for filters from preview data
        analysis.data_preview.forEach((row: any) => {
          if (row.region && !options.regions.includes(row.region)) {
            options.regions.push(row.region);
          }
          if (row.salesperson && !options.reps.includes(row.salesperson)) {
            options.reps.push(row.salesperson);
          }
          if (row.category && !options.categories.includes(row.category)) {
            options.categories.push(row.category);
          }
        });

        return options;
      }
      return { regions: [], reps: [], categories: [] };
    } catch (error: any) {
      throw new Error(`Error getting filter options: ${error.message}`);
    }
  }

  // ============================================================================
  // CHART DATA METHODS - All support filtering
  // ============================================================================

  private buildFilterParams(filters: FilterParams): Record<string, string> {
    const params: Record<string, string> = {};
    
    if (filters.date_from) {
      params.date_from = filters.date_from;
    }
    if (filters.date_to) {
      params.date_to = filters.date_to;
    }
    if (filters.regions && filters.regions.length > 0) {
      params.regions = filters.regions.join(',');
    }
    if (filters.reps && filters.reps.length > 0) {
      params.reps = filters.reps.join(',');
    }
    if (filters.categories && filters.categories.length > 0) {
      params.categories = filters.categories.join(',');
    }
    
    return params;
  }

  async getSalesByRegion(datasetId: number, filters: FilterParams = {}): Promise<ChartData | null> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/charts/sales-by-region`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching sales by region: ${error.message}`);
    }
  }

  async getSalesOverTime(datasetId: number, filters: FilterParams = {}): Promise<ChartData | null> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/charts/sales-over-time`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching sales over time: ${error.message}`);
    }
  }

  async getSalesByChannel(datasetId: number, filters: FilterParams = {}): Promise<ChartData | null> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/charts/sales-by-channel`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching sales by channel: ${error.message}`);
    }
  }

  async getRevenueDistribution(datasetId: number, filters: FilterParams = {}): Promise<ChartData | null> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/charts/revenue-distribution`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching revenue distribution: ${error.message}`);
    }
  }

  async getHistogramData(datasetId: number, column: string = "revenue", bins: number = 20, filters: FilterParams = {}): Promise<ChartData | null> {
    try {
      const params = {
        ...this.buildFilterParams(filters),
        column,
        bins: bins.toString()
      };
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/charts/histogram-data`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching histogram data: ${error.message}`);
    }
  }

  // ============================================================================
  // TOP PERFORMERS METHODS
  // ============================================================================

  async getTopSalespeople(datasetId: number, limit: number = 10, filters: FilterParams = {}): Promise<any> {
    try {
      const params = {
        ...this.buildFilterParams(filters),
        limit: limit.toString()
      };
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/top-performers/salespeople`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching top salespeople: ${error.message}`);
    }
  }

  async getTopProducts(datasetId: number, limit: number = 10, filters: FilterParams = {}): Promise<any> {
    try {
      const params = {
        ...this.buildFilterParams(filters),
        limit: limit.toString()
      };
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/top-performers/products`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching top products: ${error.message}`);
    }
  }

  async getRegionalPerformance(datasetId: number, filters: FilterParams = {}): Promise<any> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/regional-performance`,
        { params, timeout: 30000 }
      );
      console.log(response.data)
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching regional performance: ${error.message}`);
    }
  }

  // ============================================================================
  // PRODUCT ANALYSIS METHODS
  // ============================================================================

  async getProductAnalysisByCategory(datasetId: number, filters: FilterParams = {}): Promise<any> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/product-analysis/by-category`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching product analysis by category: ${error.message}`);
    }
  }

  async getProductPerformanceTable(datasetId: number, filters: FilterParams = {}): Promise<any> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/product-analysis/performance-table`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching product performance table: ${error.message}`);
    }
  }

  // ============================================================================
  // CUSTOMER INSIGHTS METHODS
  // ============================================================================

  async getCustomerInsights(datasetId: number, filters: FilterParams = {}): Promise<any> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/customer-insights`,
        { params, timeout: 30000 }
      );
      console.log(response.data)
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching customer insights: ${error.message}`);
    }
  }

  // ============================================================================
  // DATA EXPORT & RAW DATA METHODS
  // ============================================================================

  async exportFilteredCSV(datasetId: number, filters: FilterParams = {}): Promise<Blob | null> {
    try {
      const params = this.buildFilterParams(filters);
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/export-csv`,
        {
          params,
          timeout: 30000,
          responseType: 'blob'
        }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error exporting CSV: ${error.message}`);
    }
  }

  async getRawData(datasetId: number, limit?: number, offset: number = 0, filters: FilterParams = {}): Promise<any> {
    try {
      const params: Record<string, string> = {
        ...this.buildFilterParams(filters),
        offset: offset.toString()
      };
      
      if (limit) {
        params.limit = limit.toString();
      }
      
      const response = await axiosAuth.get(
        `${this.baseUrl}/data/datasets/${datasetId}/raw-data`,
        { params, timeout: 30000 }
      );
      return response.status === 200 ? response.data : null;
    } catch (error: any) {
      throw new Error(`Error fetching raw data: ${error.message}`);
    }
  }
}

// Export a singleton instance
export const apiClient = new ContinuumAPIClient();