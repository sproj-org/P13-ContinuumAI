# ContinuumAI Sales Dashboard - React Frontend

This is the React.js version of the ContinuumAI Sales Dashboard, converted from the original Streamlit application. All functionality and UI elements have been preserved.

## Features

- **Data Upload**: Upload CSV files with sales data
- **Demo Data**: Try the dashboard with sample data
- **Interactive Filters**: Filter by date range, region, salesperson, and product category
- **KPI Cards**: Quick insights including revenue, orders, AOV, and conversion rate
- **Multiple Tabs**:
  - Sales Overview: Regional sales, time-based trends, channel analysis
  - Top Performers: Salespeople and products rankings
  - Product Analysis: Category performance and product tables
  - Customer Insights: New vs returning customers, order frequency
- **Download**: Export filtered data as CSV
- **Premium UI**: Aurora gradient background with smooth animations

## Installation & Setup

### Prerequisites
- Node.js (v18 or higher)
- Python 3.8+
- npm or yarn

### Backend Setup (Flask API)

1. Install Python dependencies:
```bash
cd /path/to/code
pip install -r api_requirements.txt
```

2. Start the Flask server:
```bash
python api_server.py
```

The API will run on `http://localhost:5000`

### Frontend Setup (React)

1. Navigate to the React directory:
```bash
cd frontend-react
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The React app will run on `http://localhost:3000`

## Usage

1. Make sure both the Flask API (port 5000) and React app (port 3000) are running
2. Open your browser to `http://localhost:3000`
3. Either upload a CSV file or click "Use Demo Data"
4. Use the sidebar filters to explore your data
5. Switch between tabs to view different analytics
6. Download filtered data using the download button

## CSV File Format

Your CSV file should include columns such as:
- `order_date`: Date of the order
- `revenue`: Revenue amount
- `units`: Number of units sold
- `region`: Sales region
- `salesperson`: Name of salesperson
- `category`: Product category
- `product_name`: Name of product
- `customer_id`: Unique customer identifier
- `order_id`: Unique order identifier
- `channel`: Sales channel
- `is_returning`: Whether customer is returning (0 or 1)

## Technology Stack

- **Frontend**: React 18, Vite, Recharts, Axios
- **Backend**: Flask, Flask-CORS, Pandas, NumPy
- **Styling**: Custom CSS with gradient animations

## Architecture

The application uses a client-server architecture:
- React frontend handles UI and user interactions
- Flask backend processes data and applies filters
- RESTful API endpoints for data operations
- In-memory data storage (suitable for prototypes)

## API Endpoints

- `GET /api/demo-data`: Load demo dataset
- `POST /api/upload`: Upload and process CSV file
- `POST /api/filter`: Apply filters and get chart data
- `POST /api/download`: Download filtered data as CSV

## Build for Production

```bash
cd frontend-react
npm run build
```

This creates an optimized production build in the `dist` folder.

## Notes

- The backend stores data in memory; for production, implement proper session management
- Ensure CORS is properly configured for your deployment environment
- The demo data file should be located at `../data/demo_sales.csv` relative to the API server
