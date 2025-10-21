'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Upload, BarChart3, TrendingUp, Users, Map, FileText, AlertCircle, Loader2 } from 'lucide-react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { 
  ContinuumAPIClient, 
  Dataset, 
  AnalysisResult, 
  FilterParams, 
  FilterOptions, 
  ChartData 
} from '../lib/api-client';

import LogoutButton from './components/LogoutButton';

// Initialize API client
const apiClient = new ContinuumAPIClient();

// Tab Component Interfaces
interface TabProps {
  currentDatasetId: number;
  filters: FilterParams;
}

interface RawDataTabProps extends TabProps {
  currentPage: number;
  pageSize: number;
  setCurrentPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

// Chart Colors
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

// Helper function to safely extract numeric values
const extractNumericValue = (value: any): number => {
  if (typeof value === 'number') {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? 0 : parsed;
  }
  if (typeof value === 'object' && value !== null) {
    // If it's an object, try to sum up all numeric values
    const values = Object.values(value);
    return values.reduce((sum: number, val: any) => {
      const numVal = extractNumericValue(val);
      return sum + numVal;
    }, 0);
  }
  return 0;
};

// Sales Overview Tab Component
function SalesOverviewTab({ currentDatasetId, filters }: TabProps) {
  const [salesByRegion, setSalesByRegion] = useState<ChartData | null>(null);
  const [salesByChannel, setSalesByChannel] = useState<ChartData | null>(null);
  const [salesOverTime, setSalesOverTime] = useState<ChartData | null>(null);
  const [revenueDistribution, setRevenueDistribution] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [regionData, channelData, timeData, distData] = await Promise.all([
          apiClient.getSalesByRegion(currentDatasetId, filters),
          apiClient.getSalesByChannel(currentDatasetId, filters),
          apiClient.getSalesOverTime(currentDatasetId, filters),
          apiClient.getRevenueDistribution(currentDatasetId, filters)
        ]);

        setSalesByRegion(regionData);
        setSalesByChannel(channelData);
        setSalesOverTime(timeData);
        setRevenueDistribution(distData);
      } catch (error) {
        console.error('Error loading overview data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [currentDatasetId, filters]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h3 className="text-lg font-semibold text-gray-900">📈 Sales Overview</h3>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales by Region */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-4">Sales by Region</h4>
          {salesByRegion?.labels && salesByRegion?.values ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={salesByRegion.labels.map((label, index) => ({
                    name: label,
                    value: salesByRegion.values[index]
                  }))}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {salesByRegion.labels.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No regional data available
            </div>
          )}
        </div>

        {/* Sales by Channel */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-4">Sales by Channel</h4>
          {salesByChannel?.labels && salesByChannel?.values ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={salesByChannel.labels.map((label, index) => ({
                name: label,
                value: salesByChannel.values[index]
              }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis tickFormatter={(value) => `$${value.toLocaleString()}`} />
                <Tooltip formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']} />
                <Bar dataKey="value" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No channel data available
            </div>
          )}
        </div>
      </div>

      {/* Sales Over Time */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h4 className="font-medium text-gray-900 mb-4">Sales Over Time</h4>
        {salesOverTime?.labels && salesOverTime?.values ? (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={salesOverTime.labels.map((label, index) => ({
              date: format(parseISO(label), 'MMM dd'),
              value: salesOverTime.values[index]
            }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis tickFormatter={(value) => `$${value.toLocaleString()}`} />
              <Tooltip 
                formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Line type="monotone" dataKey="value" stroke="#8884d8" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500">
            No time series data available
          </div>
        )}
      </div>

      {/* Revenue Distribution */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h4 className="font-medium text-gray-900 mb-4">Revenue Distribution</h4>
        {revenueDistribution?.labels && revenueDistribution?.values ? (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={revenueDistribution.labels.map((label, index) => ({
              range: label,
              count: revenueDistribution.values[index]
            }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" />
              <YAxis />
              <Tooltip formatter={(value: any) => [value, 'Count']} />
              <Bar dataKey="count" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500">
            No revenue distribution data available
          </div>
        )}
      </div>
    </div>
  );
}

// Top Performers Tab Component
function TopPerformersTab({ currentDatasetId, filters }: TabProps) {
  const [topSalespeople, setTopSalespeople] = useState<any>(null);
  const [topProducts, setTopProducts] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [salespeople, products] = await Promise.all([
          apiClient.getTopSalespeople(currentDatasetId, 10, filters),
          apiClient.getTopProducts(currentDatasetId, 10, filters)
        ]);

        setTopSalespeople(salespeople);
        setTopProducts(products);
      } catch (error) {
        console.error('Error loading top performers data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [currentDatasetId, filters]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h3 className="text-lg font-semibold text-gray-900">🏆 Top Performers</h3>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Salespeople */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-4">Top Salespeople</h4>
          {topSalespeople?.leaderboard ? (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Salesperson
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Total Revenue
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {Object.entries(topSalespeople.leaderboard).map(([name, data]: [string, any]) => (
                      <tr key={name}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${data['Total Revenue']?.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {topSalespeople.labels && topSalespeople.values && (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={topSalespeople.labels.slice(0, 10).map((label: string, index: number) => ({
                    name: label,
                    value: topSalespeople.values[index]
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
                    <YAxis tickFormatter={(value) => `$${value.toLocaleString()}`} />
                    <Tooltip formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']} />
                    <Bar dataKey="value" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No salesperson data available
            </div>
          )}
        </div>

        {/* Top Products */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-4">Top Products</h4>
          {topProducts?.chart_data ? (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Product Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Total Revenue
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {Object.entries(topProducts.chart_data).map(([name, revenue]: [string, any]) => (
                      <tr key={name}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${revenue?.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {topProducts.labels && topProducts.values && (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={topProducts.labels.slice(0, 10).map((label: string, index: number) => ({
                    name: label,
                    value: topProducts.values[index]
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
                    <YAxis tickFormatter={(value) => `$${value.toLocaleString()}`} />
                    <Tooltip formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']} />
                    <Bar dataKey="value" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No product data available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Product Analysis Tab Component
function ProductAnalysisTab({ currentDatasetId, filters }: TabProps) {
  const [productAnalysis, setProductAnalysis] = useState<any>(null);
  const [productTable, setProductTable] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [analysis, table] = await Promise.all([
          apiClient.getProductAnalysisByCategory(currentDatasetId, filters),
          apiClient.getProductPerformanceTable(currentDatasetId, filters)
        ]);

        console.log('Product Analysis Data:', analysis);
        console.log('Product Table Data:', table);
        
        setProductAnalysis(analysis);
        setProductTable(table);
      } catch (error) {
        console.error('Error loading product analysis data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [currentDatasetId, filters]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h3 className="text-lg font-semibold text-gray-900">📦 Product Analysis</h3>
      
      {/* Product Analysis by Category */}
      {productAnalysis && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Sales by Category */}
          {productAnalysis.sales_by_category && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-4">Sales by Category</h4>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={Object.entries(productAnalysis.sales_by_category).map(([category, value]: [string, any]) => ({
                      name: category,
                      value: extractNumericValue(value)
                    }))}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {Object.keys(productAnalysis.sales_by_category).map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Units by Category */}
          {productAnalysis.units_by_category && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-4">Units by Category</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={Object.entries(productAnalysis.units_by_category).map(([category, units]: [string, any]) => ({
                  name: category,
                  value: extractNumericValue(units)
                }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(value: any) => [value, 'Units Sold']} />
                  <Bar dataKey="value" fill="#82ca9d" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Product Performance Table */}
      {productTable?.data && (
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-4">Detailed Product Performance</h4>
          <div className="overflow-x-auto bg-white rounded-lg shadow">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Product Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Revenue
                  </th>
                  {/* <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Units
                  </th> */}
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Avg Revenue per Order
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {Object.entries(productTable.data).map(([productName, data]: [string, any]) => (
                  <tr key={productName}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {productName}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      ${data['Total Revenue']?.toLocaleString()}
                    </td>
                    {/* <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {data['Total Units']?.toLocaleString()}
                    </td> */}
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      ${data['Avg Revenue per Order']?.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!productAnalysis && !productTable && (
        <div className="text-center py-12 text-gray-500">
          No product analysis data available
        </div>
      )}
    </div>
  );
}

// Customer Insights Tab Component
function CustomerInsightsTab({ currentDatasetId, filters }: TabProps) {
  const [customerInsights, setCustomerInsights] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const insights = await apiClient.getCustomerInsights(currentDatasetId, filters);
        setCustomerInsights(insights);
      } catch (error) {
        console.error('Error loading customer insights data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [currentDatasetId, filters]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h3 className="text-lg font-semibold text-gray-900">👥 Customer Insights</h3>
      
      {customerInsights ? (
        <div className="space-y-8">
          {/* New vs Returning Customers */}
          {customerInsights.new_vs_returning && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-4">New vs Returning Customers</h4>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={customerInsights.new_vs_returning.labels.map((label: string, index: number) => ({
                      name: label,
                      value: customerInsights.new_vs_returning.values[index]
                    }))}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {customerInsights.new_vs_returning.labels.map((_: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => [value, 'Customers']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* AOV by Customer Type */}
            {customerInsights.aov_by_type && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-4">AOV by Customer Type</h4>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={customerInsights.aov_by_type.labels.map((label: string, index: number) => ({
                    name: label,
                    value: customerInsights.aov_by_type.values[index]
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis tickFormatter={(value) => `$${value}`} />
                    <Tooltip formatter={(value: any) => [`$${value}`, 'AOV']} />
                    <Bar dataKey="value" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Order Frequency */}
            {customerInsights.order_frequency && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-4">Order Frequency Distribution</h4>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={customerInsights.order_frequency.labels.map((label: string, index: number) => ({
                    name: label,
                    value: customerInsights.order_frequency.values[index]
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value: any) => [value, 'Customers']} />
                    <Bar dataKey="value" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Top Customers */}
          {customerInsights.top_customers?.data && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-4">Top Customers by Revenue</h4>
              <div className="overflow-x-auto bg-white rounded-lg shadow">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Customer ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Total Revenue
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {Object.entries(customerInsights.top_customers.data).map(([customerId, data]: [string, any]) => (
                      <tr key={customerId}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {customerId}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${data.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {customerInsights.top_customers.data && (
            console.log("DATA:", customerInsights.top_customers.data)
          )}

        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
          No customer insights available
        </div>
      )}
    </div>
  );
}

// Regional Analysis Tab Component
function RegionalAnalysisTab({ currentDatasetId, filters }: TabProps) {
  const [regionalPerformance, setRegionalPerformance] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const performance = await apiClient.getRegionalPerformance(currentDatasetId, filters);
        setRegionalPerformance(performance);
      } catch (error) {
        console.error('Error loading regional performance data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [currentDatasetId, filters]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h3 className="text-lg font-semibold text-gray-900">🌍 Regional Analysis</h3>
      
      {regionalPerformance?.data ? (
        <div className="space-y-8">
          {/* Regional Performance Summary Table */}
          <div className="bg-gray-50 p-4 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-4">Regional Performance Summary</h4>
            <div className="overflow-x-auto bg-white rounded-lg shadow">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Region
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Total Revenue
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Total Orders
                    </th>
                    {/* <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Avg Order Value
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Total Units
                    </th> */}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {Object.entries(regionalPerformance.data).map(([region, data]: [string, any]) => (
                    <tr key={region}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {region}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${data['Total Revenue']?.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {data['Total Orders']?.toLocaleString()}
                      </td>
                      {/* <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${data['Avg Order Value']?.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {data['Total Units']?.toLocaleString()}
                      </td> */}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Regional Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Revenue by Region */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-4">Revenue by Region</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={Object.entries(regionalPerformance.data).map(([region, data]: [string, any]) => ({
                  name: region,
                  value: data['Total Revenue']
                }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis tickFormatter={(value) => `$${value.toLocaleString()}`} />
                  <Tooltip formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']} />
                  <Bar dataKey="value" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Orders by Region */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-4">Orders by Region</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={Object.entries(regionalPerformance.data).map(([region, data]: [string, any]) => ({
                  name: region,
                  value: data['Total Orders']
                }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(value: any) => [value, 'Orders']} />
                  <Bar dataKey="value" fill="#82ca9d" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
          No regional performance data available
        </div>
      )}
    </div>
  );
}

function RawDataTab({ currentDatasetId, filters, currentPage, pageSize, setCurrentPage, setPageSize }: RawDataTabProps) {
  const [rawData, setRawData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const offset = (currentPage - 1) * pageSize;
        const data = await apiClient.getRawData(currentDatasetId, pageSize, offset, filters);
        setRawData(data);
      } catch (error) {
        console.error('Error loading raw data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [currentDatasetId, filters, currentPage, pageSize]);

  const exportData = async () => {
    try {
      const blob = await apiClient.exportFilteredCSV(currentDatasetId, filters);
      if (blob) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'filtered_data.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Error exporting data:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">📋 Raw Data</h3>
        <button
          onClick={exportData}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
        >
          Export Filtered Data to CSV
        </button>
      </div>

      {/* Pagination Controls */}
      <div className="flex items-center space-x-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Rows per page</label>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={500}>500</option>
            <option value={1000}>1000</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Page</label>
          <input
            type="number"
            min={1}
            value={currentPage}
            onChange={(e) => setCurrentPage(Math.max(1, Number(e.target.value)))}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 w-20"
          />
        </div>
      </div>

      {rawData && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
          <p className="text-blue-800">
            Showing {rawData.returned_records} of {rawData.total_records} total records
          </p>
        </div>
      )}

      {/* Data Table */}
      {rawData?.data && rawData.data.length > 0 ? (
        <div className="overflow-x-auto bg-white rounded-lg shadow">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {Object.keys(rawData.data[0]).map((key) => (
                  <th key={key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {rawData.data.map((row: any, index: number) => (
                <tr key={index}>
                  {Object.values(row).map((value: any, cellIndex: number) => (
                    <td key={cellIndex} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {value?.toString() || ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
          No data available for the selected filters
        </div>
      )}
    </div>
  );
}

interface TabData {
  id: string;
  name: string;
  icon: React.ComponentType<any>;
}

const tabs: TabData[] = [
  { id: 'overview', name: 'Sales Overview', icon: BarChart3 },
  { id: 'performers', name: 'Top Performers', icon: TrendingUp },
  { id: 'products', name: 'Product Analysis', icon: BarChart3 },
  { id: 'customers', name: 'Customer Insights', icon: Users },
  { id: 'regional', name: 'Regional Analysis', icon: Map },
  { id: 'raw', name: 'Raw Data', icon: FileText },
];

export default function ContinuumDashboard() {
  // Core state
  const [isApiHealthy, setIsApiHealthy] = useState<boolean | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [currentDatasetId, setCurrentDatasetId] = useState<number | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [filteredAnalysis, setFilteredAnalysis] = useState<AnalysisResult | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ regions: [], reps: [], categories: [] });
  
  // UI state
  const [activeTab, setActiveTab] = useState('overview');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filter state
  const [filters, setFilters] = useState<FilterParams>({});
  const [dateRange, setDateRange] = useState<{ from: string; to: string } | null>(null);
  const [selectedRegions, setSelectedRegions] = useState<string[]>([]);
  const [selectedReps, setSelectedReps] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  
  // Pagination state for raw data
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);

  // Health check on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const healthy = await apiClient.healthCheck();
        setIsApiHealthy(healthy);
        if (healthy) {
          loadDatasets();
        }
      } catch (err) {
        setIsApiHealthy(false);
        setError('Failed to connect to backend API');
      }
    };
    checkHealth();
  }, []);

  // Load datasets
  const loadDatasets = async () => {
    try {
      const datasets = await apiClient.getDatasets();
      setDatasets(datasets);
    } catch (err) {
      setError('Failed to load datasets');
    }
  };

  // Load dataset analysis
  const loadAnalysis = async (datasetId: number) => {
    setIsLoading(true);
    try {
      const analysis = await apiClient.analyzeDataset(datasetId);
      const filterOpts = await apiClient.getFilterOptions(datasetId);
      
      setAnalysisResult(analysis);
      setFilteredAnalysis(analysis);
      setFilterOptions(filterOpts);
      setError(null);
    } catch (err) {
      setError('Failed to analyze dataset');
    } finally {
      setIsLoading(false);
    }
  };

  // Apply filters
  const applyFilters = useCallback(async () => {
    if (!currentDatasetId) return;
    
    setIsLoading(true);
    try {
      const filterParams: FilterParams = {
        ...(dateRange && { date_from: dateRange.from, date_to: dateRange.to }),
        ...(selectedRegions.length > 0 && { regions: selectedRegions }),
        ...(selectedReps.length > 0 && { reps: selectedReps }),
        ...(selectedCategories.length > 0 && { categories: selectedCategories }),
      };

      const filtered = await apiClient.analyzeDatasetFiltered(currentDatasetId, filterParams);
      setFilteredAnalysis(filtered);
      setFilters(filterParams);
    } catch (err) {
      setError('Failed to apply filters');
    } finally {
      setIsLoading(false);
    }
  }, [currentDatasetId, dateRange, selectedRegions, selectedReps, selectedCategories]);

  // Reset filters
  const resetFilters = () => {
    setDateRange(null);
    setSelectedRegions([]);
    setSelectedReps([]);
    setSelectedCategories([]);
    setFilteredAnalysis(analysisResult);
    setFilters({});
  };

  // Upload CSV file
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    try {
      const datasetId = await apiClient.uploadCSV(file);
      if (datasetId) {
        setCurrentDatasetId(datasetId);
        await loadDatasets();
        await loadAnalysis(datasetId);
      }
    } catch (err) {
      setError('Failed to upload file');
    } finally {
      setIsLoading(false);
    }
  };

  // Load demo data
  const loadDemoData = async () => {
    setIsLoading(true);
    try {
      const demoCSV = `order_date,customer_id,product_name,category,units,revenue,aov,region,salesperson,channel
2024-01-15,C001,Product A,Electronics,5,2500,500,North,John Doe,Online
2024-01-16,C002,Product B,Clothing,3,450,150,South,Jane Smith,Retail
2024-01-17,C003,Product C,Electronics,2,1200,600,East,Bob Johnson,Online
2024-01-18,C004,Product D,Home,4,800,200,West,Alice Brown,Online
2024-01-19,C005,Product E,Clothing,1,100,100,North,John Doe,Retail`;

      const datasetId = await apiClient.uploadDemoCSV(demoCSV);
      if (datasetId) {
        setCurrentDatasetId(datasetId);
        await loadDatasets();
        await loadAnalysis(datasetId);
      }
    } catch (err) {
      setError('Failed to load demo data');
    } finally {
      setIsLoading(false);
    }
  };

  // Delete dataset
  const deleteDataset = async (datasetId: number) => {
    try {
      await apiClient.deleteDataset(datasetId);
      await loadDatasets();
      if (currentDatasetId === datasetId) {
        setCurrentDatasetId(null);
        setAnalysisResult(null);
        setFilteredAnalysis(null);
      }
    } catch (err) {
      setError('Failed to delete dataset');
    }
  };

  // Load dataset
  const loadDataset = async (datasetId: number) => {
    setCurrentDatasetId(datasetId);
    await loadAnalysis(datasetId);
  };

  if (isApiHealthy === false) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center p-8">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Backend API Unavailable</h1>
          <p className="text-gray-600">Please ensure the backend server is running.</p>
        </div>
      </div>
    );
  }

  if (isApiHealthy === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p>Connecting to backend...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-end mb-4">
           <LogoutButton />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">ContinuumAI Sales Dashboard</h1>
          <p className="text-gray-600 mt-2">API-Powered Analytics Platform</p>
          
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4">
            <div className="flex">
              <AlertCircle className="h-5 w-5 text-red-400" />
              <div className="ml-3">
                <p className="text-sm text-red-800">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="ml-auto text-red-400 hover:text-red-600"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Data Management Section */}
        <div className="bg-white shadow rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Data Management</h2>
          
          {/* Existing Datasets */}
          {datasets.length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Existing Datasets</h3>
              <div className="space-y-2">
                {datasets.map((dataset) => (
                  <div key={dataset.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-md">
                    <div>
                      <span className="font-medium">📊 {dataset.name}</span>
                      <span className="text-gray-500 ml-2">({dataset.total_records} records)</span>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => loadDataset(dataset.id)}
                        className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                        disabled={isLoading}
                      >
                        Load
                      </button>
                      <button
                        onClick={() => deleteDataset(dataset.id)}
                        className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload Section */}
          <div className="flex items-center space-x-4">
            <div className="flex-1">
              <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-2">
                Upload New CSV File
              </label>
              <input
                id="file-upload"
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                disabled={isLoading}
              />
            </div>
            <button
              onClick={loadDemoData}
              className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50"
              disabled={isLoading}
            >
              Use Demo Data
            </button>
          </div>
        </div>

        {/* Main Content */}
        {!currentDatasetId ? (
          <div className="text-center py-12">
            <Upload className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Dataset Selected</h3>
            <p className="text-gray-600">Please upload a CSV file or use demo data to begin analysis.</p>
          </div>
        ) : isLoading && !analysisResult ? (
          <div className="text-center py-12">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
            <p>Analyzing dataset...</p>
          </div>
        ) : (
          <>
            {/* Dataset Info */}
            <div className="bg-green-50 border border-green-200 rounded-md p-4 mb-6">
              <p className="text-green-800">
                📊 Currently analyzing: Dataset {currentDatasetId} ({analysisResult?.total_records || 0} records)
              </p>
            </div>

            {/* Filters Section */}
            <div className="bg-white shadow rounded-lg p-6 mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">🎛️ Filters</h2>
                <button
                  onClick={resetFilters}
                  className="px-4 py-2 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
                >
                  Reset All Filters
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Date Range */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Order Date Range
                  </label>
                  <div className="flex space-x-2">
                    <input
                      type="date"
                      value={dateRange?.from || ''}
                      onChange={(e) => setDateRange(prev => ({ ...prev, from: e.target.value, to: prev?.to || '' }))}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                      type="date"
                      value={dateRange?.to || ''}
                      onChange={(e) => setDateRange(prev => ({ ...prev, from: prev?.from || '', to: e.target.value }))}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                {/* Regions */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Region
                  </label>
                  <select
                    multiple
                    value={selectedRegions}
                    onChange={(e) => setSelectedRegions(Array.from(e.target.selectedOptions, option => option.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    size={Math.min(filterOptions.regions.length + 1, 4)}
                  >
                    <option value="">All Regions</option>
                    {filterOptions.regions.map(region => (
                      <option key={region} value={region}>{region}</option>
                    ))}
                  </select>
                </div>

                {/* Salespeople */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Salesperson
                  </label>
                  <select
                    multiple
                    value={selectedReps}
                    onChange={(e) => setSelectedReps(Array.from(e.target.selectedOptions, option => option.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    size={Math.min(filterOptions.reps.length + 1, 4)}
                  >
                    <option value="">All Salespeople</option>
                    {filterOptions.reps.map(rep => (
                      <option key={rep} value={rep}>{rep}</option>
                    ))}
                  </select>
                </div>

                {/* Categories */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Categories
                  </label>
                  <select
                    multiple
                    value={selectedCategories}
                    onChange={(e) => setSelectedCategories(Array.from(e.target.selectedOptions, option => option.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    size={Math.min(filterOptions.categories.length + 1, 4)}
                  >
                    <option value="">All Categories</option>
                    {filterOptions.categories.map(category => (
                      <option key={category} value={category}>{category}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-4">
                <button
                  onClick={applyFilters}
                  className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  disabled={isLoading}
                >
                  {isLoading ? 'Applying...' : 'Apply Filters'}
                </button>
              </div>
            </div>

            {/* KPIs Section */}
            <div className="bg-white shadow rounded-lg p-6 mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-6">Quick Insights</h2>
              
              {filteredAnalysis?.kpis && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <h3 className="text-sm font-medium text-blue-600 mb-1">Total Revenue</h3>
                      <p className="text-2xl font-bold text-blue-900">
                        ${filteredAnalysis.kpis.total_revenue?.toLocaleString() || '0'}
                      </p>
                    </div>
                    
                    <div className="bg-green-50 p-4 rounded-lg">
                      <h3 className="text-sm font-medium text-green-600 mb-1">Total Orders</h3>
                      <p className="text-2xl font-bold text-green-900">
                        {filteredAnalysis.kpis.total_orders?.toLocaleString() || '0'}
                      </p>
                    </div>
                    
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <h3 className="text-sm font-medium text-purple-600 mb-1">Average Order Value</h3>
                      <p className="text-2xl font-bold text-purple-900">
                        ${filteredAnalysis.kpis.avg_aov?.toLocaleString() || '0'}
                      </p>
                    </div>
                    
                    <div className="bg-orange-50 p-4 rounded-lg">
                      <h3 className="text-sm font-medium text-orange-600 mb-1">Conversion Rate</h3>
                      <p className="text-2xl font-bold text-orange-900">
                        {filteredAnalysis.kpis.conversion_rate 
                          ? `${(filteredAnalysis.kpis.conversion_rate * 100).toFixed(1)}%` 
                          : 'N/A'}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-teal-50 p-4 rounded-lg">
                      <h3 className="text-sm font-medium text-teal-600 mb-1">New Customers</h3>
                      <p className="text-2xl font-bold text-teal-900">
                        {filteredAnalysis.kpis.new_count?.toLocaleString() || '0'}
                      </p>
                    </div>
                    
                    <div className="bg-indigo-50 p-4 rounded-lg">
                      <h3 className="text-sm font-medium text-indigo-600 mb-1">Returning Customers</h3>
                      <p className="text-2xl font-bold text-indigo-900">
                        {filteredAnalysis.kpis.returning_count?.toLocaleString() || '0'}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Tabbed Interface */}
            <div className="bg-white shadow rounded-lg">
              {/* Tab Navigation */}
              <div className="border-b border-gray-200">
                <nav className="-mb-px flex space-x-8 px-6">
                  {tabs.map((tab) => {
                    const Icon = tab.icon;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm ${
                          activeTab === tab.id
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                      >
                        <Icon className="h-5 w-5" />
                        <span>{tab.name}</span>
                      </button>
                    );
                  })}
                </nav>
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {activeTab === 'overview' && <SalesOverviewTab currentDatasetId={currentDatasetId!} filters={filters} />}
                {activeTab === 'performers' && <TopPerformersTab currentDatasetId={currentDatasetId!} filters={filters} />}
                {activeTab === 'products' && <ProductAnalysisTab currentDatasetId={currentDatasetId!} filters={filters} />}
                {activeTab === 'customers' && <CustomerInsightsTab currentDatasetId={currentDatasetId!} filters={filters} />}
                {activeTab === 'regional' && <RegionalAnalysisTab currentDatasetId={currentDatasetId!} filters={filters} />}
                {activeTab === 'raw' && (
                  <RawDataTab 
                    currentDatasetId={currentDatasetId!} 
                    filters={filters}
                    currentPage={currentPage}
                    pageSize={pageSize}
                    setCurrentPage={setCurrentPage}
                    setPageSize={setPageSize}
                  />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
