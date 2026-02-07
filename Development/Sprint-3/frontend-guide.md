# Frontend Implementation Summary

## 1. Pages & Routes Added

| Route | File | Purpose |
|-------|------|---------|
| `/dashboard` | `app/dashboard/page.tsx` | Welcome screen + Dataset selection (entry point after login) |
| `/workspace/[datasetId]` | `app/workspace/[datasetId]/page.tsx` | Main workspace with 3 tabs |

### App Flow
```
Login (/login)
    ↓
Dashboard (/dashboard)
    - Shows welcome message
    - Dataset cards (SilkRoute = ready, Connect DB = disabled)
    ↓ (click SilkRoute)
Workspace (/workspace/silkroute)
    ├── Tab 1: Table Profiling
    ├── Tab 2: Column Profiling
    └── Tab 3: Chart Builder
```

---

## 2. Component Architecture

```
app/
├── dashboard/page.tsx          # Welcome + dataset selection
├── workspace/[datasetId]/
│   └── page.tsx                # Workspace container with tabs
│
components/workspace/
├── TableProfilingTab.tsx       # Table-level profiling view
├── ColumnProfilingTab.tsx      # Column-level profiling view
├── ChartBuilderTab.tsx         # Drag-and-drop chart builder
└── index.ts                    # Barrel export

lib/
├── store.ts                    # Zustand global state
├── types.ts                    # TypeScript interfaces
├── mock-data.ts                # Hardcoded mock data (TEMPORARY)
└── query-provider.tsx          # React Query provider
```

---

## 3. Current Data Flow (Hardcoded)

Currently, **all data is hardcoded** in `lib/mock-data.ts`:

```
┌─────────────────────────────────────────────────────────┐
│                    mock-data.ts                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────┐ │
│  │ salesDetailed   │ │ customer360     │ │ storeDaily│ │
│  │ Profile         │ │ Profile         │ │ Profile   │ │
│  └────────┬────────┘ └────────┬────────┘ └─────┬─────┘ │
└───────────┼───────────────────┼────────────────┼───────┘
            │                   │                │
            ▼                   ▼                ▼
┌─────────────────────────────────────────────────────────┐
│              tableProfiles (Record<string, TableProfile>)│
└────────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    TableProfilingTab  ColumnProfilingTab  ChartBuilderTab
```

**No API calls are made yet.** Components directly import from `mock-data.ts`.

---

## 4. Data Format / TypeScript Interfaces

The frontend expects data in these formats (defined in `lib/types.ts`):

### TableProfile (main structure)
```typescript
interface TableProfile {
  tableName: string;
  rowCount: number;
  columnCount: number;
  missingPercentage: number;
  lastUpdated: string;
  duplicateRows: number;
  hasOutliers: boolean;
  columnRoleDistribution: {
    dimensions: number;
    measures: number;
    temporal: number;
  };
  columns: ColumnProfile[];
  keyInsights: string[];
  suggestedQuestions: string[];
}
```

### ColumnProfile (per-column metadata)
```typescript
interface ColumnProfile {
  name: string;
  role: 'dimension' | 'measure' | 'temporal';
  dataType: string;
  nullPercentage: number;
  uniqueCount: number;
  totalCount: number;
  
  // For dimensions
  cardinality?: 'low' | 'medium' | 'high';
  topValues?: Array<{ value: string; count: number }>;
  
  // For measures
  min?: number;
  max?: number;
  mean?: number;
  median?: number;
  outlierCount?: number;
  histogram?: Array<{ bin: string; count: number }>;
  
  // For temporal
  minDate?: string;
  maxDate?: string;
  granularity?: 'day' | 'week' | 'month' | 'year';
  timeSeriesData?: Array<{ date: string; count: number }>;
  
  // Suggestions
  suggestedCharts?: Array<{
    type: 'bar' | 'line' | 'pie' | 'histogram' | 'scatter';
    title: string;
    xAxis: string;
    yAxis?: string;
  }>;
}
```

### ChartConfig (for chart builder)
```typescript
interface ChartConfig {
  id: string;
  type: 'bar' | 'line' | 'pie' | 'histogram' | 'scatter';
  title: string;
  xAxis?: string;
  yAxis?: string;
  aggregation?: 'sum' | 'avg' | 'count' | 'min' | 'max';
}
```

---

## 5. Global State (Zustand Store)

```typescript
interface AppState {
  // Dataset selection
  activeDataset: string | null;
  setActiveDataset: (dataset: string | null) => void;
  
  // Aggregation table selection
  selectedAggregation: string;
  setSelectedAggregation: (agg: string) => void;
  
  // Column selection (for column profiling tab)
  selectedColumn: string | null;
  setSelectedColumn: (col: string | null) => void;
  
  // Active tab
  activeTab: 'table' | 'column' | 'chart';
  setActiveTab: (tab: 'table' | 'column' | 'chart') => void;
  
  // Chart builder state
  chartConfig: ChartConfig;
  setChartConfig: (config: Partial<ChartConfig>) => void;
  resetChartConfig: () => void;
}
```

---

## 6. Backend Endpoints Required

To make this a proper app, your backend team needs to implement these endpoints:

### 6.1 List Available Aggregations
```http
GET /api/datasets/{datasetId}/aggregations
```

