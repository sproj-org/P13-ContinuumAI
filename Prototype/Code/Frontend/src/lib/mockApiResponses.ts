// Mock API responses for testing Plotly rendering before backend integration

export interface PlotlyData {
  type: string;
  [key: string]: any;
}

export interface PlotlyLayout {
  title?: string | { text: string; [key: string]: any };
  [key: string]: any;
}

export interface PlotlyChart {
  data: PlotlyData[];
  layout: PlotlyLayout;
}

export interface ApiSuccessResponse {
  status: 'success';
  text?: string; // Optional text explanation/summary
  results: PlotlyChart[];
}

export interface ApiErrorResponse {
  status: 'error';
  message: string;
}

export type ApiResponse = ApiSuccessResponse | ApiErrorResponse;

// Mock responses for different query types
export const mockResponses: Record<string, ApiResponse> = {
  // UC-001: Revenue Drivers Analysis (Chart Response)
  'revenue': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'indicator',
          value: 1250000,
          mode: 'number+delta',
          delta: { reference: 1000000, relative: true },
          number: { prefix: '$', valueformat: ',.0f' },
          title: { text: 'Total Revenue', font: { size: 18, color: '#ffffff' } }
        }],
        layout: {
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#ffffff' },
          height: 200,
          margin: { t: 40, b: 20, l: 20, r: 20 }
        }
      }
    ]
  },

  // UC-002: Quota Tracking (Chart Response)
  'quota': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'bar',
          x: ['John Doe', 'Jane Smith', 'Mike Johnson', 'Sarah Williams'],
          y: [85000, 92000, 78000, 95000],
          marker: {
            color: ['#00d4ff', '#00d4ff', '#ff6b6b', '#00d4ff']
          },
          text: ['85%', '92%', '78%', '95%'],
          textposition: 'outside',
          name: 'Actual Sales'
        }, {
          type: 'scatter',
          x: ['John Doe', 'Jane Smith', 'Mike Johnson', 'Sarah Williams'],
          y: [100000, 100000, 100000, 100000],
          mode: 'lines',
          line: { color: '#ffd700', dash: 'dash', width: 2 },
          name: 'Quota Target'
        }],
        layout: {
          title: { text: 'Sales Rep Quota Performance', font: { size: 18 } },
          xaxis: { title: 'Sales Rep', gridcolor: 'rgba(255,255,255,0.1)' },
          yaxis: { title: 'Revenue ($)', gridcolor: 'rgba(255,255,255,0.1)' },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(20,20,20,0.5)',
          font: { color: '#ffffff' },
          showlegend: true,
          legend: { x: 0, y: 1 },
          height: 450
        }
      }
    ]
  },

  // UC-003: Rep Benchmarking (Multiple Charts)
  'benchmark': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'scatter',
          x: ['Q1', 'Q2', 'Q3', 'Q4'],
          y: [75000, 82000, 88000, 95000],
          mode: 'lines+markers',
          name: 'Top Performer',
          line: { color: '#00d4ff', width: 3 },
          marker: { size: 8 }
        }, {
          type: 'scatter',
          x: ['Q1', 'Q2', 'Q3', 'Q4'],
          y: [65000, 68000, 72000, 75000],
          mode: 'lines+markers',
          name: 'Average',
          line: { color: '#ffd700', width: 2 },
          marker: { size: 6 }
        }],
        layout: {
          title: 'Performance Trend Comparison',
          xaxis: { title: 'Quarter' },
          yaxis: { title: 'Revenue ($)' },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(20,20,20,0.5)',
          font: { color: '#ffffff' },
          showlegend: true
        }
      },
      {
        data: [{
          type: 'pie',
          labels: ['Enterprise', 'Mid-Market', 'SMB'],
          values: [45, 35, 20],
          marker: {
            colors: ['#00d4ff', '#00a8cc', '#007799']
          },
          hole: 0.4
        }],
        layout: {
          title: 'Deal Distribution by Segment',
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#ffffff' },
          showlegend: true
        }
      }
    ]
  },

  // UC-005: Graph Visualizations (Complex Chart)
  'trend': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'scatter',
          x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
          y: [120000, 135000, 128000, 145000, 158000, 172000],
          mode: 'lines+markers',
          name: 'Revenue',
          line: { color: '#00d4ff', width: 3 },
          marker: { size: 10, color: '#00d4ff' },
          fill: 'tozeroy',
          fillcolor: 'rgba(0, 212, 255, 0.1)'
        }],
        layout: {
          title: 'Monthly Revenue Trend',
          xaxis: { 
            title: 'Month',
            gridcolor: 'rgba(255,255,255,0.1)'
          },
          yaxis: { 
            title: 'Revenue ($)',
            gridcolor: 'rgba(255,255,255,0.1)'
          },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(20,20,20,0.5)',
          font: { color: '#ffffff' }
        }
      }
    ]
  },

  // AOV Over Time (Spline Chart with Real Data)
  'aov': {
    status: 'success',
    results: [
      {
        data: [{
          line: { shape: "spline", smoothing: 0.3 },
          mode: "lines+markers",
          name: "AOV",
          x: ["2023-04-30", "2023-10-31", "2024-01-31", "2024-03-31", "2024-04-30", "2024-05-31", "2024-06-30", "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30", "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31", "2025-08-31", "2025-09-30", "2025-10-31"],
          y: [13576.92, 5221.85, 182.94, 733.0, 33370.4, 3961.62, 307.29, 5429.55, 1214.47, 6616.98, 10867.45, 4553.96, 8032.79, 2542.90, 7878.31, 8737.09, 7014.05, 8226.17, 8308.66, 5804.90, 5365.24, 4905.45, 6728.91],
          type: "scatter"
        }],
        layout: {
          xaxis: { 
            title: { text: "Date" }, 
            tickformat: "%b %Y", 
            dtick: "M1" 
          },
          title: { text: "AOV Over Time" },
          yaxis: { title: { text: "AOV" } },
          height: 420
        }
      }
    ]
  },

  // Average AOV Indicator
  'average': {
    status: 'success',
    results: [
      {
        data: [{
          mode: "number",
          number: { prefix: "$", valueformat: ",.2f" },
          title: { text: "Avg AOV" },
          value: 6363.76,
          type: "indicator"
        }],
        layout: {
          margin: { t: 8, b: 8, l: 8, r: 8 },
          height: 120
        }
      }
    ]
  },

  // Multiple Charts - AOV Analysis (Indicator + Line Chart)
  'aov analysis': {
    status: 'success',
    results: [
      {
        data: [{
          mode: "number",
          number: { prefix: "$", valueformat: ",.2f" },
          title: { text: "Avg AOV" },
          value: 6363.76,
          type: "indicator"
        }],
        layout: {
          margin: { t: 8, b: 8, l: 8, r: 8 },
          height: 120
        }
      },
      {
        data: [{
          line: { shape: "spline", smoothing: 0.3 },
          mode: "lines+markers",
          name: "AOV",
          x: ["2023-04-30", "2023-10-31", "2024-01-31", "2024-03-31", "2024-04-30", "2024-05-31", "2024-06-30", "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30", "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31", "2025-08-31", "2025-09-30", "2025-10-31"],
          y: [13576.92, 5221.85, 182.94, 733.0, 33370.4, 3961.62, 307.29, 5429.55, 1214.47, 6616.98, 10867.45, 4553.96, 8032.79, 2542.90, 7878.31, 8737.09, 7014.05, 8226.17, 8308.66, 5804.90, 5365.24, 4905.45, 6728.91],
          type: "scatter",
          marker: { color: '#00d4ff', size: 8 }
        }],
        layout: {
          xaxis: { 
            title: { text: "Date" }, 
            tickformat: "%b %Y", 
            dtick: "M1" 
          },
          title: { text: "AOV Over Time" },
          yaxis: { title: { text: "AOV ($)" } },
          height: 420
        }
      }
    ]
  },

  // Sales by Region (Pie Chart)
  'region': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'pie',
          labels: ['North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East'],
          values: [42, 28, 18, 8, 4],
          marker: {
            colors: ['#00d4ff', '#00a8cc', '#007799', '#005566', '#003344']
          },
          hole: 0.4,
          textinfo: 'label+percent',
          textposition: 'outside'
        }],
        layout: {
          title: 'Sales Distribution by Region',
          height: 450,
          showlegend: true,
          legend: { orientation: 'h', y: -0.1 }
        }
      }
    ]
  },

  // Product Performance (Horizontal Bar Chart)
  'product': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'bar',
          orientation: 'h',
          y: ['Product A', 'Product B', 'Product C', 'Product D', 'Product E'],
          x: [450000, 380000, 320000, 280000, 195000],
          marker: {
            color: ['#00d4ff', '#00d4ff', '#00d4ff', '#ffd700', '#ff6b6b'],
            line: { color: 'rgba(255,255,255,0.2)', width: 1 }
          },
          text: ['$450K', '$380K', '$320K', '$280K', '$195K'],
          textposition: 'outside'
        }],
        layout: {
          title: 'Product Performance (YTD Revenue)',
          xaxis: { title: 'Revenue ($)' },
          yaxis: { title: '' },
          height: 400
        }
      }
    ]
  },

  // Conversion Funnel (Funnel Chart)
  'funnel': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'funnel',
          y: ['Leads', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won'],
          x: [10000, 5500, 3200, 1800, 950],
          textinfo: 'value+percent initial',
          marker: {
            color: ['#00d4ff', '#00c4ef', '#00b4df', '#00a4cf', '#0094bf']
          }
        }],
        layout: {
          title: 'Sales Conversion Funnel',
          height: 450,
          margin: { l: 150 }
        }
      }
    ]
  },

  // Monthly Sales Comparison (Grouped Bar Chart)
  'monthly': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'bar',
          name: '2024',
          x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
          y: [120000, 135000, 128000, 145000, 158000, 172000],
          marker: { color: '#00d4ff' }
        }, {
          type: 'bar',
          name: '2025',
          x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
          y: [145000, 152000, 168000, 175000, 188000, 195000],
          marker: { color: '#ffd700' }
        }],
        layout: {
          title: 'Monthly Sales Comparison (2024 vs 2025)',
          xaxis: { title: 'Month' },
          yaxis: { title: 'Revenue ($)' },
          barmode: 'group',
          height: 420
        }
      }
    ]
  },

  // Win Rate by Deal Size (Scatter Plot)
  'winrate': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'scatter',
          mode: 'markers',
          x: [5000, 15000, 25000, 45000, 75000, 120000, 200000, 350000],
          y: [85, 78, 72, 65, 58, 45, 38, 25],
          marker: {
            size: [10, 15, 20, 25, 30, 35, 40, 45],
            color: [85, 78, 72, 65, 58, 45, 38, 25],
            colorscale: 'Viridis',
            showscale: true,
            colorbar: { title: 'Win Rate %' }
          },
          text: ['$5K', '$15K', '$25K', '$45K', '$75K', '$120K', '$200K', '$350K'],
          textposition: 'top center'
        }],
        layout: {
          title: 'Win Rate by Deal Size',
          xaxis: { title: 'Deal Size ($)', type: 'log' },
          yaxis: { title: 'Win Rate (%)' },
          height: 450
        }
      }
    ]
  },

  // Comprehensive multi-chart example
  'full analysis': {
    status: 'success',
    results: [
      {
        data: [{
          type: 'scatter',
          x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
          y: [120000, 135000, 128000, 145000, 158000, 172000],
          mode: 'lines+markers',
          name: 'Revenue',
          line: { color: '#00d4ff', width: 3 },
          marker: { size: 10, color: '#00d4ff' },
          fill: 'tozeroy',
          fillcolor: 'rgba(0, 212, 255, 0.1)'
        }],
        layout: {
          title: { text: 'Monthly Revenue Trend', font: { size: 18 } },
          xaxis: { 
            title: 'Month',
            gridcolor: 'rgba(255,255,255,0.1)'
          },
          yaxis: { 
            title: 'Revenue ($)',
            gridcolor: 'rgba(255,255,255,0.1)'
          },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(20,20,20,0.5)',
          font: { color: '#ffffff' },
          height: 400
        }
      },
      {
        data: [{
          type: 'pie',
          labels: ['North America', 'Europe', 'Asia Pacific', 'Latin America'],
          values: [42, 28, 22, 8],
          marker: {
            colors: ['#00d4ff', '#00a8cc', '#007799', '#005566']
          },
          hole: 0.4,
          textinfo: 'label+percent',
          textposition: 'outside'
        }],
        layout: {
          title: { text: 'Sales by Region', font: { size: 18 } },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#ffffff' },
          height: 400,
          showlegend: true,
          legend: { orientation: 'h', y: -0.15 }
        }
      },
      {
        data: [{
          type: 'bar',
          orientation: 'h',
          y: ['Product A', 'Product B', 'Product C', 'Product D'],
          x: [450000, 380000, 320000, 280000],
          marker: {
            color: ['#00d4ff', '#00c4ef', '#00b4df', '#00a4cf']
          },
          text: ['$450K', '$380K', '$320K', '$280K'],
          textposition: 'outside'
        }],
        layout: {
          title: { text: 'Top Products by Revenue', font: { size: 18 } },
          xaxis: { title: 'Revenue ($)', gridcolor: 'rgba(255,255,255,0.1)' },
          yaxis: { gridcolor: 'rgba(255,255,255,0.1)' },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(20,20,20,0.5)',
          font: { color: '#ffffff' },
          height: 350
        }
      },
      {
        data: [{
          type: 'funnel',
          y: ['Leads', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won'],
          x: [10000, 5500, 3200, 1800, 950],
          textinfo: 'value+percent initial',
          marker: {
            color: ['#00d4ff', '#00c4ef', '#00b4df', '#00a4cf', '#0094bf']
          }
        }],
        layout: {
          title: { text: 'Conversion Funnel', font: { size: 18 } },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#ffffff' },
          height: 450,
          margin: { l: 150 }
        }
      }
    ]
  },

  // Error response example
  'error': {
    status: 'error',
    message: "I'm sorry, I couldn't find that data. Please try rephrasing your question."
  }
};

