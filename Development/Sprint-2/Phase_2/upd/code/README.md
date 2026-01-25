# ContinuumAi

A full-stack data analysis webapp for sales backed by AI. Built with Next.js (frontend) and FastAPI (backend) with PostgreSQL via Supabase.

## 🚀 Quick Start

### Prerequisites

- **Node.js** (v18+) — [Download](https://nodejs.org/)
- **Python** (v3.10+) — [Download](https://www.python.org/)
- **PostgreSQL Database** — We use [Supabase](https://supabase.com/) (free tier available)

---

### 1. Clone the Repository

```bash
git clone <repository-url>
cd code
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Configure Backend Environment

Create a `.env` file in the `backend/` directory:

```env
# Supabase PostgreSQL Connection
DATABASE_URL= 
# JWT Configuration
JWT_SECRET_KEY=secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
# CORS
FRONTEND_URL=http://localhost:3000

```

> **Note:** Get your `DATABASE_URL` from Supabase Dashboard → Settings → Database → Connection string (URI)

#### Run Backend

```bash
cd backend
uvicorn app.main:app --reload
```

Backend will be available at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`

---

### 3. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

#### Configure Frontend Environment

Create a `.env.local` file in the `frontend/` directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

#### Run Frontend

```bash
cd frontend
npm run dev
```

Frontend will be available at: `http://localhost:3000`

---

## 📁 Project Structure

```
code/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app entry point, CORS config
│   │   ├── api/
│   │   │   └── auth.py        # Auth endpoints (signup, login, me, verify)
│   │   ├── core/
│   │   │   ├── config.py      # Environment settings (Pydantic Settings)
│   │   │   └── security.py    # JWT tokens, password hashing (bcrypt)
│   │   ├── db/
│   │   │   ├── database.py    # SQLAlchemy engine & session
│   │   │   └── models.py      # User model (SQLAlchemy ORM)
│   │   └── schemas/
│   │       └── user.py        # Pydantic schemas (UserCreate, UserLogin, etc.)
│   ├── requirements.txt       # Python dependencies
│   └── .env                   # Backend environment variables (create this)
│
├── frontend/                   # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx         # Root layout with fonts, AuthProvider
│   │   ├── globals.css        # Global styles, Tailwind imports
│   │   ├── page.tsx           # Landing page (/)
│   │   ├── login/
│   │   │   └── page.tsx       # Login page (/login)
│   │   ├── signup/
│   │   │   └── page.tsx       # Signup page (/signup)
│   │   └── dashboard/
│   │       └── page.tsx       # Dashboard page (/dashboard) - Protected
│   ├── components/
│   │   ├── ElectricBorder.tsx # Animated electric border effect
│   │   ├── Noise.tsx          # Animated noise background
│   │   ├── ProtectedRoute.tsx # Auth guard for protected pages
│   │   ├── TargetCursor.tsx   # Custom animated cursor
│   │   └── TextType.tsx       # Typewriter text animation
│   ├── lib/
│   │   ├── api.ts             # API client for backend communication
│   │   └── auth-context.tsx   # React context for auth state
│   ├── package.json           # Node.js dependencies
│   ├── next.config.ts         # Next.js configuration
│   ├── tailwind.config.ts     # Tailwind CSS configuration
│   ├── tsconfig.json          # TypeScript configuration
│   └── .env.local             # Frontend environment variables (create this)
│
└── README.md                   # This file
```

---

## 🔐 Authentication Flow

1. **Signup** (`POST /api/auth/signup`)
   - Accepts: username, email, password, confirm_password
   - Returns: JWT token + user data
   - Password is hashed with bcrypt

2. **Login** (`POST /api/auth/login`)
   - Accepts: username, password
   - Returns: JWT token + user data

3. **Get Current User** (`GET /api/auth/me`)
   - Requires: Bearer token in Authorization header
   - Returns: Current user data

4. **Verify Token** (`POST /api/auth/verify`)
   - Requires: Bearer token in Authorization header
   - Returns: Token validity status

---

## 🎨 Design System

### Colors
- **Primary Background:** `#060010` (deep purple/black)
- **Accent:** `#5237ff` (vibrant purple)
- **Accent Hover:** `#6347ff` (lighter purple)

### Fonts
- **Heading:** Special Gothic Expanded One (Google Fonts CDN)
- **Body:** Geist Sans
- **Mono:** Geist Mono

### Animations (GSAP)
- `Noise` — Animated grain background
- `TargetCursor` — Custom cursor with parallax effect
- `ElectricBorder` — Animated border around forms
- `TextType` — Typewriter effect for text

---

## 🛠 Tech Stack

### Backend
- **FastAPI** — Modern Python web framework
- **SQLAlchemy** — ORM for database operations
- **Pydantic** — Data validation & settings
- **python-jose** — JWT token handling
- **bcrypt** — Password hashing
- **psycopg2-binary** — PostgreSQL adapter

### Frontend
- **Next.js 15** — React framework with App Router
- **React 19** — UI library
- **TypeScript** — Type safety
- **Tailwind CSS 4** — Utility-first CSS
- **GSAP** — Animation library

### Database
- **PostgreSQL** — Via Supabase

---

## 📝 Development Notes

### Adding New API Endpoints

1. Create route in `backend/app/api/`
2. Add schemas in `backend/app/schemas/`
3. Include router in `backend/app/main.py`
4. Add API client method in `frontend/lib/api.ts`

### Adding New Pages

1. Create folder in `frontend/app/`
2. Add `page.tsx` inside
3. For protected pages, wrap with `ProtectedRoute` component

### Database Migrations

Currently using auto-create tables via SQLAlchemy. For production, consider adding Alembic for proper migrations.

---

## 🐛 Common Issues

### CORS Errors
Make sure backend CORS is configured to allow `http://localhost:3000`

### Database Connection Failed
Check your `DATABASE_URL` in `.env` — ensure Supabase database is accessible

### Token Expired
JWT tokens expire after 30 minutes by default. User needs to log in again.

---

## 📄 License

Private — Internal use only
