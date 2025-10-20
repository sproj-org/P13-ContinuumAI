import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import './TabStyles.css'

function ProductAnalysis({ data }) {
  if (!data) return <div>Loading...</div>

  const COLORS = ['#a78bfa', '#7dd3fc', '#f0abfc', '#fb923c', '#34d399', '#fbbf24', '#f87171', '#a3e635', '#60a5fa']

  return (
    <div className="tab-section">
      <h3 className="tab-title">Product Analysis</h3>
      
      <div className="charts-grid">
        <div className="chart-container">
          <h4>Sales by Product Category</h4>
          {data.sales_by_category && data.sales_by_category.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={data.sales_by_category}
                  dataKey="revenue"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  label={({ category, percent }) => `${category}: ${(percent * 100).toFixed(0)}%`}
                  animationDuration={1500}
                  animationBegin={0}
                >
                  {data.sales_by_category.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }}
                  formatter={(value) => `$${value.toLocaleString()}`}
                />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Category data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Units Sold by Category</h4>
          {data.units_by_category && data.units_by_category.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.units_by_category}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="category" stroke="#b3b1c8" />
                <YAxis stroke="#b3b1c8" />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Bar dataKey="units" fill="#7dd3fc" animationDuration={1500} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Units data not available</div>
          )}
        </div>
      </div>

      <div className="full-width-section">
        <div className="chart-container">
          <h4>Product Performance Table</h4>
          {data.product_performance && data.product_performance.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product Name</th>
                    <th>Total Revenue</th>
                    <th>Units Sold</th>
                    <th>Number of Orders</th>
                    <th>Avg Revenue per Order</th>
                  </tr>
                </thead>
                <tbody>
                  {data.product_performance.map((row, idx) => (
                    <tr key={idx}>
                      <td>{row.product_name}</td>
                      <td>{row.total_revenue}</td>
                      <td>{row.units_sold}</td>
                      <td>{row.num_orders}</td>
                      <td>{row.avg_revenue_per_order}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="no-data">Product performance data not available</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ProductAnalysis
