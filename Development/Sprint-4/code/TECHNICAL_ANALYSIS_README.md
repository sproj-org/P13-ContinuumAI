# ContinuumAI Technical Analysis (Sprint-4)

Date: 2026-03-16
Scope: Full-stack codebase audit for architecture, workflows, endpoints, datasets, and hardcoded vs generalized behavior.

## 1) What this app is

ContinuumAI is a full-stack analytics product with:
- Frontend: Next.js App Router + React + TypeScript (`frontend/`)
- Backend: FastAPI + SQLAlchemy + Pydantic (`backend/`)
- Database: PostgreSQL (Supabase-compatible via `DATABASE_URL`)
- Auth: JWT bearer tokens
- AI layer: OpenAI-backed chat orchestration with deterministic fallback behavior
- Analytics model: dataset-scoped marts, profile JSON metadata, aggregate/chart execution
- Strategy layer: YAML-managed strategy bundle + KPI registry + revisioned updates

At runtime, the backend serves APIs under `/api/*` and the frontend calls those APIs using `NEXT_PUBLIC_API_URL`.

## 2) High-level architecture and flow

### Backend composition
- App entrypoint: `backend/app/main.py`
- Routers mounted under `/api`:
  - `auth`, `admin`, `profiling`, `datasets`, `saved-charts`, `chat-threads`, `debug`, `decision`, `strategy` (bundle), `strategy/agent`, `kpi-registry`
- DB layer:
  - SQLAlchemy session/engine in `backend/app/db/database.py`
  - Core tables in `backend/app/db/models.py`
- Dataset registry:
  - `backend/app/core/mart_registry.py` maps `dataset_id -> marts`
- Chart execution:
  - `backend/app/services/charts/spec_resolver.py` resolves ChartSpec and delegates to aggregate engine (`app/api/query.py`)
- AI chat orchestration:
  - `backend/app/services/agents/chat_orchestrator.py`
  - Uses mart profile metadata + strategy hints + OpenAI JSON plans
  - Falls back to deterministic planning on missing key or OpenAI failure

### Frontend composition
- Public pages: `frontend/app/page.tsx`, `/login`, `/get-access`, `/support`
- Auth state: `frontend/lib/auth-context.tsx`
- Workspace shell: `frontend/app/workspace/[datasetId]/page.tsx`
- Core workspace tabs:
  - Profiling/Marts
  - Chart Builder
  - Dashboard
  - Strategy
- API client: `frontend/lib/api.ts`
- Query hooks: `frontend/lib/hooks.ts`
- Persistent app state: `frontend/lib/store.ts`
- Chat thread sync: `frontend/lib/useChatSync.ts`

## 3) User workflow (technical)

### A) Access and onboarding
1. User lands on `/`.
2. Login flow:
- `/login` calls `POST /api/auth/login`.
- On success, frontend stores `access_token` in localStorage.
- Auth context verifies with `GET /api/auth/me`.
3. Public signup is disabled:
- Backend has no signup route; `frontend/app/signup/page.tsx` redirects to `/get-access`.
4. Actual account creation path:
- Admin creates users via admin APIs/UI.
- Script `backend/scripts/create_admin.py` bootstraps first admin.

### B) Dataset selection and workspace
1. Authenticated user reaches `/dashboard`.
2. Dashboard currently shows a single selectable dataset card (`silkroute`) and routes to `/workspace/silkroute`.
3. Workspace route param `[datasetId]` drives data calls and store selection.

### C) Profiling and marts
1. Workspace loads `GET /api/datasets/{dataset_id}/profiling/aggregations`.
2. User selects a mart (table).
3. Frontend calls profile endpoints for table/column metadata.

### D) Charting and queries
1. Chart Builder builds `ChartSpecV1`.
2. Frontend calls `POST /api/datasets/{dataset_id}/charts/preview`.
3. Backend validates dataset, table, field roles, aggregations, and filters.
4. Aggregate SQL executes against PostgreSQL; rows/meta are returned.
5. User can persist charts with saved-chart APIs.

### E) AI assistant (VizAgent)
1. User asks a question for the selected mart.
2. Frontend calls `POST /api/datasets/{dataset_id}/chat`.
3. Orchestrator:
- Builds compact mart context from profile JSON.
- Loads strategy digest for guidance.
- Tries OpenAI JSON planning.
- If OpenAI unavailable/fails, deterministic fallback chooses clarify/chart/explain/refuse.
4. For chart plans, backend executes chart preview and returns rows + narrative.
5. Chat state and turns are persisted through chat-thread APIs with debounced sync.

### F) Strategy workflow
1. Strategy tab loads decision state, strategy bundle YAML, KPI registry YAML, and editable targets/rules/KPI libraries.
2. Users can update strategy and KPI artifacts with optimistic revision checks.
3. Strategy agent endpoints support extraction, reconciliation, apply, and undo patch workflows.
4. Strategy evaluation and decision-signals endpoints compute readiness and KPI/rule status.

