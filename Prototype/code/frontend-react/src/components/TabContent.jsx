import { useState } from 'react'
import SalesOverview from './tabs/SalesOverview'
import TopPerformers from './tabs/TopPerformers'
import ProductAnalysis from './tabs/ProductAnalysis'
import CustomerInsights from './tabs/CustomerInsights'
import './TabContent.css'

function TabContent({ filteredData }) {
  const [activeTab, setActiveTab] = useState('sales')

  const tabs = [
    { id: 'sales', label: 'Sales Overview' },
    { id: 'performers', label: 'Top Performers' },
    { id: 'products', label: 'Product Analysis' },
    { id: 'customers', label: 'Customer Insights' }
  ]

  return (
    <div className="tab-container">
      <div className="tab-header">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'sales' && <SalesOverview data={filteredData} />}
        {activeTab === 'performers' && <TopPerformers data={filteredData} />}
        {activeTab === 'products' && <ProductAnalysis data={filteredData} />}
        {activeTab === 'customers' && <CustomerInsights data={filteredData} />}
      </div>
    </div>
  )
}

export default TabContent
