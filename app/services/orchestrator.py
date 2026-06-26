"""Job orchestrator — runs crawl/agent jobs and persists results to Postgres."""

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.job import Job, JobStatus, JobType
from app.services import agent as agent_svc
from app.services import crawler as crawler_svc
from app.services import firecrawl as firecrawl_svc
from app.services import summarizer as summarizer_svc

logger = logging.getLogger(__name__)
settings = get_settings()


async def _update_job(job_id: int, **fields) -> None:
    """Update job fields."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        for k, v in fields.items():
            setattr(job, k, v)
        await session.commit()


async def run_crawl_job(
    job_id: int,
    url: str,
    summarize: bool,
    summary_prompt: str,
    extraction_schema: dict | None = None,
    wait_for_selector: str | None = None,
    screenshot: bool = False,
    backend: str = "auto",
) -> None:
    """Execute a crawl job end-to-end.

    Backend selection:
      - "firecrawl": use Firecrawl API (requires FIRECRAWL_API_KEY)
      - "local": use Playwright + Crawl4AI (free, slower, no anti-bot)
      - "auto": firecrawl if configured + key set, else local (with fallback)
    """
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    backend_used = "local"
    await _update_job(
        job_id, status=JobStatus.RUNNING, started_at=started_at, model_used=settings.deepseek_model
    )

    total_tokens = 0
    try:
        # Resolve effective backend
        use_firecrawl = (
            backend == "firecrawl"
            or (backend == "auto" and settings.firecrawl_default_backend and firecrawl_svc.is_configured())
        )

        result: dict | None = None
        if use_firecrawl:
            try:
                formats = ["markdown"]
                if screenshot:
                    formats.append("screenshot")
                if extraction_schema:
                    formats.append(
                        {
                            "type": "json",
                            "prompt": "Extract structured data from this page",
                            "schema": extraction_schema,
                        }
                    )
                fc_result = await firecrawl_svc.scrape(
                    url, formats=formats, only_main_content=True
                )
                result = {
                    "title": fc_result.get("title"),
                    "markdown": fc_result.get("markdown"),
                    "extracted_json": fc_result.get("json"),
                    "screenshot_path": None,  # Firecrawl screenshots are URLs, not paths
                }
                backend_used = "firecrawl"
                logger.info(f"Job {job_id}: scraped via Firecrawl ({fc_result.get('credits_used', 0)} credits)")
            except Exception as e:
                logger.warning(f"Firecrawl failed, falling back to local: {e}")
                if backend == "firecrawl":
                    raise  # explicit choice, don't fall back
                result = None  # force local fallback

        if result is None:
            # Local Playwright + Crawl4AI
            result = await crawler_svc.crawl_url(
                url,
                wait_for_selector=wait_for_selector,
                screenshot=screenshot,
                extraction_schema=extraction_schema,
            )
            backend_used = "local"

        extracted_json = result.get("extracted_json")
        markdown = result.get("markdown") or ""
        title = result.get("title")
        tokens_used = 0

        if summarize and markdown:
            try:
                summary, tokens_used = await summarizer_svc.summarize(
                    markdown, summary_prompt
                )
                total_tokens += tokens_used
            except Exception as e:
                logger.warning(f"Summarization failed: {e}")
                summary = f"(summarization failed: {e})"

        duration_ms = int((time.monotonic() - started) * 1000)
        completed_at = datetime.now(timezone.utc)

        await _update_job(
            job_id,
            status=JobStatus.COMPLETED,
            completed_at=completed_at,
            duration_ms=duration_ms,
            tokens_used=total_tokens or None,
            title=title,
            markdown=markdown,
            extracted_json=json.dumps(extracted_json) if extracted_json else None,
            summary=summary if summarize else None,
        )
        logger.info(f"Job {job_id} completed in {duration_ms}ms via {backend_used}")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        duration_ms = int((time.monotonic() - started) * 1000)
        await _update_job(
            job_id,
            status=JobStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error=str(e)[:2000],
        )


async def run_agent_job(
    job_id: int,
    task: str,
    start_url: str | None = None,
    max_steps: int = 15,
) -> None:
    """Execute an agent job end-to-end."""
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    await _update_job(
        job_id, status=JobStatus.RUNNING, started_at=started_at, model_used=settings.deepseek_model
    )

    try:
        result = await agent_svc.run_agent_task(
            task, start_url=start_url, max_steps=max_steps
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        completed_at = datetime.now(timezone.utc)

        await _update_job(
            job_id,
            status=JobStatus.COMPLETED,
            completed_at=completed_at,
            duration_ms=duration_ms,
            tokens_used=result.get("tokens_used"),
            agent_result=result.get("final_result"),
            extracted_json=json.dumps(
                {"steps_taken": result.get("steps_taken"), "history": result.get("history", [])}
            ),
        )
        logger.info(f"Agent job {job_id} completed in {duration_ms}ms")

    except Exception as e:
        logger.exception(f"Agent job {job_id} failed")
        duration_ms = int((time.monotonic() - started) * 1000)
        await _update_job(
            job_id,
            status=JobStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error=str(e)[:2000],
        )