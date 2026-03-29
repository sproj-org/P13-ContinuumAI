# ContinuumAI (Sprint 4)

Single source of truth for local setup and run instructions for the Sprint 4 codebase.

## What Is In This Folder

- `backend/`: FastAPI backend with JWT auth, admin/org management, strategy services, dashboards, and chat APIs.
- `frontend/`: Next.js frontend application.

## Prerequisites

- Node.js 18+
- npm
- Python 3.10+
- PostgreSQL connection string (Supabase or any compatible Postgres)

## Quick Start

Run backend and frontend in separate terminals.

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
```

Activate virtual environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS/Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create backend env file from template:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# macOS/Linux
cp .env.example .env
```

Update `backend/.env` values.

Required for startup:

- `DATABASE_URL`
- `JWT_SECRET_KEY`

Recommended defaults (already present in `.env.example`):

- `HOST=0.0.0.0`
- `PORT=8000`
- `FRONTEND_URL=http://localhost:3000`
- `ENABLE_DEBUG=0`

LLM-related values:

- `OPENAI_API_KEY` for AI-backed features.
- Model can be set with either `VIZAGENT_MODEL` or `OPENAI_MODEL`.
  The backend resolves both to one model setting.

Run backend:

```bash
uvicorn app.main:app --reload
```

Backend URLs:

- API base: `http://localhost:8000/api`
- Swagger docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

### 2. Frontend Setup

```bash
cd frontend
npm install
```

Create frontend env file from template:

```powershell
# Windows PowerShell
Copy-Item .env.example .env.local
```

```bash
# macOS/Linux
cp .env.example .env.local
```

Set frontend env values:

- `NEXT_PUBLIC_API_URL=http://localhost:8000/api`
- `NEXT_PUBLIC_ENABLE_DEBUG=0` (optional)

Run frontend:

```bash
npm run dev
```

Frontend URL:

- `http://localhost:3000`

## Environment Variables Reference

### Backend (`backend/.env`)

Core:

- `ENV`
- `HOST`
- `PORT`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `FRONTEND_URL`
- `CORS_ORIGINS`
- `ENABLE_DEBUG`

LLM:

- `OPENAI_API_KEY`
- `VIZAGENT_MODEL`
- `OPENAI_MODEL`

Minimal alerts (optional feature set):

- `ALERTS_ENABLED`
- `ALERT_STATE_FILE`
- `ALERT_MONITOR_LOG`
- `ALERT_DEFAULT_DATASET_ID`
- `ALERT_EVENT_SOURCE`
- `ALERT_EMAIL_TO`
- `ALERT_EMAIL_FROM`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`

### Frontend (`frontend/.env.local`)

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ENABLE_DEBUG`

## Auth and Access Model (Current)

- Public signup is removed.
- Users are created and managed by admins.
- Admin APIs are under `/api/admin/*`.
- Standard user auth endpoints remain under `/api/auth/*` (login, token verification, current user).

## OpenAI Fallback Troubleshooting

If the app shows OpenAI fallback behavior:

1. Check backend logs for `correlation_id` and diagnostic information.
2. Validate `OPENAI_API_KEY` and selected model.

Common API status mappings:

- `401` or `403`: invalid or unauthorized API key.
- `429`: rate limited.
- `404`: model name is invalid or unavailable.
- `timeout` or network errors: local network/proxy/firewall/VPN issue.

If `ENABLE_DEBUG=1`, debug endpoint is available:

- `GET /api/debug/openai`

Example response fields:

- `openai_configured`
- `openai_model`
- `vizagent_model`
- `key_fingerprint`

## Notes

- Backend reads environment from `backend/.env`.
- Frontend normalizes API base URLs and supports values with or without trailing `/api`.
- This file replaces previous split setup docs.

## License

Private - Internal use only
