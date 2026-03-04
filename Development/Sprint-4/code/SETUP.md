# Sprint-4 Setup

## Codebase copy

Sprint-4 was initialized by copying:

- `Development/Sprint-3/code` -> `Development/Sprint-4/code`

## Backend setup (`Development/Sprint-4/code/backend`)

1. Create `backend/.env` from `backend/.env.example`.
2. Set required values:
   - `OPENAI_API_KEY`
   - `DATABASE_URL`
   - `JWT_SECRET_KEY`
3. Install and run:

```bash
cd Development/Sprint-4/code/backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Frontend setup (`Development/Sprint-4/code/frontend`)

1. Create `frontend/.env` from `frontend/.env.example`.
2. Set required values:
   - `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000/api`)
3. Install and run:

```bash
cd Development/Sprint-4/code/frontend
npm install
npm run dev
```

## Required environment variables

- Backend: `OPENAI_API_KEY`, `DATABASE_URL`
- Frontend: `NEXT_PUBLIC_API_URL`

## Troubleshooting OpenAI Fallback

If the chat banner says OpenAI failed, check backend logs for `correlation_id` and OpenAI diagnostics.

- `401` or `403` (`authentication_error`): check `OPENAI_API_KEY` value and key permissions.
- `429` (`rate_limit`): wait, reduce request rate, or use a higher quota tier.
- `404` (`not_found`): verify the configured model name.
- `network` / `timeout`: check proxy, firewall, VPN, and outbound connectivity.

When `ENABLE_DEBUG=1`, you can also check:

- `GET /api/debug/openai`
- Response: `{ "openai_configured": bool, "vizagent_model": string|null }`
