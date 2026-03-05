# Sprint-4 Setup

## Backend (`Development/Sprint-4/code/backend`)

1. Create `backend/.env` from `backend/.env.example`.
2. Set required values:
   - `OPENAI_API_KEY`
   - `DATABASE_URL`
   - `JWT_SECRET_KEY`
   - Optional model override: `VIZAGENT_MODEL` (or keep `OPENAI_MODEL`)
3. Run:

```bash
cd Development/Sprint-4/code/backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Frontend (`Development/Sprint-4/code/frontend`)

1. Create `frontend/.env.local` (or `frontend/.env`) using `frontend/.env.example`.
2. Set:
   - `NEXT_PUBLIC_API_URL=http://localhost:8000/api`
3. Run:

```bash
cd Development/Sprint-4/code/frontend
npm install
npm run dev
```
