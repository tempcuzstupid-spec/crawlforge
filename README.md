# 🕷️ CrawlForge

**Free, open-source AI web crawler** — Playwright browser + Crawl4AI extraction + Browser-Use agent + DeepSeek summarization, all wired to Neon Postgres and one-click deployed to Render.

## ✨ Features

- 🔍 **Single-URL crawl** — give it a URL, get clean Markdown + structured JSON
- 🤖 **AI agent mode** — describe a task in natural language, Browser-Use + DeepSeek drives the browser
- 📝 **AI summarization** — DeepSeek summarizes crawled content with custom prompts
- 💾 **Neon Postgres storage** — every job, every result, every summary persisted
- 🎨 **Web dashboard** — simple UI to trigger crawls, view history, download results
- 🚀 **One-click deploy to Render** — Dockerfile + render.yaml included
- 🔄 **GitHub Actions auto-deploy** — push to main, Render redeploys
- 💰 **100% free** — Render free tier + Neon free tier + DeepSeek ~$0.14/1M tokens

## 🏗️ Stack

| Layer | Tool |
|-------|------|
| Browser | Playwright (Chromium headless-shell) |
| Extraction | Crawl4AI |
| Agent | Browser-Use |
| LLM | DeepSeek (via OpenAI-compatible API) |
| API | FastAPI + uvicorn |
| DB | Neon Postgres (asyncpg + SQLAlchemy) |
| Templates | Jinja2 |
| Deploy | Render + Docker |

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/<your-user>/crawlforge.git
cd crawlforge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 2. Configure

```bash
cp .env.example .env
# Fill in: DEEPSEEK_API_KEY, DATABASE_URL (Neon)
```

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000

### 4. Deploy to Render

1. Push to GitHub
2. Connect repo at render.com
3. Render auto-detects `render.yaml` and deploys
4. Set `DEEPSEEK_API_KEY` and `DATABASE_URL` in Render dashboard

## 📡 API

### `POST /api/v1/crawl`
Crawl a single URL, extract clean Markdown, optionally summarize.

```json
{
  "url": "https://example.com/article",
  "summarize": true,
  "summary_prompt": "Extract the 3 key takeaways"
}
```

### `POST /api/v1/agent`
Run a natural-language browser task.

```json
{
  "task": "Go to github.com/microsoft/playwright and find the latest release version",
  "max_steps": 15
}
```

### `GET /api/v1/jobs/{job_id}`
Get job status + result.

### `GET /api/v1/jobs`
List recent jobs.

## 💸 Cost breakdown

| Component | Cost |
|-----------|------|
| Render web service | $0 (750 hrs/mo free) |
| Render disk | $0 (ephemeral) |
| Neon Postgres | $0 (0.5GB free, no expiry) |
| DeepSeek API | ~$0.14 per 1M tokens (cents/mo for personal use) |
| GitHub | $0 (public/private repos) |
| **Total** | **~$0-1/mo** |

## 📄 License

MIT