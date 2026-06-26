"""CrawlForge FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import agent as agent_api
from app.api import batch as batch_api
from app.api import crawl as crawl_api
from app.api import extract as extract_api
from app.api import jobs as jobs_api
from app.api import map as map_api
from app.api import monitors as monitors_api
from app.api import pages as pages_api
from app.api import search as search_api
from app.core.config import get_settings
from app.services import proxy as proxy_svc
from app.services.firecrawl import is_configured as firecrawl_configured
from app.core.database import init_db

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🕷️  CrawlForge v{__version__} starting up...")
    proxy_svc.init()
    try:
        await init_db()
        logger.info("✅ Database tables ready")
    except Exception as e:
        logger.warning(f"⚠️  Database init failed: {e}. Will retry on first request.")
    yield
    logger.info("👋 CrawlForge shutting down")


app = FastAPI(
    title="CrawlForge",
    description="Free, open-source AI web crawler — Playwright + Crawl4AI + Browser-Use + DeepSeek",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Static + templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routers
app.include_router(crawl_api.router)
app.include_router(agent_api.router)
app.include_router(jobs_api.router)
app.include_router(search_api.router)
app.include_router(map_api.router)
app.include_router(batch_api.router)
app.include_router(extract_api.router)
app.include_router(monitors_api.router)

# HTML pages
app.include_router(pages_api.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "env": settings.app_env,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "firecrawl_configured": firecrawl_configured(),
        "stealth_mode": settings.stealth_mode,
        "proxy_rotation": settings.proxy_rotation and proxy_svc.has_proxies(),
    }


@app.get("/api/v1/info")
async def info():
    return {
        "name": "CrawlForge",
        "version": __version__,
        "stack": {
            "browser": "Playwright",
            "extraction": "Crawl4AI",
            "agent": "Browser-Use",
            "llm": settings.deepseek_model,
            "db": "Neon Postgres",
            "premium_backend": "Firecrawl" if firecrawl_configured() else None,
            "stealth": settings.stealth_mode,
            "proxy_rotation": settings.proxy_rotation,
        },
        "endpoints": {
            "POST /api/v1/crawl": "Single URL → clean Markdown + AI summary (auto/local/firecrawl)",
            "POST /api/v1/agent": "Natural-language browser task (Browser-Use + DeepSeek)",
            "POST /api/v1/search": "Web search (requires Firecrawl)",
            "POST /api/v1/map": "Discover all URLs on a domain (sitemap + crawl, requires Firecrawl)",
            "POST /api/v1/crawl-site": "Multi-page crawl + per-page summaries (requires Firecrawl)",
            "POST /api/v1/batch": "Batch scrape up to 500 URLs async (requires Firecrawl)",
            "POST /api/v1/extract": "LLM-driven structured extraction across URLs (requires Firecrawl)",
            "POST /api/v1/monitors": "Create URL change monitor",
            "POST /api/v1/monitors/run-due": "Run all due monitors (call from cron)",
            "GET /api/v1/jobs": "List recent jobs (all types)",
            "GET /api/v1/jobs/{id}": "Get specific job",
            "DELETE /api/v1/jobs/{id}": "Delete job",
        },
    }