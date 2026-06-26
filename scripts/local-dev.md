# Local Development

## Prerequisites

- Python 3.11+
- Git
- ~2GB disk for Chromium

## Setup

```bash
git clone <your-repo-url>
cd crawlforge

# Virtual env
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Dependencies
pip install -r requirements.txt
playwright install --with-deps chromium

# Env
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY and DATABASE_URL

# Run
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000

## Useful commands

```bash
# API docs
open http://localhost:8000/docs

# Test crawl
curl -X POST http://localhost:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "summarize": true}'

# Test agent
curl -X POST http://localhost:8000/api/v1/agent \
  -H "Content-Type: application/json" \
  -d '{"task": "Go to example.com and tell me what it says", "max_steps": 10}'

# List jobs
curl http://localhost:8000/api/v1/jobs
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `playwright install` fails | `playwright install chromium` without `--with-deps`, then install deps manually |
| `asyncpg` won't install | Need `libpq-dev` system package |
| Database connection refused | Check `DATABASE_URL`, make sure Neon project isn't paused |
| DeepSeek 401 | Wrong API key, regenerate at platform.deepseek.com |
| Agent runs but no result | Increase `max_steps`, check DeepSeek credit balance |