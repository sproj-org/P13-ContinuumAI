# ContinuumAI - Sales Intelligence Prototype

**Team:** SensAI  
**Project:** P13-ContinuumAI  
**Sprint:** Front-Back Integration  
**Date:** November 6, 2025

---

## LIST OF REQUIREMENTS COMPLETED IN THE PROTOTYPE

### Phase 1 Requirements 

#### 1. User Authentication
**Status:**  COMPLETED  
**Developer:** Muhammad Mustufa (Auth Specialist)  
**Implementation:**
- Secure JWT-based authentication system
- FastAPI backend with `/login` and `/register` endpoints
- Protected routes with `get_current_user` dependency
- Password hashing with bcrypt
- Session management and token validation

**Files:**
- `backend/app/auth/` - Authentication logic
- `backend/app/controllers/auth.py` - Auth endpoints
- `backend/app/core/security.py` - JWT & password hashing
- `Frontend/src/contexts/AuthContext.tsx` - Frontend auth state

---

#### 2. Basic UI & Data Pipeline
**Status:**  COMPLETED (Enhanced)  
**Developers:**
- **Muhammad Bazaf Shakeel** (Frontend Lead) - Next.js UI implementation
- **Muhammad Mustufa** (Database Specialist) - MySQL database setup
- **Ali Faizan** (Data Expert) - ETL pipeline and data models

**Implementation:**
- Modern Next.js 16 frontend with premium dark theme UI
- MySQL database hosted on Railway
- Complete ETL pipeline for CSV data processing
- SQLAlchemy models for all entities
- Automated data loading scripts

**Files:**
- `Frontend/src/` - Complete Next.js application
- `backend/database/` - ETL scripts and SQL schemas
- `backend/app/models/` - SQLAlchemy data models
- `backend/app/db/` - Database session management

---

#### 3. UC-005: Sales Trend Drilldown
**Status:**  COMPLETED (Enhanced with AI)  
**Developers:**
- **Ali Faizan** (Data & Tool Developer) - Chart generation functions
- **Umer Nafees** (Agent Orchestrator) - Intent classification & routing
- **Muhammad Bazaf Shakeel** (Frontend Lead) - Chart rendering UI

**Implementation:**
- Natural language query processing (beyond basic dropdowns)
- 17+ visualization functions including:
  - Sales Over Time with rolling averages
  - AOV (Average Order Value) Over Time
  - Revenue by Region/Country/City
  - Top Products by Revenue
  - Pareto Analysis (80/20 rule)
- Advanced filtering: date ranges, regions, sales reps, categories
- Filter display as centered subtitle in all charts
- Dynamic chart generation based on user queries

**Files:**
- `backend/app/utils/data_functions.py` - All chart generation functions
- `Frontend/src/components/chat/PlotlyChart.tsx` - Chart rendering
- `backend/app/orchestrator/gemini_router.py` - Query routing

---

### Phase 2 Requirements 

#### 4. Full Chatbot Interface
**Status:**  COMPLETED  
**Developers:**
- **Muhammad Bazaf Shakeel** (Frontend Lead) - Chat UI implementation
- **Nafees** (Backend Lead) - API integration
- **Umer Nafees** (Agent Orchestrator) - Gemini AI integration

**Implementation:**
- Conversational AI powered by Gemini 2.5 Pro
- Real-time streaming responses
- Natural language query understanding
- Dynamic intent classification
- Filter extraction from conversational queries
- Sidebar navigation with conversation history
- Dashboard to chat navigation with back button

**Files:**
- `Frontend/src/components/chat/ChatInterface.tsx` - Main chat UI
- `Frontend/src/components/chat/Sidebar.tsx` - Navigation
- `backend/app/orchestrator/gemini_router.py` - AI orchestration
- `backend/app/controllers/query.py` - Chat endpoint

---

#### 5. UC-002: Quota Tracking
**Status:**  COMPLETED  
**Developers:**
- **Ali Faizan** (Data & Tool Developer) - KPI calculation functions
- **Umer Nafees** (Agent Orchestrator) - Tool routing

**Implementation:**
- Real-time KPI tracking:
  - Total Revenue indicator
  - Total Orders counter
  - Average Order Value (AOV)
  - Conversion Rate gauge chart
