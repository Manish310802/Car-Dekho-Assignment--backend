# CarMatch — Backend (FastAPI)

FastAPI backend for the CarMatch AI car-buying advisor. A deterministic scoring engine ranks ~45 Indian-market cars against a buyer's survey answers; an LLM agent writes the grounded rationale.

## Quick start

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                              # fill in keys (all optional)
uvicorn app.main:app --reload                     # http://localhost:8000
```

API docs at http://localhost:8000/docs.

**No API key and no database required.** Without `OPENAI_API_KEY`/`XAI_API_KEY` the app produces a templated rationale. Without `DATABASE_URL` it uses local SQLite.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | No | Primary LLM provider |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `XAI_API_KEY` | No | Fallback (Grok / xAI) |
| `XAI_MODEL` | No | Default: `grok-2-latest` |
| `DATABASE_URL` | No | Neon Postgres string; falls back to SQLite |
| `CORS_ORIGINS` | Yes (prod) | Comma-separated allowed origins (your Vercel URL) |

## Architecture

```
POST /api/recommend  →  services.py  →  agent.py (LLM + tools)
                                          └→ filter_and_rank_cars → scoring.py
                         repository.py  →  Neon / SQLite
GET  /api/shortlist/:id  ←  repository.py
POST /api/refine         →  agent re-ranks with updated profile
```

Layered and testable: thin routes (`main.py`) → `services.py` → `scoring.py` / `agent.py` / `repository.py`. The scoring engine is pure (no I/O), unit-tested directly.

## Tests & quality

```bash
pytest                # scoring-engine smoke tests
ruff check app        # lint
```

## Deploy on Render

1. Create a [Neon](https://neon.tech) project and copy the `postgresql+psycopg://…` connection string.
2. In Render: **New → Blueprint → this repo**. Set **Root Directory = `backend`** — Render will pick up `render.yaml` from there.
3. Set secret env vars in Render dashboard: `OPENAI_API_KEY`, `XAI_API_KEY`, `DATABASE_URL`, `CORS_ORIGINS` (your Vercel frontend URL).