**Response:**
```json
{
  "aggregations": [
    {
      "name": "sales_detailed",
      "schema": "aggregations",
      "rowCount": 45230,
      "lastUpdated": "2025-12-31"
    },
    {
      "name": "customer_360",
      "schema": "aggregations", 
      "rowCount": 2500,
      "lastUpdated": "2025-12-31"
    },
    {
      "name": "store_daily_performance",
      "schema": "aggregations",
      "rowCount": 2190,
      "lastUpdated": "2025-12-31"
    }
  ]
}
```

---

### 6.2 Table-Level Profile
```http
GET /api/profiling/aggregations/{tableName}/profile
```

**Response:** (matches `TableProfile` interface)
```json
{
  "tableName": "sales_detailed",
  "rowCount": 45230,
  "columnCount": 18,
  "missingPercentage": 2.3,
  "lastUpdated": "2025-12-31",
  "duplicateRows": 0,
  "hasOutliers": true,
  "columnRoleDistribution": {
    "dimensions": 8,
    "measures": 7,
    "temporal": 3
  },
  "columns": [
    {
      "name": "transaction_id",
      "role": "dimension",
      "dataType": "string",
      "nullPercentage": 0,
      "uniqueCount": 45230,
      "totalCount": 45230,
      "cardinality": "high"
    }
  ],
  "keyInsights": [
    "Online channel shows 42% growth over the year",
    "Top 10 hero SKUs account for 45% of total revenue"
  ],
  "suggestedQuestions": [
    "Which products drive the most revenue?",
    "How do online vs store sales compare?"
  ]
}
```

---

### 6.3 Column-Level Profile (Detailed)
```http
GET /api/profiling/aggregations/{tableName}/columns/{columnName}
```

**Response for dimension:**
```json
{
  "name": "channel",
  "role": "dimension",
  "dataType": "string",
  "nullPercentage": 0,
  "uniqueCount": 2,
  "totalCount": 45230,
  "cardinality": "low",
  "topValues": [
    { "value": "Store", "count": 28340 },
    { "value": "Online", "count": 16890 }
  ],
  "suggestedCharts": [
    { "type": "pie", "title": "Channel Split", "xAxis": "channel" }
  ]
}
```

**Response for measure:**
```json
{
  "name": "revenue",
  "role": "measure",
  "dataType": "decimal",
  "nullPercentage": 0,
  "uniqueCount": 4230,
  "totalCount": 45230,
  "min": 4.99,
  "max": 7899.94,
  "mean": 201.34,
  "median": 124.50,
  "outlierCount": 423,
  "histogram": [
    { "bin": "0-50", "count": 12340 },
    { "bin": "50-100", "count": 9870 },
    { "bin": "100-200", "count": 11230 }
  ]
}
```

**Response for temporal:**
```json
{
  "name": "transaction_date",
  "role": "temporal",
  "dataType": "date",
  "nullPercentage": 0,
  "uniqueCount": 365,
  "totalCount": 45230,
  "minDate": "2025-01-01",
  "maxDate": "2025-12-31",
  "granularity": "day",
  "timeSeriesData": [
    { "date": "2025-01", "count": 3245 },
    { "date": "2025-02", "count": 3120 }
  ]
}
```

---

### 6.4 Chart Data Endpoint
```http
POST /api/charts/data
```

**Request:**
```json
{
  "tableName": "sales_detailed",
  "chartType": "bar",
  "xAxis": "channel",
  "yAxis": "revenue",
  "aggregation": "sum"
}
```

**Response:**
```json
{
  "data": {
    "x": ["Store", "Online"],
    "y": [5678900.50, 3421000.25],
    "type": "bar"
  },
  "layout": {
    "title": "Revenue by Channel"
  }
}
```

---

### 6.5 Save Chart to Dashboard
```http
POST /api/charts/save
```

**Request:**
```json
{
  "userId": "user-123",
  "datasetId": "silkroute",
  "chartConfig": {
    "type": "bar",
    "title": "Revenue by Channel",
    "xAxis": "channel",
    "yAxis": "revenue",
    "aggregation": "sum"
  }
}
```

---

### 6.6 Get Saved Charts (for Dashboard)
```http
GET /api/charts/saved?userId={userId}
```

**Response:**
```json
{
  "charts": [
    {
      "id": "chart-1",
      "title": "Revenue by Channel",
      "type": "bar",
      "createdAt": "2025-02-07T10:30:00Z"
    }
  ]
}
```

---

## 7. Summary Table

| What | Current State | To Become Production |
|------|--------------|----------------------|
| Data source | `mock-data.ts` (hardcoded) | API calls to backend |
| Table profiles | Static JSON | `GET /api/profiling/aggregations/{table}/profile` |
| Column profiles | Embedded in table | `GET /api/profiling/aggregations/{table}/columns/{col}` |
| Chart data | Mock Plotly data | `POST /api/charts/data` |
| Saved charts | Not implemented | `POST /api/charts/save` + `GET /api/charts/saved` |

---

## 8. Next Steps for Frontend

Once backend endpoints are ready, the frontend needs to:

1. Replace mock imports with React Query hooks
2. Add loading/error states
3. Connect chart builder to real data
4. Implement dashboard with saved charts

---

## 9. Color Scheme Reference

| Element | Color |
|---------|-------|
| Primary accent | `#5237ff` |
| Primary hover | `#6347ff` |
| Background | `#060010` |
| Card background | `bg-white/5` |
| Borders | `border-white/10` |
| Text primary | `text-white` |
| Text secondary | `text-gray-400` |
| Text muted | `text-gray-500` |
