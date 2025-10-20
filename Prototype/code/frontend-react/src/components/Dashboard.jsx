import { useState, useEffect, useMemo } from 'react'
import axios from 'axios'
import { format } from 'date-fns'
import Sidebar from './Sidebar'
import KPICards from './KPICards'
import TabContent from './TabContent'
import './Dashboard.css'

function Dashboard({ data, usingDemo, onClearDemo }) {
  const [filters, setFilters] = useState({
    dateFrom: data.min_date,
    dateTo: data.max_date,
    regions: [],
    salespeople: [],
    categories: []
  })
  
  const [filteredData, setFilteredData] = useState(null)
  const [kpis, setKpis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // Apply filters whenever they change OR on initial mount
  useEffect(() => {
    applyFilters()
  }, [filters])

  const applyFilters = async () => {
    setLoading(true)
    try {
      const response = await axios.post('http://localhost:5001/api/filter', {
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
        regions: filters.regions,
        salespeople: filters.salespeople,
        categories: filters.categories
      })
      setFilteredData(response.data.filtered_data)
      setKpis(response.data.kpis)
    } catch (err) {
      console.error('Filter error:', err)
      alert('Error applying filters: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const resetFilters = () => {
    setFilters({
      dateFrom: data.min_date,
      dateTo: data.max_date,
      regions: [],
      salespeople: [],
      categories: []
    })
  }

  const downloadFilteredData = async () => {
    try {
      const response = await axios.post('http://localhost:5001/api/download', {
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
        regions: filters.regions,
        salespeople: filters.salespeople,
        categories: filters.categories
      }, {
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'filtered_sales.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error('Download error:', err)
      alert('Error downloading file: ' + err.message)
    }
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <button 
          className={`sidebar-toggle ${sidebarCollapsed ? 'collapsed' : ''}`}
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          aria-label="Toggle Sidebar"
        >
          {sidebarCollapsed ? '☰' : '✕'}
        </button>
        <h1>Sales Dashboard</h1>
      </header>
      
      <Sidebar
        data={data}
        filters={filters}
        setFilters={setFilters}
        resetFilters={resetFilters}
        downloadFilteredData={downloadFilteredData}
        usingDemo={usingDemo}
        onClearDemo={onClearDemo}
        collapsed={sidebarCollapsed}
      />

      <main className={`dashboard-main ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        {loading && <div className="loading-overlay">Loading...</div>}
        
        {kpis && (
          <>
            <KPICards kpis={kpis} />
            <TabContent filteredData={filteredData} />
          </>
        )}
      </main>

      <footer className="dashboard-footer">
        ContinuumAI © 2025 — The Future of Business Intelligence
      </footer>
    </div>
  )
}

export default Dashboard