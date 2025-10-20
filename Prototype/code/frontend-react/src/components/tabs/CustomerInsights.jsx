import { BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import './TabStyles.css'

function CustomerInsights({ data }) {
  if (!data) return <div>Loading...</div>

  const COLORS = ['#a78bfa', '#7dd3fc', '#f0abfc', '#fb923c', '#34d399', '#fbbf24']

  return (
    <div className="tab-section">
      <h3 className="tab-title">Customer Insights</h3>
      
      <div className="charts-grid">
        <div className="chart-container">
          <h4>New vs Returning Customers</h4>
          {data.customer_type && data.customer_type.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={data.customer_type}
                  dataKey="count"
                  nameKey="type"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={({ type, percent }) => `${type}: ${(percent * 100).toFixed(0)}%`}
                  animationDuration={1500}
                  animationBegin={0}
                >
                  {data.customer_type.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }}
                />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Customer type data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Average Order Value by Customer Type</h4>
          {data.aov_by_type && data.aov_by_type.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.aov_by_type}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="type" stroke="#b3b1c8" />
                <YAxis stroke="#b3b1c8" />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Bar dataKey="aov" fill="#7dd3fc" animationDuration={1500} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">AOV data not available</div>
          )}
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-container">
          <h4>Top Customers by Revenue</h4>
          {data.top_customers && data.top_customers.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.top_customers} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis type="number" stroke="#b3b1c8" />
                <YAxis dataKey="customer" type="category" stroke="#b3b1c8" width={100} />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Bar dataKey="revenue" fill="#a78bfa" animationDuration={1500} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Customer revenue data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Customer Order Frequency</h4>
          {data.order_frequency && data.order_frequency.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.order_frequency}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="orders" stroke="#b3b1c8" />
                <YAxis stroke="#b3b1c8" />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Bar dataKey="count" fill="#7dd3fc" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Order frequency data not available</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CustomerInsights