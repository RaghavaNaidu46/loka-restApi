# Loka FastAPI Backend

Verified Civic Participation Platform — Backend API

## Stack
- **FastAPI** (async)
- **PostgreSQL 16** — primary datastore with full-text search via `tsvector`
- **Redis 7** — OTP storage + JWT blacklisting
- **SQLAlchemy 2.0** (async) + asyncpg
- **Alembic** — database migrations

## Quick Start (Docker)

```bash
# 1. Start PostgreSQL + Redis
docker-compose up postgres redis -d

# 2. Install dependencies
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 3. Run database migrations (auto-runs on startup too)
# Tables are auto-created on first launch via SQLAlchemy

# 4. Seed districts
python -m scripts.seed_districts

# 5. Start dev server
uvicorn app.main:app --reload --port 8000
```

The API will be live at: http://localhost:8000  
Swagger docs: http://localhost:8000/docs

## API Modules

| Module | Prefix | Description |
|---|---|---|
| Auth | `/auth` | OTP send/verify, JWT refresh, logout |
| Verification | `/verification` | Aadhaar Offline XML upload |
| Issues | `/issues` | Create, edit (draft), submit, view |
| Feed | `/feed` | Nearby, New, Priority, Resolved feeds |
| Participation | `/issues/{id}/support\|oppose` | Immutable civic participation |
| Comments | `/issues/{id}/comments` | Issue comments |
| Profile | `/profile` | Self + public profiles, history |
| Search | `/search` | Full-text + filter issue search |
| Notifications | `/notifications` | Citizen notification inbox |
| Moderation | `/moderation` | Approve, reject, merge, clarify |

## Environment Variables

Copy `.env.example` to `.env` and adjust values. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `MOCK_OTP` | `true` | Skip SMS; OTP is always `123456` |
| `MOCK_VERIFICATION` | `true` | Accept any Aadhaar XML upload |
| `SECRET_KEY` | — | **Change before production** |
| `DATABASE_URL` | — | PostgreSQL async connection string |

## Auth Flow

```
POST /auth/send-otp  { phoneNumber }
→ OTP stored in Redis (TTL: 5 min)

POST /auth/verify-otp  { phoneNumber, otp }
→ { accessToken, refreshToken }

POST /auth/refresh  { refreshToken }
→ { accessToken, refreshToken }  (old refresh token blacklisted)

POST /auth/logout  { refreshToken }
→ Refresh token blacklisted
```