## 4) Backend endpoint inventory

Base prefix: `/api`

### Health
- `GET /`
- `GET /api/health`

### Auth (`/auth`)
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/verify`

### Admin (`/admin`) [requires admin user]
- `GET /admin/organizations`
- `POST /admin/organizations`
- `GET /admin/organizations/{org_id}`
- `PUT /admin/organizations/{org_id}`
- `DELETE /admin/organizations/{org_id}`
- `GET /admin/organizations/{org_id}/datasets`
- `POST /admin/organizations/{org_id}/datasets`
- `DELETE /admin/organizations/{org_id}/datasets/{dataset_id}`
- `GET /admin/users`
- `POST /admin/users`
- `GET /admin/users/{user_id}`
- `PUT /admin/users/{user_id}`
- `DELETE /admin/users/{user_id}`
- `GET /admin/available-datasets`

### Legacy profiling aliases (`/profiling`) [default dataset alias]
- `GET /profiling/aggregations`
- `GET /profiling/aggregations/{table_name}/profile`
- `GET /profiling/aggregations/{table_name}/columns/{column_name}`
- `POST /profiling/chart-data`

### Dataset-scoped APIs (`/datasets/{dataset_id}`)
Profiling:
- `GET /datasets/{dataset_id}/profiling/aggregations`
- `GET /datasets/{dataset_id}/profiling/aggregations/{table_name}/profile`
- `GET /datasets/{dataset_id}/profiling/aggregations/{table_name}/columns/{column_name}`
- `POST /datasets/{dataset_id}/profiling/chart-data`

Query and charts:
- `POST /datasets/{dataset_id}/query/aggregate`
- `POST /datasets/{dataset_id}/charts/preview`

Chat:
- `POST /datasets/{dataset_id}/chat`
- `GET /datasets/{dataset_id}/marts/{table}/chat-hints`

Dataset strategy digest routes:
- `GET /datasets/{dataset_id}/strategy/summary`
- `GET /datasets/{dataset_id}/strategy/context`
- `GET /datasets/{dataset_id}/strategy/targets`
- `GET /datasets/{dataset_id}/strategy/kpis`
- `GET /datasets/{dataset_id}/strategy/rules`
- `GET /datasets/{dataset_id}/strategy/scoring`

### Saved charts (`/saved-charts`)
- `GET /saved-charts`
- `POST /saved-charts`
- `PATCH /saved-charts/{chart_id}`
- `DELETE /saved-charts/{chart_id}`
- `DELETE /saved-charts`

### Chat threads (`/chat-threads`)
- `GET /chat-threads`
- `PUT /chat-threads`
- `DELETE /chat-threads/{thread_key}`
- `DELETE /chat-threads`

### Decision + strategy bundle APIs
Decision:
- `GET /decision/state`

Strategy bundle/editor:
- `GET /strategy/bundle`
- `PUT /strategy/bundle`
- `GET /strategy/overview`
- `PUT /strategy/overview`
- `GET /strategy/targets`
- `POST /strategy/targets`
- `PUT /strategy/targets/{kpi_id}`
- `DELETE /strategy/targets/{kpi_id}`
- `GET /strategy/rules`
- `POST /strategy/rules`
- `PUT /strategy/rules/{rule_id}`
- `DELETE /strategy/rules/{rule_id}`
- `POST /strategy/evaluate`
- `GET /strategy/decision-signals`
- `GET /strategy/kpis`
- `POST /strategy/kpis`
- `PUT /strategy/kpis/{kpi_id}`
- `DELETE /strategy/kpis/{kpi_id}`

Strategy agent:
- `POST /strategy/agent/extract-kpis`
- `POST /strategy/agent/reconcile`
- `POST /strategy/agent/apply`
- `POST /strategy/agent/undo`

KPI registry bundle:
- `GET /kpi-registry/bundle`
- `PUT /kpi-registry/bundle`

### Debug
- `GET /debug/openai` (only when `ENABLE_DEBUG=1`)

## 5) Data assets and datasets

### Synthetic gold datasets in repo (`backend/data`)
- `gold_sales_daily.csv`
- `gold_store_sku_daily.csv`
- `gold_store_360.csv`
- `gold_product_360.csv`
- `gold_customer_360.csv`
- `gold_employee_360.csv`
- `gold_inventory_health_daily.csv`

### Profile artifacts (`backend/out`)
- `gold_*_profile.json` files for each mart above
- Legacy profile leftovers: `mart_customers_profile.json`, `mart_sales_profile.json`, `mart_stores_profile.json`

### Dataset registry reality
- Dataset IDs are validated against `mart_registry`.
- Current supported set in code is effectively one dataset ID: `silkroute`, mapped to the gold marts list.

### Strategy artifacts
Two strategy systems coexist:
1. Task-2 editable strategy config in `backend/strategy_config/*.yaml` and revisions.
2. Dataset-specific strategy resources in `backend/app/resources/strategy/silkroute/*`.

The seeded business narrative and KPI target content are SilkRoute-specific, even though the editing/revision mechanisms are generic.

## 6) Hardcoded vs generalized assessment

## A) Hardcoded / SilkRoute-coupled parts

### Strong hardcoding (code-level)
- `DEFAULT_DATASET_ID = "silkroute"` in `backend/app/core/mart_registry.py`.
- Only one dataset registered in `_DATASET_MARTS` map.
- Legacy profiling aliases always use default dataset.
- Admin available datasets endpoint currently returns only SilkRoute.
- Frontend store defaults `selectedDatasetId` and `activeDataset` to `silkroute`.
- Dashboard dataset card and handler are typed/labeled for SilkRoute only.
- Strategy tab fallback dataset defaults to `silkroute`.
- Admin dataset management pages use hardcoded dataset arrays.

### Seeded content hardcoding (business semantics)
- `backend/strategy_config/strategy_bundle.yaml` references SilkRoute Retail narrative and owners.
- `backend/app/resources/strategy/silkroute/*` contains SilkRoute-oriented SWOT/KPI structures.
- Vendor/docs/scripts often describe SilkRoute and use `--dataset-id silkroute` defaults.

### Potential functional mismatch to note
- `frontend/lib/api.ts` still has a `signup()` method pointing to `/auth/signup`, but backend intentionally removed public signup.
- UI route `/signup` redirects to `/get-access`, so this mismatch is mostly dormant unless someone calls `signup()` directly.

## B) Generalized parts (multi-dataset-ready patterns)

### Backend engines are mostly generic once dataset is registered
- Dataset-scoped endpoints accept `dataset_id` as route/query param.
- Aggregate query engine validates identifiers, filter ops, roles, and types dynamically from profile metadata.
- Chart resolver normalizes and validates ChartSpec against table profile metadata.
- Chat orchestration uses context from selected dataset/table and can operate deterministically without OpenAI.
- Saved charts/chat threads are keyed by user and dataset/thread key, not hardcoded to one dataset.
- Strategy mutation workflows (revisioning, YAML update, conflict handling) are largely generic in mechanism.

### Frontend runtime flow is dataset-parameterized in core workspace
- Workspace route uses `[datasetId]` dynamic segment.
- Most data hooks and API calls accept `datasetId` arguments.
- Query keys include dataset for caching separation.

## C) What works for a new dataset today vs what blocks it

### Would work after registering dataset and profiles
- `/api/datasets/{new_dataset_id}/query/aggregate`
- `/api/datasets/{new_dataset_id}/charts/preview`
- `/api/datasets/{new_dataset_id}/chat`
- Strategy decision-signals/evaluation endpoints with `dataset_id` query/body

### Blocks / friction points today
- New dataset ID is rejected unless added to `mart_registry`.
- Admin available datasets endpoint does not discover datasets dynamically.
- Dashboard and admin pages expose mostly hardcoded dataset choices.
- Legacy profiling endpoints still alias only default SilkRoute dataset.
- Strategy seed content is SilkRoute-specific, so output semantics remain branded unless replaced.

## 7) Auth and access-control observations

### Current auth model
- JWT auth is standard and functional for user routes.
- Admin routes enforce `is_admin` at backend dependency layer.

### Dataset authorization gap
- Organization->dataset assignments exist in DB and admin APIs.
- Runtime dataset endpoints do not currently enforce per-user organization dataset access.
- Effectively, any authenticated user can access any dataset that is registered in `mart_registry`.

This is not a SilkRoute hardcode, but it is an important multi-tenant control gap.

## 8) Recommended de-hardcode plan (practical)

Priority 1 (functional multi-dataset enablement):
1. Expand `mart_registry` to support multiple dataset IDs dynamically (config/table-driven).
2. Make `/admin/available-datasets` dynamic from registry or DB.
3. Replace frontend hardcoded dataset cards/lists with backend-fetched dataset access list.
4. Keep legacy profiling endpoints but clearly mark as deprecated aliases.

Priority 2 (tenant safety):
1. Enforce org dataset assignment in dataset-scoped endpoints.
2. Add a dependency that validates `current_user.organization_id` has access to `dataset_id`.

Priority 3 (content portability):
1. Parameterize strategy seed files per organization/dataset.
2. Split generic strategy templates from SilkRoute sample content.

Priority 4 (cleanup):
1. Remove or guard `apiClient.signup()` since public signup is disabled.
2. Normalize docs/scripts that default silently to SilkRoute.

## 9) Bottom line

- The platform core (query engine, chart resolver, chat orchestration, strategy revision mechanics) is architected with dataset parameters and is largely reusable.
- The current product experience is still strongly seeded around one dataset (`silkroute`) due to registry defaults, admin/frontend hardcoded lists, and business-content defaults.
- The path to full generalization is straightforward and mostly involves registry/dataset-discovery plumbing and access-control enforcement, not a rewrite of analytics engines.
