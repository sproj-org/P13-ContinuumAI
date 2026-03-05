# ContinuumAI - Project Update & Developer Guide

> Last Updated: February 17, 2026

---

## Overview

ContinuumAI is a data profiling and analytics web application that helps users explore aggregation tables, understand column statistics, and build visualizations. The app supports three mart tables in the `marts` schema: `mart_sales`, `mart_customers`, and `mart_stores`.

**Key Capabilities:**
- **Table Profiling** - View table metadata from pre-generated profile JSONs
- **Column Profiling** - Explore column statistics, distributions, and data quality
- **Chart Builder** - Build visualizations with real data from PostgreSQL database

---

## Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (Supabase) via SQLAlchemy ORM
- **Authentication:** JWT tokens (python-jose)
- **Password Hashing:** bcrypt (passlib)

### Frontend
- **Framework:** Next.js 15+ (App Router)
- **React:** v19
- **Styling:** TailwindCSS 4
- **State Management:** Zustand
- **Data Fetching:** TanStack Query (React Query)
- **Drag & Drop:** dnd-kit
- **Charts:** Plotly.js (react-plotly.js)
- **Animations:** Framer Motion

---

## Project Structure

```
code/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py          # Auth endpoints (signup, login, me)
│   │   │   └── profiling.py     # Profiling endpoints
│   │   ├── core/
│   │   │   ├── config.py        # Settings (env vars)
│   │   │   └── security.py      # JWT & password utils
│   │   ├── db/
│   │   │   ├── database.py      # SQLAlchemy setup
│   │   │   └── models.py        # User model
│   │   ├── schemas/
│   │   │   └── user.py          # Pydantic schemas
│   │   └── main.py              # FastAPI app entry
│   ├── out/                     # Pre-generated profile JSONs
│   │   ├── mart_sales_profile.json
│   │   ├── mart_customers_profile.json
│   │   └── mart_stores_profile.json
│   ├── requirements.txt
│   └── .env
│
└── frontend/
    ├── app/
    │   ├── page.tsx             # Landing page
    │   ├── login/page.tsx       # Login page
    │   ├── signup/page.tsx      # Signup page
    │   ├── dashboard/page.tsx   # Dashboard (post-login)
    │   └── workspace/[datasetId]/page.tsx  # Main workspace
    ├── components/
    │   ├── workspace/
    │   │   ├── TableProfilingTab.tsx    # Table-level profiling
    │   │   ├── ColumnProfilingTab.tsx   # Column-level profiling
    │   │   └── ChartBuilderTab.tsx      # Drag-drop chart builder
    │   ├── Cubes.tsx            # 3D animated cubes (landing)
    │   ├── ElectricBorder.tsx   # Electric border effect
    │   ├── Noise.tsx            # Noise texture overlay
    │   ├── ProtectedRoute.tsx   # Auth guard HOC
    │   ├── TargetCursor.tsx     # Custom cursor effect
    │   └── TextType.tsx         # Typewriter text effect
    ├── lib/
    │   ├── api.ts               # API client (auth + profiling)
    │   ├── api-types.ts         # TypeScript types for API responses
    │   ├── auth-context.tsx     # Auth context provider
    │   ├── hooks.ts             # React Query hooks
    │   ├── query-provider.tsx   # TanStack Query provider
    │   ├── store.ts             # Zustand store
    │   ├── transformers.ts      # Backend → Frontend data transformers
    │   └── types.ts             # Legacy frontend types
    └── public/
```

---

## API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/signup` | Register new user | No |
| POST | `/api/auth/login` | Login, returns JWT | No |
| GET | `/api/auth/me` | Get current user info | Yes |

**Request/Response Examples:**

```json
// POST /api/auth/signup
Request: { "username": "john", "email": "john@example.com", "password": "..." }
Response: { "access_token": "...", "token_type": "bearer", "user": {...} }

// POST /api/auth/login
Request: { "username": "john", "password": "..." }
Response: { "access_token": "...", "token_type": "bearer", "user": {...} }
```

### Profiling (`/api/profiling`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/profiling/aggregations` | List all available tables | No* |
| GET | `/api/profiling/aggregations/{table_name}/profile` | Get full table profile | No* |
| GET | `/api/profiling/aggregations/{table_name}/columns/{column_name}` | Get column profile | No* |
| POST | `/api/profiling/chart-data` | Query aggregated data for charts | No* |

*Note: Auth not currently enforced on profiling endpoints; can be added if needed.

**Available Tables (in `marts` schema):**
- `mart_sales` (29,924 rows, 44 columns)
- `mart_customers` 
- `mart_stores`

**Chart Data Endpoint:**

```json
// POST /api/profiling/chart-data
Request: {
  "table_name": "mart_sales",
  "x_axis": "channel_name",
  "y_axis": "revenue",
  "aggregation_fn": "sum",  // sum | avg | count | min | max
  "limit": 20
}

Response: {
  "x": ["Online", "Retail", "Wholesale"],
  "y": [125000.50, 98000.00, 45000.25],
  "title": "SUM(revenue) by channel_name",
  "x_axis_label": "channel_name",
  "y_axis_label": "SUM(revenue)"
}
```

