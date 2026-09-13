# Deploying VoyageMind

The system is three deployable pieces plus managed infrastructure:

| Piece | What it is | Recommended host |
|---|---|---|
| `frontend/` | Next.js 16 app (static + a couple of dynamic pages) | **Vercel** (made for Next.js) |
| `backend/` | FastAPI + SQLAlchemy, long-running Python process | **Render** / Railway / Fly.io (a Web Service, not serverless) |
| `travel-mcp-server/` | FastAPI/MCP gateway, long-running Python process | **Render** / Railway / Fly.io (second Web Service) |
| PostgreSQL | persistent data | **Neon** / Supabase / Render Postgres |
| Redis | cache only (optional — degrades gracefully) | **Upstash** / Render Redis |

> Why not Vercel for the Python services? The backend and MCP gateway are
> long-running stateful-ish processes (DB pools, in-memory rate limiting,
> MCP sessions). Vercel serverless functions would cold-start them on every
> request. Vercel is perfect for the frontend; use Render/Railway/Fly for the
> two Python services.

## Step 0 — provision infrastructure

1. Create a Postgres database (Neon has a free tier). Copy its connection
   string, e.g. `postgresql+psycopg://user:pass@host/db`.
2. Create a Redis instance (Upstash free tier). Copy the URL, e.g.
   `redis://default:pass@host:6379`. *(Optional — the app works without it.)*

## Step 1 — deploy the Travel MCP gateway (Render example)

1. Render → New → Web Service → connect your GitHub repo.
2. Root directory: `travel-mcp-server`, Runtime: Docker (uses its Dockerfile).
3. Environment variables:

   | Key | Value |
   |---|---|
   | `DUFFEL_API_KEY` | your Duffel test key (optional; demo flights until set) |
   | `TAVILY_API_KEY` | your Tavily key (optional; search says "no_provider" until set) |
   | `TRAVEL_MCP_DEMO_MODE` | leave unset in production (set `1` only for demos) |

4. Note the public URL, e.g. `https://voyagemind-mcp.onrender.com`.

## Step 2 — deploy the backend (Render example)

1. Render → New → Web Service → same repo.
2. Root directory: `backend`, Runtime: Docker (Dockerfile runs
   `alembic upgrade head` then uvicorn).
3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your Neon/Supabase URL (`postgresql+psycopg://...`) |
   | `REDIS_URL` | your Upstash URL (optional) |
   | `JWT_SECRET` | **a long random string** (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
   | `ENVIRONMENT` | `production` |
   | `DEBUG` | `false` |
   | `LLM_PROVIDER` | `gemini` |
   | `GEMINI_API_KEY` | your Google AI Studio key (enables Modes A/C + Copilot) |
   | `TRAVEL_MCP_URL` | the MCP gateway URL from step 1 |
   | `CORS_ORIGINS` | `["https://your-frontend.vercel.app"]` |

## Step 3 — deploy the frontend (Vercel)

1. Vercel → Add New Project → import the repo.
2. Root directory: `frontend` (Vercel auto-detects Next.js).
3. Environment variables:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the backend URL from step 2, e.g. `https://voyagemind-api.onrender.com` |

   This is the **only** frontend variable and it is public by design — no keys
   ever ship to the browser.

## Alternative: single VPS with Docker

```bash
cp .env.example .env    # edit: real JWT_SECRET, DATABASE_URL, CORS_ORIGINS, GEMINI_API_KEY
docker compose up --build -d
```

Put nginx/Caddy in front for TLS. This runs everything (Postgres, Redis,
backend, gateway, frontend) on one machine — simplest full-stack demo host.

## Pre-flight checklist

- [ ] `JWT_SECRET` is a unique 32+ character value (backend logs shout if not)
- [ ] `DEBUG=false`, `ENVIRONMENT=production` on the backend
- [ ] `CORS_ORIGINS` lists only your frontend URL(s)
- [ ] `TRAVEL_MCP_DEMO_MODE` is **unset** on the gateway (or data will be labeled demo)
- [ ] `GEMINI_API_KEY` set if you want Modes A/C and the Copilot
- [ ] Health checks pass: `GET /health` on backend and gateway
- [ ] First backend deploy runs `alembic upgrade head` (its Dockerfile does automatically)

## Cost picture (prototype)

| Thing | Free tier? |
|---|---|
| Vercel (frontend) | yes |
| Render web services | free tier sleeps after idle (cold starts); paid ~$7/mo/service for always-on |
| Neon Postgres / Upstash Redis | yes |
| Gemini API | generous free tier |
| Open-Meteo / OSRM / Nominatim / Overpass | free, no key |
| Duffel | free test mode |