// Helper function to simulate API call with delay
export async function mockApiCall(query: string): Promise<ApiResponse> {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Simple keyword matching to return appropriate mock response
  const lowerQuery = query.toLowerCase();
  
  if (lowerQuery.includes('full analysis') || lowerQuery.includes('comprehensive') || lowerQuery.includes('dashboard')) {
    return mockResponses['full analysis'];
  } else if (lowerQuery.includes('aov analysis')) {
    return mockResponses['aov analysis'];
  } else if (lowerQuery.includes('aov')) {
    return mockResponses.aov;
  } else if (lowerQuery.includes('average')) {
    return mockResponses.average;
  } else if (lowerQuery.includes('region')) {
    return mockResponses.region;
  } else if (lowerQuery.includes('product')) {
    return mockResponses.product;
  } else if (lowerQuery.includes('funnel') || lowerQuery.includes('conversion')) {
    return mockResponses.funnel;
  } else if (lowerQuery.includes('monthly') || lowerQuery.includes('comparison')) {
    return mockResponses.monthly;
  } else if (lowerQuery.includes('win rate') || lowerQuery.includes('winrate')) {
    return mockResponses.winrate;
  } else if (lowerQuery.includes('revenue') || lowerQuery.includes('sales')) {
    return mockResponses.revenue;
  } else if (lowerQuery.includes('quota') || lowerQuery.includes('target')) {
    return mockResponses.quota;
  } else if (lowerQuery.includes('benchmark') || lowerQuery.includes('compare')) {
    return mockResponses.benchmark;
  } else if (lowerQuery.includes('trend') || lowerQuery.includes('graph')) {
    return mockResponses.trend;
  } else {
    return mockResponses.error;
  }
}
