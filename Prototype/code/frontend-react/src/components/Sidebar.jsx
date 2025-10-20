import { useState } from 'react'
import './Sidebar.css'

function Sidebar({ 
  data, 
  filters, 
  setFilters, 
  resetFilters, 
  downloadFilteredData,
  usingDemo,
  onClearDemo,
  collapsed 
}) {
  const handleDateChange = (field, value) => {
    setFilters(prev => ({ ...prev, [field]: value }))
  }

  const handleMultiSelectChange = (field, value) => {
    setFilters(prev => {
      let newValues = [...prev[field]]
      
      if (value === 'All') {
        // Select all means empty array (no filter)
        newValues = []
      } else {
        // Toggle the selected value
        if (newValues.includes(value)) {
          newValues = newValues.filter(v => v !== value)
        } else {
          newValues.push(value)
        }
      }
      
      return { ...prev, [field]: newValues }
    })
  }

  const isSelected = (field, value) => {
    if (value === 'All') {
      return filters[field].length === 0
    }
    return filters[field].includes(value)
  }

  return (
    <div className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-section">
        <h3>Controls & Data</h3>
        
        {usingDemo ? (
          <div className="data-source-info demo">
            <span>Using Demo Data</span>
            <button onClick={onClearDemo} className="clear-btn">Clear Demo Data</button>
          </div>
        ) : (
          <div className="data-source-info uploaded">
            <span>Using Uploaded Data</span>
          </div>
        )}

        {data.min_date && data.max_date && (
          <div className="date-range-info">
            Data available: {data.min_date} to {data.max_date}
          </div>
        )}

        <button onClick={resetFilters} className="reset-btn">
          Reset All Filters
        </button>
      </div>

      <div className="sidebar-section">
        <label>Order Date Range</label>
        <div className="date-inputs">
          <input
            type="date"
            value={filters.dateFrom}
            min={data.min_date}
            max={data.max_date}
            onChange={(e) => handleDateChange('dateFrom', e.target.value)}
          />
          <input
            type="date"
            value={filters.dateTo}
            min={data.min_date}
            max={data.max_date}
            onChange={(e) => handleDateChange('dateTo', e.target.value)}
          />
        </div>
      </div>

      <div className="sidebar-section">
        <label>Region</label>
        <div className="checkbox-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={isSelected('regions', 'All')}
              onChange={() => handleMultiSelectChange('regions', 'All')}
            />
            <span>All</span>
          </label>
          {data.regions?.map(region => (
            <label key={region} className="checkbox-label">
              <input
                type="checkbox"
                checked={isSelected('regions', region)}
                onChange={() => handleMultiSelectChange('regions', region)}
              />
              <span>{region}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="sidebar-section">
        <label>Salesperson</label>
        <div className="checkbox-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={isSelected('salespeople', 'All')}
              onChange={() => handleMultiSelectChange('salespeople', 'All')}
            />
            <span>All</span>
          </label>
          {data.salespeople?.map(person => (
            <label key={person} className="checkbox-label">
              <input
                type="checkbox"
                checked={isSelected('salespeople', person)}
                onChange={() => handleMultiSelectChange('salespeople', person)}
              />
              <span>{person}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="sidebar-section">
        <label>Product Category</label>
        <div className="checkbox-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={isSelected('categories', 'All')}
              onChange={() => handleMultiSelectChange('categories', 'All')}
            />
            <span>All</span>
          </label>
          {data.categories?.map(category => (
            <label key={category} className="checkbox-label">
              <input
                type="checkbox"
                checked={isSelected('categories', category)}
                onChange={() => handleMultiSelectChange('categories', category)}
              />
              <span>{category}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="sidebar-section">
        <button onClick={downloadFilteredData} className="download-btn">
          Download Filtered Dataset (CSV)
        </button>
      </div>
    </div>
  )
}

export default Sidebar