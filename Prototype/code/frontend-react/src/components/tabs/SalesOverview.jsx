import { BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './TabStyles.css'

function SalesOverview({ data }) {
  if (!data) return <div>Loading...</div>

  // Beautiful gradient colors for charts
  const COLORS = ['#a78bfa', '#7dd3fc', '#f0abfc', '#fb923c', '#34d399', '#fbbf24']

  return (
    <div className="tab-section">
      <h3 className="tab-title">Sales Overview</h3>
      
      <div className="charts-grid">
        <div className="chart-container">
          <h4>Sales by Region</h4>
          {data.sales_by_region && data.sales_by_region.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.sales_by_region}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="region" stroke="#b3b1c8" />
                <YAxis stroke="#b3b1c8" />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Bar dataKey="revenue" fill="#a78bfa" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Region or Revenue data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Sales over Time</h4>
          {data.sales_over_time && data.sales_over_time.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={data.sales_over_time}>
                <defs>
                  <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7dd3fc" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#7dd3fc" stopOpacity={0.1}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" stroke="#b3b1c8" />
                <YAxis stroke="#b3b1c8" />
                <Tooltip 
                  contentStyle={{ 
                    background: 'rgba(15, 10, 30, 0.9)', 
                    border: '1px solid rgba(167, 139, 250, 0.3)',
                    borderRadius: '8px'
                  }} 
                />
                <Area 
                  type="monotone" 
                  dataKey="revenue" 
                  stroke="#7dd3fc" 
                  strokeWidth={3}
                  fill="url(#colorRevenue)"
                  animationDuration={1500}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Order Date or Revenue data not available</div>
          )}
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-container">
          <h4>Sales by Channel</h4>
          {data.sales_by_channel && data.sales_by_channel.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={data.sales_by_channel}
                  dataKey="revenue"
                  nameKey="channel"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={({ channel, percent }) => `${channel}: ${(percent * 100).toFixed(0)}%`}
                  animationDuration={1500}
                  animationBegin={0}
                >
                  {data.sales_by_channel.map((entry, index) => (
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
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data">Channel data not available</div>
          )}
        </div>

        <div className="chart-container">
          <h4>Revenue Distribution</h4>
          {data.revenue_distribution && data.revenue_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.revenue_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="range" stroke="#b3b1c8" angle={-45} textAnchor="end" height={100} />
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
            <div className="no-data">No revenue data available</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SalesOverview