**Validation Rules:**
- Table name must be in allowed list (`mart_sales`, `mart_customers`, `mart_stores`)
- Column names validated against table profile (prevents SQL injection)
- Aggregation function validated against column type (see Aggregation Compatibility)

---

## Frontend Pages

### Public Pages
- **`/`** - Landing page with animated 3D cubes, typewriter effect, login/signup CTAs
- **`/login`** - Login form
- **`/signup`** - Registration form

### Protected Pages (require auth)
- **`/dashboard`** - Post-login landing, links to workspace
- **`/workspace/[datasetId]`** - Main workspace with 3 tabs:
  - **Table Profiling** - Overview of selected table (row count, columns, missing %, insights)
  - **Column Profiling** - Detailed column stats (dimensions, measures, temporal)
  - **Chart Builder** - Drag-and-drop chart configuration

---

## Key Features Implemented

### 1. Authentication Flow
- JWT-based authentication
- Token stored in localStorage
- Protected routes via `ProtectedRoute` component
- Auth context provides `user`, `login()`, `logout()`, `isAuthenticated`

### 2. Table Profiling Tab
- Lists 3 aggregation tables (mart_sales, mart_customers, mart_stores)
- Shows table metadata: row count, column count, profiled date
- Displays calculated missing data percentage
- Shows column role distribution (dimensions/measures/temporal)
- Auto-generates key insights from profile data
- Suggests analytical questions

### 3. Column Profiling Tab
- Lists all columns grouped by role (dimension/measure/temporal)
- Shows column details: null %, unique values, total count
- **Dimension columns:** cardinality badge, top values bar chart, pie chart
- **Measure columns:** min/max/mean/median stats, suggested aggregations
- **Temporal columns:** date range, distinct days
- Suggests relevant charts based on column type

### 4. Chart Builder Tab
- Drag-and-drop interface using dnd-kit
- Fields grouped by role (dimensions, measures, temporal)
- Drop zones for X-axis, Y-axis, Color/Group
- Chart type selector: Bar, Line, Pie, Histogram
- Aggregation function selector: SUM, AVG, COUNT, MIN, MAX
- **Real-time data fetching from PostgreSQL database**
- **Smart aggregation validation** - disables invalid aggregations based on column type
- Live chart preview with Plotly.js

#### Aggregation Compatibility

| Y-Axis Column Role | Available Aggregations | Disabled |
|--------------------|------------------------|----------|
| **Measure** (numeric) | SUM, AVG, COUNT, MIN, MAX | None |
| **Temporal** (date/datetime) | COUNT, MIN, MAX | SUM, AVG |
| **Dimension** (categorical) | COUNT | SUM, AVG, MIN, MAX |

The frontend auto-switches to a valid aggregation if the user selects an incompatible column.

---

## Data Flow Architecture

### Profiling Flow (Table & Column Profiling)
```
┌─────────────────────────────────────────────────────────────┐
│  Frontend                                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ React Query  │───▶│ transformers │───▶│  Components  │  │
│  │   Hooks      │    │  .ts         │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐                                           │
│  │   api.ts     │                                           │
│  │  ApiClient   │                                           │
│  └──────────────┘                                           │
└─────────│───────────────────────────────────────────────────┘
          │ HTTP (GET)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                          │
│  ┌──────────────┐    ┌──────────────┐                      │
│  │  Routers     │───▶│  out/*.json  │  (Static profiles)   │
│  │  (profiling) │    │  (profiles)  │                      │
│  └──────────────┘    └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### Chart Builder Flow (Real Data)
```
┌─────────────────────────────────────────────────────────────┐
│  Frontend                                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ useChartData │───▶│   api.ts     │───▶│ ChartBuilder │  │
│  │   Hook       │    │ getChartData │    │   + Plotly   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────│───────────────────────────────────────────────────┘
          │ HTTP (POST /api/profiling/chart-data)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Validation  │───▶│ SQL Builder  │───▶│  PostgreSQL  │  │
│  │  (profile +  │    │ (GROUP BY)   │    │  (Supabase)  │  │
│  │   agg compat)│    │              │    │  marts.*     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Chart Builder Technical Workflow

### 1. User Interaction (Frontend)
```
User selects table → User drags columns to X/Y axes → User picks aggregation
```

### 2. Frontend Validation
```typescript
// ChartBuilderTab.tsx
const validAggregations = useMemo(() => {
  const role = columnRoleMap.get(chartConfig.yAxis);
  if (role === "measure") return ["sum", "avg", "count", "min", "max"];
  if (role === "temporal") return ["count", "min", "max"];
  return ["count"]; // dimension
}, [chartConfig.yAxis]);

// Auto-switch if current aggregation invalid
useEffect(() => {
  if (!validAggregations.includes(chartConfig.aggregationFn)) {
    setChartConfig({ aggregationFn: validAggregations[0] });
  }
}, [chartConfig.yAxis]);
```

