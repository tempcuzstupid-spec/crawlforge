# Architecture

## High-level flow

```
┌──────────────────────────────────────────────────────────────┐
│                       Client / Dashboard                      │
│                  (browser, curl, API client)                  │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼───────────────────────────────┐
│                    FastAPI App (Render)                       │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ /crawl   │  │ /agent   │  │ /jobs    │  │ / (UI)   │    │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └──────────┘    │
│        │              │             │                          │
│        │              │             │  read                   │
└────────┼──────────────┼─────────────┼──────────────────────────┘
         │              │             │
         │ enqueue      │ enqueue     │
         ▼              ▼             ▼
   ┌─────────────────────────────────────────┐
   │            Background Tasks             │
   │  ┌────────────────┐ ┌────────────────┐  │
   │  │ run_crawl_job  │ │ run_agent_job  │  │
   │  └────────┬───────┘ └────────┬───────┘  │
   └───────────┼──────────────────┼──────────┘
               │                  │
       ┌───────▼────────┐ ┌───────▼────────┐
       │   Crawl4AI     │ │  Browser-Use   │
       │ + Playwright   │ │ + Playwright   │
       └───────┬────────┘ └───────┬────────┘
               │                  │
               └────────┬─────────┘
                        │ clean text / result
                        ▼
                ┌───────────────────┐
                │  DeepSeek API     │ ← summarization
                │  (OpenAI-compat)  │
                └─────────┬─────────┘
                          │ summary
                          ▼
                ┌───────────────────┐
                │  Neon Postgres    │
                │  (jobs table)     │
                └───────────────────┘
```

## Component responsibilities

| Component | Responsibility |
|-----------|----------------|
| **FastAPI** | HTTP routing, request validation, background task scheduling |
| **Crawl4AI** | Single-URL → clean Markdown (heuristic), optional LLM extraction |
| **Browser-Use** | Multi-step natural-language → browser actions |
| **Playwright** | Headless Chromium driver for both Crawl4AI and Browser-Use |
| **DeepSeek** | LLM for summarization + Browser-Use agent decisions |
| **Neon Postgres** | Persist all jobs, results, summaries |
| **Jinja2 templates** | Server-rendered dashboard UI |
| **Docker** | Reproducible build, Chromium bundled |
| **Render** | Hosting (free web service tier) |
| **GitHub Actions** | CI test + manual Render deploy trigger |

## Why these choices

- **FastAPI over Flask**: async-native, great for background tasks, auto OpenAPI docs
- **SQLAlchemy 2.0 async**: modern async ORM, no Alembic needed for v1 (just `create_all`)
- **Jinja2 over React**: zero build step, works on free Render tier with no Node
- **BackgroundTasks over Celery**: simpler, no Redis/worker needed, fits free tier
- **DeepSeek over OpenAI**: 100x cheaper, near-GPT-4 quality, OpenAI-compatible API
- **Neon over Render Postgres**: no 90-day expiry, generous free tier, modern pg 16
- **Playwright headless-shell over full Chromium**: smaller image, faster cold start

## Scaling considerations (future)

- Background tasks run in-process — fine for ~10 concurrent jobs on free tier
- For higher scale: move to Celery + Redis, add rate limiting, use Playwright pool
- Free tier constraints: 512MB RAM (Playwright is heavy), 750h/mo (≈31 days continuous)
- Database: Neon free tier = 0.5GB storage, 190 compute hrs/mo

## Security notes

- No auth on v1 — assumes private deployment
- Add API key auth before exposing publicly
- Set `SECRET_KEY` to a real random value in production
- Neon requires SSL — handled by `?ssl=require`
- Playwright runs headless with sandbox — safe for untrusted URLs but consider rate limits