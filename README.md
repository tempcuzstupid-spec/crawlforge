---
title: CrawlForge
emoji: 🕷️
colorFrom: purple
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🕷️ CrawlForge

Free AI web crawler — Playwright + Crawl4AI + Browser-Use + Firecrawl + DeepSeek.

## Endpoints

- `GET /` — Dashboard
- `GET /health` — Health check
- `GET /api/v1/info` — Stack info + endpoint list
- `POST /api/v1/crawl` — Crawl a URL
- `POST /api/v1/agent` — Natural-language browser task
- `POST /api/v1/search` — Web search (Firecrawl)
- `POST /api/v1/map` — Discover URLs on a domain (Firecrawl)
- `POST /api/v1/batch` — Batch scrape up to 500 URLs (Firecrawl)
- `POST /api/v1/extract` — LLM-driven structured extraction (Firecrawl)
- `POST /api/v1/crawl-site` — Multi-page crawl
- `POST /api/v1/monitors` — Create URL change monitor
- `GET /api/v1/jobs` — List jobs
- `GET /api/v1/jobs/{id}` — Get job result

## Required Environment Variables (set as Secrets in Space settings)

- `DATABASE_URL` — Neon Postgres asyncpg URL
- `DEEPSEEK_API_KEY` — from platform.deepseek.com
- `FIRECRAWL_API_KEY` — from firecrawl.dev (optional, enables premium backend)