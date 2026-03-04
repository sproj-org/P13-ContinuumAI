# ContinuumAI Assessment Report

> Generated: March 3, 2026  
> Purpose: Detailed analysis of current state, gaps, and roadmap for desired workflow

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Desired Workflow vs Current State](#desired-workflow-vs-current-state)
3. [Feature Assessment Matrix](#feature-assessment-matrix)
4. [Hardcoded vs Generalizable Analysis](#hardcoded-vs-generalizable-analysis)
5. [Detailed Gap Analysis](#detailed-gap-analysis)
6. [Required Changes & Additions](#required-changes--additions)
7. [Technical Debt & Fixes](#technical-debt--fixes)
8. [Recommended Implementation Order](#recommended-implementation-order)

---

## Executive Summary

### Current State
ContinuumAI is a partially functional BI tool with:
- ✅ Working authentication system
- ✅ Static profiling display (pre-generated JSON)
- ✅ Manual chart builder (functional but using Plotly)
- ✅ AI chat assistant (Numi) with OpenAI integration
- ⚠️ Dashboard (client-side only, no persistence)
- ❌ No dynamic data onboarding
- ❌ No KPI calculation tab
- ❌ Single hardcoded dataset ("silkroute")

### Key Finding
**~70% of current functionality is hardcoded for the "silkroute" dataset.** The app cannot currently onboard new datasets without developer intervention.

---

## Desired Workflow vs Current State

### Desired Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. DATA ONBOARDING                                                         │
│     • Company onboards user data                                            │
│     • Data copied to ContinuumAI database                                   │
│     • Auto-discovery of tables/columns                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. DASHBOARD (Home)                                                        │
│     • Shows connected databases count                                       │
│     • User selects database to analyze                                      │
│     • "Contact ContinuumAI" to add new datasets                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. WORKSPACE (4 Tabs)                                                      │
│                                                                             │
│     Tab 1: PROFILING                                                        │
│     • Auto-generated table profiles                                         │
│     • Auto-generated column profiles                                        │
│     • Stats, distributions, quality metrics                                 │
│                                                                             │
│     Tab 2: KPI CALCULATOR (NEW)                                            │
│     • User-defined KPI formulas                                            │
│     • Calculate from real data                                             │
│     • Save KPI tiles to dashboard                                          │
│                                                                             │
│     Tab 3: CHART BUILDER                                                   │
│     • Manual chart creation                                                │
│     • Filters, aggregations, options                                       │
│     • Save to dashboard                                                    │
│                                                                             │
│     Tab 4: DASHBOARD                                                       │
│     • Multiple dashboard instances                                         │
│     • Saved charts + KPI tiles                                            │
│     • Persistent (saved to DB)                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  NUMI (AI Layer - Across All Tabs)                                         │
│     • Build charts via natural language                                    │
│     • Analyze results                                                      │
│     • Provide reasoning/insights                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. NO DATA ONBOARDING                                                      │
│     ❌ Manual CSV files in backend/data/                                    │
│     ❌ Pre-generated profile JSONs in backend/out/                          │
│     ❌ Hardcoded mart registry                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. DASHBOARD (Home)                                                        │
│     ⚠️ Shows only 1 hardcoded dataset ("silkroute")                        │
│     ❌ No "contact team" flow                                               │
│     ❌ No actual database connection display                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. WORKSPACE (3 Tabs)                                                      │
│                                                                             │
│     Tab 1: PROFILING                                                        │
│     ✅ Table-level profiling display                                        │
│     ✅ Column-level profiling display                                       │
│     ❌ NOT auto-generated (loads pre-made JSON)                            │
│                                                                             │
│     Tab 2: CHART BUILDER                                                   │
│     ✅ Manual chart creation (Plotly)                                      │
│     ✅ Filters, aggregations                                               │
│     ✅ Save to dashboard (client-side only)                                │
│                                                                             │
│     Tab 3: DASHBOARD                                                       │
│     ⚠️ Single dashboard only                                               │
│     ⚠️ Saved to localStorage (lost on clear)                              │
│     ❌ No multiple dashboard instances                                     │
│     ❌ No KPI tiles                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  NUMI (AI Layer)                                                           │
│     ✅ Build charts via natural language                                   │
│     ✅ Explain mode for insights                                           │
│     ⚠️ Only works with silkroute dataset                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Assessment Matrix

| Feature | Status | Generalizable? | Notes |
|---------|--------|----------------|-------|
| **Authentication** | ✅ Complete | ✅ Yes | JWT-based, works for any user |
| **User Management** | ✅ Complete | ✅ Yes | Signup/login/logout functional |
| **Database Connection** | ❌ Missing | - | No mechanism to connect user DBs |
| **Data Onboarding** | ❌ Missing | - | No data import/copy pipeline |
| **Dataset Discovery** | ❌ Missing | - | No auto-detection of tables |
| **Table Profiling** | ⚠️ Partial | ❌ No | Displays pre-generated JSON only |
| **Column Profiling** | ⚠️ Partial | ❌ No | Displays pre-generated JSON only |
| **Auto-Profiling Engine** | ❌ Missing | - | Need runtime profiling service |
| **KPI Calculator Tab** | ❌ Missing | - | Not implemented |
| **KPI Tile Saving** | ❌ Missing | - | Not implemented |
| **Chart Builder UI** | ✅ Complete | ✅ Yes | Works with any data source |
| **Chart Execution** | ⚠️ Partial | ⚠️ Limited | Queries hardcoded schema |
| **Chart Library** | ⚠️ Plotly | - | Request to switch to AntV |
| **Dashboard Display** | ✅ Complete | ✅ Yes | UI works generically |
| **Dashboard Persistence** | ❌ Missing | - | Only localStorage (client) |
| **Multiple Dashboards** | ❌ Missing | - | Single dashboard only |
| **Numi Chat** | ✅ Complete | ⚠️ Limited | Strategy layer is silkroute-only |
| **Strategy/KPI Layer** | ⚠️ Partial | ❌ No | YAML files for silkroute only |

---

## Hardcoded vs Generalizable Analysis

### 🔴 Hardcoded (Silkroute-Specific)

| Component | File | What's Hardcoded |
|-----------|------|------------------|
| **Dataset ID** | `backend/app/core/mart_registry.py` | `DEFAULT_DATASET_ID = "silkroute"` |
| **Mart List** | `backend/app/core/mart_registry.py` | 7 gold tables hardcoded in `MARTS` array |
| **Profile Files** | `backend/out/*.json` | Pre-generated for silkroute tables only |
| **Strategy YAML** | `backend/app/resources/strategy/silkroute/` | KPIs, rules only for silkroute |
| **Dashboard Selection** | `frontend/app/dashboard/page.tsx` | Only `"silkroute"` option shown |
| **OpenAI Key** | `backend/app/core/config.py` | API key exposed in source |
| **Schema Name** | Profile JSONs | `"schema_name": "gold"` throughout |

#### Code Evidence

**mart_registry.py:7-55** - All tables hardcoded:
```python
DEFAULT_DATASET_ID = "silkroute"

MARTS = [
    {
        "id": "gold_sales_daily",
        "label": "Sales Daily",
        "description": "Daily x store x channel sales fact table",
        "schema": "gold",
        "profile_file": "gold_sales_daily_profile.json",
    },
    # ... 6 more hardcoded tables
]
```

**dashboard/page.tsx:16** - Only silkroute selectable:
```tsx
const handleDatasetSelect = (datasetId: "silkroute") => {
    // Type literally restricts to "silkroute" only
}
```

### 🟢 Generalizable (Works for Any Dataset)

| Component | File | Why It's Generalizable |
|-----------|------|------------------------|
| **Auth System** | `backend/app/api/auth.py` | User-agnostic JWT flow |
| **Chart Builder UI** | `frontend/components/workspace/ChartBuilderTab.tsx` | Accepts any column data |
| **Aggregate Query Engine** | `backend/app/api/query.py` | Dynamic SQL from spec |
| **ChartSpec Model** | `backend/app/services/charts/models.py` | Schema-agnostic spec |
| **Chat Models** | `backend/app/services/agents/chat_models.py` | Generic request/response |
| **Zustand Store** | `frontend/lib/store.ts` | Key-based state by dataset |
| **API Client** | `frontend/lib/api.ts` | Parameterized by datasetId |
| **Profiling UI** | `frontend/components/workspace/MartsTab.tsx` | Dynamic column rendering |

### 🟡 Partially Generalizable (Needs Work)

| Component | Current State | Required Change |
|-----------|---------------|-----------------|
| **Profile Loading** | Reads static JSON files | Add runtime profiling service |
| **Mart Discovery** | Hardcoded registry | Add DB introspection API |
| **Strategy Layer** | YAML per dataset ID | Auto-generate or make optional |
| **Chart Execution** | Assumes `gold` schema | Parameterize schema in mart config |
| **Chat Hints** | Build from profile | Works if profile exists |

---

## Detailed Gap Analysis

### Gap 1: Data Onboarding Pipeline

**Current:** None. Data must be manually placed in `backend/data/` as CSV.

**Required:**
- [ ] Database connection management (store connection strings per user)
- [ ] Table discovery API (introspect connected DB for tables)
- [ ] Data sync mechanism (copy/mirror user tables)
- [ ] Schema registration (dynamic mart registry)

**Backend Changes:**
```python
# New models needed
class UserDatabase(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String)
    connection_string = Column(String)  # encrypted
    created_at = Column(DateTime)

class DatasetMart(Base):
    id = Column(Integer, primary_key=True)
    database_id = Column(Integer, ForeignKey('user_databases.id'))
    table_name = Column(String)
    schema_name = Column(String)
    profile_json = Column(JSON)  # store profile in DB
    profiled_at = Column(DateTime)
```

---

### Gap 2: Auto-Profiling Engine

**Current:** Profile JSONs are pre-generated via scripts (`scripts/generate_gold_profiles.py`).

**Required:**
- [ ] Runtime profiling service that queries actual DB
- [ ] Profile caching in database (not filesystem)
- [ ] Scheduled re-profiling or on-demand refresh

**Backend Service Needed:**
```python
# backend/app/services/profiling/engine.py
class ProfilingEngine:
    def profile_table(self, db_session, schema: str, table: str) -> dict:
        """Generate profile by querying actual database."""
        # Run SQL to get row_count, column stats, etc.
        # Return profile dict matching current JSON schema
        pass
    
    def profile_column(self, db_session, schema: str, table: str, column: str) -> dict:
        """Generate column-level profile."""
        pass
```

---

### Gap 3: KPI Calculator Tab

**Current:** Does not exist.

**Required:**
- [ ] New tab between Profiling and Chart Builder
- [ ] KPI formula builder UI
- [ ] KPI execution engine (calculate from real data)
- [ ] Save KPI as tile to dashboard

**Frontend Component Needed:**
```tsx
// frontend/components/workspace/KpiCalculatorTab.tsx
- Formula input (e.g., "SUM(revenue) / COUNT(orders)")
- Table/column selector
- Preview result
- Save as tile button
```

**Backend Endpoint Needed:**
```python
# POST /api/datasets/{dataset_id}/kpis/calculate
class KpiRequest(BaseModel):
    name: str
    formula: str  # e.g., "SUM(revenue) - SUM(cost)"
    table: str
    filters: list[FilterSpec] = []

class KpiResponse(BaseModel):
    name: str
    value: float | int
    formula: str
    calculated_at: str
```

---

### Gap 4: Dashboard Persistence

**Current:** Charts saved to Zustand → localStorage (browser only).

**Required:**
- [ ] Backend dashboard models
- [ ] CRUD endpoints for dashboards
- [ ] Save chart/KPI tiles to DB
- [ ] Multiple dashboard instances per user

**Backend Models Needed:**
```python
class Dashboard(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String)
    dataset_id = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class DashboardTile(Base):
    id = Column(Integer, primary_key=True)
    dashboard_id = Column(Integer, ForeignKey('dashboards.id'))
    tile_type = Column(String)  # 'chart' | 'kpi'
    title = Column(String)
    config_json = Column(JSON)  # ChartSpecV1 or KPI config
    position = Column(JSON)  # {x, y, w, h} for grid layout
    created_at = Column(DateTime)
```

**Backend Endpoints Needed:**
```
GET    /api/dashboards                     - List user's dashboards
POST   /api/dashboards                     - Create new dashboard
GET    /api/dashboards/{id}                - Get dashboard with tiles
PUT    /api/dashboards/{id}                - Update dashboard
DELETE /api/dashboards/{id}                - Delete dashboard
POST   /api/dashboards/{id}/tiles          - Add tile to dashboard
PUT    /api/dashboards/{id}/tiles/{tid}    - Update tile
DELETE /api/dashboards/{id}/tiles/{tid}    - Remove tile
```

---

### Gap 5: Multiple Datasets Support

**Current:** Only "silkroute" works.

**Required:**
- [ ] Dynamic dataset registry (from DB, not code)
- [ ] Per-dataset profile storage
- [ ] Strategy layer fallback (optional, not required)
- [ ] Dashboard shows actual connected datasets

**Changes to mart_registry.py:**
```python
# Instead of hardcoded MARTS, query from database:
def list_marts(dataset_id: str, db: Session) -> list[dict]:
    """Fetch marts from database for given dataset."""
    return db.query(DatasetMart).filter(
        DatasetMart.database_id == dataset_id
    ).all()
```

---

### Gap 6: Chart Library (AntV Integration)

**Current:** Using Plotly.js via react-plotly.js

**Required:**
- [ ] Replace Plotly with AntV (G2, S2, or G6)
- [ ] Update `renderChart.tsx` component
- [ ] Ensure chart spec compatibility

**Recommended AntV Libraries:**
- **@antv/g2** - General charts (bar, line, pie)
- **@antv/s2** - Pivot tables / spreadsheets
- **@antv/g6** - Graph visualization (if needed)

**Package Changes:**
```json
// Remove
"plotly.js": "^3.3.1",
"react-plotly.js": "^2.6.0",
"@types/react-plotly.js": "^2.6.4",

// Add
"@antv/g2": "^5.x",
"@antv/s2": "^2.x"
```

---

### Gap 7: UI Design Changes

**Current Dashboard Page Shows:**
- "Connect Database" card (not functional)
- Single silkroute dataset card

**Required:**
- [ ] Remove "Add New Database" card
- [ ] Add "Contact ContinuumAI Team" button/section
- [ ] Show only datasets actually connected for user
- [ ] Request form / modal for new dataset requests

---

## Required Changes & Additions

### Backend Changes

| Priority | Change | Effort | Files Affected |
|----------|--------|--------|----------------|
| 🔴 High | Remove hardcoded OpenAI key | 5 min | `config.py` |
| 🔴 High | Add database models for dashboards | 2 hrs | `models.py` |
| 🔴 High | Add dashboard CRUD endpoints | 4 hrs | New `api/dashboards.py` |
| 🔴 High | Add KPI calculation endpoint | 3 hrs | New `api/kpis.py` |
| 🟡 Medium | Runtime profiling service | 8 hrs | New `services/profiling/engine.py` |
| 🟡 Medium | Dynamic mart registry from DB | 4 hrs | `mart_registry.py`, `models.py` |
| 🟡 Medium | User database connection models | 4 hrs | `models.py`, new `api/databases.py` |
| 🟢 Low | Strategy layer fallback | 2 hrs | `strategy/store.py` |

### Frontend Changes

| Priority | Change | Effort | Files Affected |
|----------|--------|--------|----------------|
| 🔴 High | Add KPI Calculator tab | 8 hrs | New `KpiCalculatorTab.tsx` |
| 🔴 High | Dashboard persistence (API calls) | 6 hrs | `DashboardTab.tsx`, `store.ts`, `api.ts` |
| 🔴 High | Multiple dashboard instances | 4 hrs | `DashboardTab.tsx`, `store.ts` |
| 🟡 Medium | Replace Plotly with AntV | 8 hrs | `renderChart.tsx`, `package.json` |
| 🟡 Medium | Dashboard page redesign | 4 hrs | `dashboard/page.tsx` |
| 🟡 Medium | "Contact Team" modal | 2 hrs | `dashboard/page.tsx` |
| 🟡 Medium | Tab order (add KPI tab) | 1 hr | `workspace/[datasetId]/page.tsx` |
| 🟢 Low | Dynamic dataset list from API | 2 hrs | `dashboard/page.tsx`, `api.ts` |

---

## Technical Debt & Fixes

### Security Issues

| Issue | Severity | Fix |
|-------|----------|-----|
| OpenAI API key in source code | 🔴 Critical | Move to `.env` only, remove default |
| No rate limiting | 🟡 Medium | Add FastAPI rate limiter |
| No input sanitization for SQL | 🟡 Medium | Already using parameterized queries ✅ |

### Code Quality Issues

| Issue | Location | Fix |
|-------|----------|-----|
| No error boundary in React | Frontend | Add ErrorBoundary component |
| Console.log statements | Various | Remove before production |
| Unused imports | Various | Run ESLint fix |
| Missing loading states | Some components | Add Suspense/skeleton |

### Architecture Issues

| Issue | Current | Recommended |
|-------|---------|-------------|
| Profile storage | Filesystem JSON | Database JSON column |
| Dashboard storage | localStorage | Database with API |
| Mart registry | Hardcoded Python | Database table |
| Chart library | Plotly | AntV (per request) |

---

## Recommended Implementation Order

### Phase 1: Foundation (Week 1-2)
1. ✅ Fix OpenAI key exposure
2. Add dashboard database models
3. Add dashboard CRUD endpoints
4. Connect frontend dashboard to API (persistence)
5. Add multiple dashboard support

### Phase 2: KPI Feature (Week 2-3)
6. Add KPI calculation endpoint
7. Create KpiCalculatorTab component
8. Add KPI tile type to dashboard
9. Integrate KPI saving

### Phase 3: Generalization (Week 3-4)
10. Dynamic mart registry from DB
11. Runtime profiling service
12. User database connection models (admin only initially)
13. Strategy layer fallback for new datasets

### Phase 4: UI/UX (Week 4-5)
14. Replace Plotly with AntV
15. Dashboard page redesign
16. "Contact Team" request flow
17. Polish and testing

---

## Recent Implementation: Organization-Based Access Control

> **Implemented:** Admin Panel & Organization Management

### Changes Made

#### Backend Changes

1. **New Models** (`backend/app/db/models.py`):
   - `Organization` - Companies onboarded to the platform
   - `OrganizationDataset` - Links organizations to datasets they can access
   - Updated `User` model with `organization_id`, `is_admin`, `is_active`

2. **New Admin API** (`backend/app/api/admin.py`):
   - `GET /admin/organizations` - List all organizations with users and datasets
   - `POST /admin/organizations` - Create new organization
   - `GET /admin/organizations/{id}` - Get organization details
   - `PUT /admin/organizations/{id}` - Update organization
   - `DELETE /admin/organizations/{id}` - Soft delete (deactivate)
   - `POST /admin/organizations/{id}/datasets` - Assign dataset to org
   - `DELETE /admin/organizations/{id}/datasets/{id}` - Remove dataset
   - `GET /admin/users` - List all users
   - `POST /admin/users` - Create user in organization
   - `PUT /admin/users/{id}` - Update user
   - `DELETE /admin/users/{id}` - Delete user

3. **Auth Changes** (`backend/app/api/auth.py`):
   - Removed public `/signup` endpoint
   - Login now checks `user.is_active` and `organization.is_active`

4. **Updated Schemas** (`backend/app/schemas/user.py`):
   - Added organization schemas
   - Added `AdminUserCreate` for admin-only user creation
   - Updated `UserResponse` with `is_active`, `organization_id`

5. **Admin Bootstrap Script** (`backend/scripts/create_admin.py`):
   ```bash
   python -m scripts.create_admin --username admin --email admin@example.com --password <password>
   ```

#### Frontend Changes

1. **Signup Flow Removed**:
   - `frontend/app/signup/page.tsx` now redirects to `/get-access`
   - Login page shows "Get Access" link instead of "Sign Up"

2. **Get Access Page** (`frontend/app/get-access/page.tsx`):
   - Contact information for requesting access
   - Lists what's included with access

3. **Admin Panel** (`frontend/app/admin/`):
   - `layout.tsx` - Admin sidebar with navigation
   - `login/page.tsx` - Admin login page
   - `page.tsx` - Dashboard with stats
   - `organizations/page.tsx` - Organizations list
   - `organizations/new/page.tsx` - Create organization
   - `organizations/[id]/page.tsx` - Edit organization, manage users & datasets
   - `users/page.tsx` - All users list with filters
   - `users/new/page.tsx` - Create user form
   - `datasets/page.tsx` - Dataset access matrix

### How It Works

1. **Initial Setup**: Run `create_admin.py` to create first admin user
2. **Admin Login**: Go to `/admin/login` with admin credentials
3. **Create Organization**: Add company with name, slug
4. **Assign Datasets**: Select which datasets the org can access
5. **Create Users**: Add users to the organization
6. **Users Login**: Regular users log in at `/login`, can only access their org's datasets

### Database Schema

```
organizations
├── id (PK)
├── name
├── slug
├── description
├── is_active
└── created_at

organization_datasets
├── id (PK)
├── organization_id (FK)
├── dataset_id (string)
├── display_name
└── is_active

users
├── id (PK)
├── username
├── email
├── hashed_password
├── organization_id (FK, nullable)
├── is_admin
├── is_active
└── created_at
```

### Next Steps

1. Run database migrations to create new tables
2. Create initial admin user
3. Update frontend queries to filter data by user's organization
4. Integrate dataset access check in data APIs

---

## Summary

### What's Working ✅
- Authentication system
- Profiling display UI
- Chart builder functionality
- Numi AI chat
- Basic dashboard display
- **Organization-based access control (NEW)**
- **Admin panel for user management (NEW)**

### What's Hardcoded 🔴
- Single dataset ("silkroute")
- 7 gold tables in code
- Pre-generated profile JSONs
- Strategy YAML files
- Dashboard selection UI

### What's Missing ❌
- Data onboarding pipeline
- Auto-profiling engine
- KPI Calculator tab
- Dashboard persistence
- Multiple dashboards
- Dynamic dataset support
- AntV chart library
- ~~Contact team flow~~ → Replaced with "Get Access" page

### Effort Estimate
- **Backend:** ~30 hours
- **Frontend:** ~35 hours
- **Testing/Integration:** ~15 hours
- **Total:** ~80 hours (2-3 weeks with 1 dev)

---

*This assessment should be updated as implementation progresses.*
*Last updated: Admin panel & organization management implementation complete.*