- Performance comparison against targets
- Filter-based quota tracking (by date, region, rep, category)
- Visual gauge charts for conversion metrics

**Files:**
- `backend/app/utils/data_functions.py`:
  - `total_revenue()` function
  - `total_orders()` function
  - `avg_aov()` function
  - `conversion_rate()` function

---

#### 6. UC-003: Rep Benchmarking
**Status:**  COMPLETED  
**Developers:**
- **Ali Faizan** (Data & Tool Developer) - Benchmarking functions
- **Muhammad Mustufa** (Database Specialist) - Sales rep data schema

**Implementation:**
- Top Salespeople by Revenue (horizontal bar chart)
- Leaderboard table with rankings
- Average Sales Cycle by Rep comparison
- Performance KPIs:
  - Win rate tracking
  - Average deal size
  - Sales cycle duration
- Rep-specific filtering capabilities

**Files:**
- `backend/app/utils/data_functions.py`:
  - `top_salespeople()` function
  - `leaderboard()` function
  - `avg_sales_cycle_by_rep()` function

---

#### 7. UC-001: Revenue Drivers Analysis
**Status:**  COMPLETED  
**Developers:**
- **Ali Faizan** (Data & Tool Developer) - Analysis functions
- **Umer Nafees** (Agent Orchestrator) - AI-powered insights
- **Nafees** (Backend Lead) - API integration

**Implementation:**
- AI-powered revenue driver identification using Gemini
- Pareto Analysis for product revenue (80/20 rule)
- Multi-dimensional breakdowns:
  - Revenue by Product/Region/Country/City
  - Revenue by Category
  - Revenue by Sales Rep
- Opportunity funnel analysis
- Sales cycle distribution analysis
- Cumulative revenue tracking
- Natural language summaries of findings

**Files:**
- `backend/app/utils/data_functions.py`:
  - `pareto_product_revenue()` function
  - `revenue_by_region()` function
  - `revenue_by_country_top()` function
  - `revenue_by_city_top()` function
  - `opportunity_funnel()` function
  - `sales_cycle_histogram()` function
- `backend/app/orchestrator/gemini_router.py` - AI analysis

---

## SUMMARY OF COMPLETED WORK

### Sprint Tickets Completed: 17/17 

#### Database & Infrastructure (Muhammad Mustufa)
-  Ticket #1: Implement Universal Sales Schema in MySQL
-  Ticket #2: Populate MySQL Database with Sample Data
-  Ticket #3: Port & Implement FastAPI Authentication Backend

#### Data Models & Tools (Ali Faizan)
-  Ticket #4: Create SQLAlchemy Models
-  Ticket #5: Build Tool: UC-001 Revenue Drivers Analysis
-  Ticket #6: Build Tools: UC-002 (Quota) & UC-003 (Rep Benchmarking)
-  Ticket #7: Build Tool: UC-005 Graph Visualizations

#### Backend Integration (Nafees)
-  Ticket #8: Define and Finalize API Contract for /api/chat
-  Ticket #9: Implement Stubbed /api/chat Endpoint
-  Ticket #10: Integrate Auth and Orchestrator into /api/chat

#### Agent Orchestration (Umer)
-  Ticket #11: Build Orchestrator Service with Intent Classification
-  Ticket #12: Implement Tool Router in Orchestrator
-  Ticket #13: Format Orchestrator Output to Match API Contract

#### Frontend Development (Muhammad Bazaf Shakeel)
-  Ticket #14: Build Full Chatbot Interface (UI Shell)
-  Ticket #15: Port and Connect Authentication UI
-  Ticket #16: Connect Chat UI to /api/chat Endpoint
-  Ticket #17: Implement Dynamic Response Rendering (Text & Chart)

---

## Technical Stack

**Frontend:**
- Next.js 16.0.1 with React 19.2.0
- TypeScript 5
- Tailwind CSS 3.4.0
- Plotly.js for data visualization
- Context API for state management

**Backend:**
- FastAPI (Python 3.12)
- SQLAlchemy ORM
- MySQL Database (Railway hosted)
- JWT Authentication
- Pydantic for data validation

**AI/ML:**
- Google Gemini 2.5 Pro API
- Natural Language Processing
- Intent classification
- Filter extraction

---

