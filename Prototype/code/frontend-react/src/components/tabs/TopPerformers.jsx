import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import './TabStyles.css'

function TopPerformers({ data }) {
  if (!data) return <div>Loading...</div>

  const COLORS = ['#a78bfa', '#7dd3fc', '#f0abfc', '#fb923c', '#34d399', '#fbbf24', '#f87171', '#a3e635']

  return (
    <div className="tab-section">
      <h3 className="tab-title">Top Performers</h3>
      
      <div className="charts-grid">
        <div className="chart-container">
          <h4>Top Salespeople by Revenue</h4>
          {data.top_salespeople && data.top_salespeople.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.top_salespeople} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis type="number" stroke="#b3b1c8" />
                <YAxis dataKey="salesperson" type="category" stroke="#b3b1c8" width={100} />
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
            <div className="no-data">Salesperson data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Top Products by Revenue</h4>
          {data.top_products && data.top_products.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.top_products} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis type="number" stroke="#b3b1c8" />
                <YAxis dataKey="product" type="category" stroke="#b3b1c8" width={100} />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Bar dataKey="revenue" fill="#7dd3fc" animationDuration={1500} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Product data not available</div>
          )}
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-container">
          <h4>Salesperson Leaderboard</h4>
          {data.salesperson_leaderboard && data.salesperson_leaderboard.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Salesperson</th>
                    <th>Total Revenue</th>
                    <th>Total Orders</th>
                  </tr>
                </thead>
                <tbody>
                  {data.salesperson_leaderboard.map((row, idx) => (
                    <tr key={idx}>
                      <td>{row.salesperson}</td>
                      <td>{row.total_revenue}</td>
                      <td>{row.total_orders}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="no-data">Leaderboard data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Regional Performance</h4>
          {data.regional_performance && data.regional_performance.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Region</th>
                    <th>Total Revenue</th>
                    <th>Total Orders</th>
                    <th>Unique Customers</th>
                  </tr>
                </thead>
                <tbody>
                  {data.regional_performance.map((row, idx) => (
                    <tr key={idx}>
                      <td>{row.region}</td>
                      <td>{row.total_revenue}</td>
                      <td>{row.total_orders}</td>
                      <td>{row.unique_customers}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="no-data">Regional data not available</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default TopPerformers
