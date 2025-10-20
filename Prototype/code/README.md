# ContinuumAI - Sales Analytics Dashboard

## Tech Stack

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **Recharts** - Chart library
- **Axios** - HTTP client
- **date-fns** - Date formatting

### Backend
- **Flask** - Web framework
- **Pandas** - Data manipulation
- **NumPy** - Numerical computing
- **Streamlit** - Caching system
- **Flask-CORS** - Cross-origin resource sharing

### Styling
- **Custom CSS** - Premium gradients and animations
- **Glassmorphism** - Modern UI design
- **Responsive Design** - Mobile-first approach

---

## Prerequisites

Before installation, ensure you have:

- **Python 3.8 or higher**
- **Node.js 16 or higher**
- **npm or yarn**
- **Git**

Check versions:
```bash
python3 --version
node --version
npm --version
```

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/P13-ContinuumAI.git
cd P13-ContinuumAI/Prototype/code
```

### 2. Backend Setup (Flask API)

#### Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

#### Install Python Dependencies
```bash
pip install -r requirements.txt
```

#### Start Flask Server
```bash
python3 api_server.py
```

You should see:
```
* Running on http://127.0.0.1:5001
* Debug mode: on
```

### 3. Frontend Setup (React)

#### Open New Terminal
```bash
cd frontend-react
```

#### Install Node Dependencies
```bash
npm install
```

#### Start Development Server
```bash
npm run dev
```

You should see:
```
➜  Local:   http://localhost:3000/
```

---

## 🎮 Usage

### Quick Start

1. **Open browser** → Navigate to `http://localhost:3000`
2. **Landing page appears** with two options:
   - **Upload CSV** - Use your own sales data
   - **Use Demo Data** - Test with pre-loaded dataset

---

## 📁 Project Structure

```
P13-ContinuumAI/
└── Prototype/
    └── code/
        ├── api_server.py                 # Flask API main file
        ├── requirements.txt              # Python dependencies
        ├── backend/
        │   ├── data_logic.py            # Data processing logic
        │   └── demo_sales.csv           # Demo dataset (800 rows)
        ├── frontend-react/
        │   ├── package.json             # Node dependencies
        │   ├── vite.config.js           # Vite configuration
        │   ├── index.html               # Entry HTML
        │   └── src/
        │       ├── App.jsx              # Main React component
        │       ├── App.css              # Landing page styles
        │       ├── index.css            # Global styles
        │       ├── main.jsx             # React entry point
        │       └── components/
        │           ├── Dashboard.jsx    # Dashboard container
        │           ├── Dashboard.css    # Dashboard styles
        │           ├── Sidebar.jsx      # Filter sidebar
        │           ├── Sidebar.css      # Sidebar styles
        │           ├── KPICards.jsx     # KPI display
        │           ├── KPICards.css     # KPI styles
        │           ├── TabContent.jsx   # Tab navigation
        │           └── tabs/
        │               ├── Overview.jsx
        │               ├── ProductInsights.jsx
        │               ├── RegionalPerformance.jsx
        │               ├── TimeAnalysis.jsx
        │               ├── CustomerInsights.jsx
        │               └── TabStyles.css
        └── README.md                    # This file
```

---

## 🔌 API Endpoints

### Base URL: `http://localhost:5001/api`

---

## Development

### Running in Development Mode

Both servers must be running simultaneously:

**Terminal 1 (Backend):**
```bash
cd "/path/to/P13-ContinuumAI/Prototype/code"
source venv/bin/activate
python3 api_server.py
```

**Terminal 2 (Frontend):**
```bash
cd "/path/to/P13-ContinuumAI/Prototype/code/frontend-react"
npm run dev
```

### Making Changes

#### Backend Changes:
1. Edit files in `backend/` or `api_server.py`
2. Flask auto-reloads (debug mode)
3. Test API endpoints with Postman or browser

#### Frontend Changes:
1. Edit React components in `frontend-react/src/`
2. Vite hot-reloads automatically
3. Changes appear instantly in browser

---

## Quick Commands Reference

### Start Development
```bash
# Backend (Terminal 1)
cd "/path/to/code"
source venv/bin/activate
python3 api_server.py

# Frontend (Terminal 2)
cd "/path/to/code/frontend-react"
npm run dev
```

### Install Dependencies
```bash
# Backend
pip install -r requirements.txt

# Frontend
npm install
```

### Build for Production
```bash
# Frontend
npm run build
```

---

