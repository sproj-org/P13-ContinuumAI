import './KPICards.css'

function KPICards({ kpis }) {
  const formatCurrency = (value) => {
    return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const formatNumber = (value) => {
    return value.toLocaleString('en-US')
  }

  const formatPercentage = (value) => {
    if (isNaN(value)) return 'N/A'
    return `${(value * 100).toFixed(1)}%`
  }

  return (
    <div className="kpi-section">
      <h2>Quick Insights</h2>
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Total Revenue</div>
          <div className="kpi-value">{formatCurrency(kpis.total_revenue)}</div>
        </div>
        
        <div className="kpi-card">
          <div className="kpi-label">Total Orders</div>
          <div className="kpi-value">{formatNumber(kpis.total_orders)}</div>
        </div>
        
        <div className="kpi-card">
          <div className="kpi-label">Average Order Value (AOV)</div>
          <div className="kpi-value">{formatCurrency(kpis.avg_aov)}</div>
        </div>
        
        <div className="kpi-card">
          <div className="kpi-label">Conversion Rate</div>
          <div className="kpi-value">{formatPercentage(kpis.conversion_rate)}</div>
        </div>
      </div>

      <div className="kpi-grid-small">
        <div className="kpi-card-small">
          <div className="kpi-label">New customers (unique)</div>
          <div className="kpi-value">{formatNumber(kpis.new_count)}</div>
        </div>
        
        <div className="kpi-card-small">
          <div className="kpi-label">Returning customers (unique)</div>
          <div className="kpi-value">{formatNumber(kpis.returning_count)}</div>
        </div>
      </div>
    </div>
  )
}

export default KPICards