## HOW TO ACCESS THE PROTOTYPE

### System Requirements
- Node.js 18+ and npm
- Python 3.12+
- Windows PowerShell (or compatible terminal)

### Access URLs

**Frontend Application:**
```
URL: http://localhost:3000
```

**Backend API:**
```
Base URL: http://localhost:8000
API Documentation: http://localhost:8000/docs
```

### Test Credentials

**Demo User Account:**
```
Email: demo@continuumai.com
Password: demo123
```

**Alternative Test Account:**
```
Email: test@example.com
Password: Test@123
```

### Running the Application

#### 1. Start Backend Server

```powershell
# Navigate to backend directory
cd C:\SensAi\P13-ContinuumAI\Prototype\Code\backend

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`

#### 2. Start Frontend Application

```powershell
# Navigate to frontend directory
cd C:\SensAi\P13-ContinuumAI\Prototype\Code\Frontend

# Install dependencies (first time only)
npm install

# Start the development server
npm run dev
```

Frontend will be available at: `http://localhost:3000`

### Quick Start Guide

1. **Login/Register:**
   - Navigate to `http://localhost:3000`
   - Click "Sign In" or "Sign Up"
   - Use demo credentials or create new account

2. **Access Dashboard:**
   - After login, you'll see the main dashboard
   - View key metrics and KPIs

3. **Start Chatting:**
   - Click "New Chat" or navigate to `/chat`
   - Type natural language queries

4. **Example Queries:**
   ```
   - "Show me sales trends for 2025"
   - "What are the top products by revenue?"
   - "Compare sales rep performance"
   - "Show revenue by region"
   - "Display conversion rate"
   - "Pareto analysis of products"
   - "Show sales over time with filters: January to March, West region"
   ```

### Database Connection

**Railway MySQL Database:**
```
Host: junction.proxy.rlwy.net
Port: 11930
Database: railway
User: root
Password: [Configured in backend/.env]
```

**Connection String:**
```
DATABASE_URL=mysql+pymysql://root:password@junction.proxy.rlwy.net:11930/railway
```

### API Endpoints

**Authentication:**
- `POST /auth/register` - Create new account
- `POST /auth/login` - Login and get JWT token

**Chat/Query:**
- `POST /api/query` - Send natural language query
- **Request Body:**
  ```json
  {
    "query": "Show me sales trends",
    "filters": {
      "date_from": "2025-01-01",
      "date_to": "2025-12-31",
      "regions": ["West", "East"],
      "categories": ["Technology"]
    }
  }
  ```

### Environment Configuration

**Backend (.env file location: `backend/.env`):**
```env
DATABASE_URL=mysql+pymysql://root:password@junction.proxy.rlwy.net:11930/railway
GEMINI_API_KEY=AIzaSyD3irRyX823E4YiRjbxFmWm7acd0tIZSJM
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=True
```

---

## ADDITIONAL INFORMATION

### Recent Enhancements (Sprint Day 5)

**Chart Rendering Improvements:**
1. **Filter Display Enhancement:**
   - Added `_format_title()` helper function for proper subtitle positioning
   - Filter information now displays as a centered subtitle below chart titles
   - Format: "Period: YYYY-MM-DD to YYYY-MM-DD | Regions: X, Y | Categories: Z"

2. **Axis Label Fix:**
   - Increased bottom margin from 120px to 150px for rotated x-axis labels
   - Increased right margin from 40px to 60px to prevent label cropping at 100% width
   - Increased top margin to 100px to accommodate subtitle
   - Added smaller font size (10px) for better label density
   - Charts now display properly at full width without cropping

3. **Conversion Rate Gauge:**
   - Fixed gauge chart height (300px) with proper domain settings
   - Ensures gauge fills container properly

4. **Navigation Enhancement:**
   - Added back button in chat interface to return to dashboard
   - Improved user flow between pages

### Key Features Beyond Requirements

1. **Advanced Filtering:**
   - Multi-dimensional filtering (date, region, rep, category)
   - Filter extraction from natural language queries
   - Persistent filter state across queries

2. **AI-Powered Analytics:**
   - Intent classification using Gemini 2.5 Pro
   - Contextual query understanding
   - Automated chart selection based on query intent