### 3. API Request
```typescript
// hooks.ts - useChartData hook
POST /api/profiling/chart-data
{
  "table_name": "mart_sales",
  "x_axis": "channel_name",
  "y_axis": "revenue",
  "aggregation_fn": "sum",
  "limit": 20
}
```

### 4. Backend Validation (profiling.py)
```python
# Step 1: Validate table name against whitelist
if request.table_name not in AVAILABLE_TABLES:
    raise HTTPException(400, "Invalid table")

# Step 2: Validate columns exist in profile
x_column_profile = get_column_profile_info(table_name, x_axis)
y_column_profile = get_column_profile_info(table_name, y_axis)

# Step 3: Validate aggregation compatibility
is_valid, error = validate_aggregation_compatibility(y_column_profile, aggregation_fn)
# e.g., SUM on "city" (dimension) → Error: "Cannot apply SUM to 'city' - it's a dimension"
```

### 5. SQL Query Generation
```sql
-- Generated query (column names validated against profile)
SELECT 
    CAST("channel_name" AS TEXT) as x_value,
    SUM("revenue") as y_value
FROM marts."mart_sales"
WHERE "channel_name" IS NOT NULL
GROUP BY "channel_name"
ORDER BY y_value DESC
LIMIT 20
```

### 6. Response & Rendering
```json
{
  "x": ["Online", "Retail", "Wholesale"],
  "y": [125000.50, 98000.00, 45000.25],
  "title": "SUM(revenue) by channel_name"
}
```
Rendered via Plotly.js as bar/line/pie chart.

---

## Backend Profile Schema

Profiles in `out/` follow this structure (from `profile_schema.py`):

```python
DatasetProfile:
  - dataset_name: str
  - table_name: str | None
  - row_count: int
  - column_count: int
  - profiled_at: datetime
  - columns: List[ColumnProfile]

ColumnProfile:
  - name: str
  - physical_type: string | int | float | boolean | date | datetime
  - logical_type: numeric | categorical | datetime | boolean | text
  - effective_role: id | dimension | measure | datetime | boolean | text
  - row_count: int
  - distinct_count: int
  - null_count: int
  - null_fraction: float (0-1)
  - cardinality_bucket: low | medium | high
  - is_unique: bool
  - stats: NumericStats | CategoricalStats | DatetimeStats | BooleanStats | TextStats
```

---

## Environment Variables

### Backend (`.env`)
```env
# PostgreSQL (Supabase)
DATABASE_URL=postgresql://user:password@host:5432/postgres

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
FRONTEND_URL=http://localhost:3000
```

### Frontend (`.env`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running the App

### Backend
```bash
cd code/backend
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
# Runs on http://localhost:8000
```

### Frontend
```bash
cd code/frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

---

## What's Missing / TODO

### High Priority
- [ ] **Natural Language Query Interface** - Chat/prompt to query data
- [x] ~~**Actual Data Queries** - Connect to real database instead of static profiles~~ ✅ Done (Chart Builder)
- [x] ~~**Chart Data from API** - Currently generates mock data for charts~~ ✅ Done
- [ ] **Save/Export Charts** - Persist chart configurations

### Medium Priority
- [ ] **Auth on Profiling Endpoints** - Add JWT protection if needed
- [ ] **User Preferences** - Save selected table, chart configs per user
- [ ] **Dataset Upload** - Allow users to upload their own data
- [ ] **More Chart Types** - Scatter, heatmap, box plot, etc.
- [ ] **Chart Filters** - Add WHERE clause support to chart queries
- [ ] **Date Truncation** - Group temporal X-axis by day/week/month/year
- [ ] **Color/Group By** - Actually use the color drop zone in queries

### Low Priority
- [ ] **Dark/Light Mode Toggle** - Currently dark mode only
- [ ] **Mobile Responsive** - Workspace optimized for desktop
- [ ] **Error Boundaries** - Better error handling UI
- [ ] **Unit Tests** - Frontend and backend test coverage
- [ ] **API Documentation** - Auto-generated OpenAPI docs need polish

### Known Issues
- ESLint warnings about ternary complexity in some components
- `lib/types.ts` has some legacy types not fully migrated

### Recently Completed (Feb 17, 2026)
- ✅ Chart Builder fetches real data from PostgreSQL (`marts` schema)
- ✅ Backend validates aggregation compatibility with column types
- ✅ Frontend filters aggregation options based on Y-axis column role
- ✅ Auto-switch to valid aggregation when column changes
- ✅ Clear error messages for invalid queries (e.g., "Cannot apply SUM to 'city'")
- ✅ SQL injection prevention via column validation against profiles

---

## Color Scheme

The app uses a consistent color scheme:
- **Primary:** `#5237ff` (purple)
- **Background:** `#060010` (near-black)
- **Text:** white with various opacity levels
- **Role Colors:**
  - Dimensions: Blue (`blue-400/500`)
  - Measures: Emerald (`emerald-400/500`)
  - Temporal: Amber (`amber-400/500`)

---

## Contributing

1. Create a feature branch from `main`
2. Follow existing code patterns and file organization
3. Use TypeScript strict mode
4. Test your changes locally before PR
5. Update this document if adding new features or endpoints