3. **Production-Ready UI/UX:**
   - Premium dark theme design
   - Responsive layout (mobile/tablet/desktop)
   - Real-time streaming responses
   - Loading states and error handling
   - Smooth animations and transitions

4. **Comprehensive Data Pipeline:**
   - ETL scripts for data processing
   - Data validation and cleaning
   - Automated schema migration
   - Sample data generation

### Testing Documentation

**Test Filter Scenarios:**
- Located in: `backend/TEST_FILTERS.md`
- Contains comprehensive test cases for all chart functions
- Includes examples with and without filters

### Project Structure

```
P13-ContinuumAI/
├── Prototype/
│   ├── Code/
│   │   ├── backend/
│   │   │   ├── app/
│   │   │   │   ├── auth/          # Authentication logic
│   │   │   │   ├── controllers/   # API endpoints
│   │   │   │   ├── core/          # Config & security
│   │   │   │   ├── db/            # Database session
│   │   │   │   ├── models/        # SQLAlchemy models
│   │   │   │   ├── orchestrator/  # Gemini AI integration
│   │   │   │   ├── schemas/       # Pydantic schemas
│   │   │   │   └── utils/         # Data functions & tools
│   │   │   ├── database/          # ETL scripts & data
│   │   │   ├── requirements.txt
│   │   │   └── .env
│   │   └── Frontend/
│   │       ├── src/
│   │       │   ├── app/           # Next.js pages
│   │       │   ├── components/    # React components
│   │       │   ├── contexts/      # State management
│   │       │   ├── lib/           # API utilities
│   │       │   └── types/         # TypeScript types
│   │       ├── package.json
│   │       └── next.config.ts
│   └── README.md (this file)
```

### Known Limitations

1. **Prototype Scope:**
   - Demo data only (SampleSuperstore dataset)
   - Single-tenant architecture
   - Limited to predefined chart types

2. **Scalability:**
   - Suitable for prototype/demo purposes
   - Production deployment would require:
     - Database connection pooling
     - Caching layer (Redis)
     - Rate limiting
     - Load balancing

3. **Security:**
   - API key stored in .env (suitable for prototype)
   - Production would require secure key management (AWS Secrets Manager, Azure Key Vault)

### Future Enhancements (Post-Prototype)

1. **Advanced Analytics:**
   - Predictive modeling
   - Anomaly detection
   - Trend forecasting

2. **Additional Visualizations:**
   - Custom dashboard builder
   - Export to PDF/Excel
   - Interactive drill-down capabilities

3. **Collaboration Features:**
   - Share insights with team
   - Comment on charts
   - Scheduled reports

4. **Mobile Application:**
   - Native iOS/Android apps
   - Push notifications for alerts
   - Offline data access

### Team Contributions Summary

**Muhammad Mustufa (Database & Auth Specialist):**
- Database schema design and implementation
- ETL pipeline development
- Authentication system (JWT, password hashing)
- Data population and validation
- Total Contribution: ~20% of codebase

**Ali Faizan (Data & Tool Developer):**
- SQLAlchemy models for all entities
- 17+ data analysis and visualization functions
- All chart generation logic (Plotly)
- Business logic for KPIs and metrics
-Deployment
- Total Contribution: ~15% of codebase

**Nafees (Backend Lead):**
- API architecture and contract definition
- Backend service integration
- Auth + Orchestrator integration
- API endpoint implementation
- Sprint coordination and management
- Total Contribution: ~20% of codebase

**Umer  (Agent Orchestrator):**
- Gemini AI integration
- Intent classification system
- Tool routing logic
- Filter extraction from queries
- Response formatting
- Total Contribution: ~30% of codebase

**Muhammad Bazaf Shakeel (Frontend Lead):**
- Complete Next.js application
- Chat interface UI/UX
- Dynamic chart rendering
- Authentication UI
- State management
- Responsive design
- Total Contribution: ~15% of codebase

### Support & Contact

For technical issues or questions about the prototype:
- Check API documentation: `http://localhost:8000/docs`
- Review test documentation: `backend/TEST_FILTERS.md`
- Contact team lead: Nafees (Backend Lead)

---

**Prototype Status:**  All 7 Use Cases Completed  
**Last Updated:** November 6, 2025  
**Version:** 1.0.0 (Sprint Complete)
