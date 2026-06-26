"""Crawl endpoint — POST /api/v1/crawl."""

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.job import Job, JobType
from app.models.schemas import CrawlRequest, CrawlResponse
from app.services.orchestrator import run_crawl_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["crawl"])


@router.post("/crawl", response_model=CrawlResponse)
async def crawl(
    payload: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Crawl a single URL.

    - Extracts clean Markdown (via Firecrawl if configured, else Crawl4AI + Playwright)
    - Optionally extracts structured JSON (if extraction_schema provided)
    - Optionally summarizes via DeepSeek

    Set `backend`: "auto" (default), "local", or "firecrawl".
    """
    job = Job(
        type=JobType.CRAWL,
        url=str(payload.url),
        options=json.dumps(
            {
                "summarize": payload.summarize,
                "summary_prompt": payload.summary_prompt,
                "extract_schema": payload.extract_schema,
                "wait_for_selector": payload.wait_for_selector,
                "screenshot": payload.screenshot,
                "backend": payload.backend,
            }
        ),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        run_crawl_job,
        job.id,
        str(payload.url),
        payload.summarize,
        payload.summary_prompt,
        payload.extract_schema,
        payload.wait_for_selector,
        payload.screenshot,
        payload.backend,
    )

    return CrawlResponse(
        job_id=job.id,
        status="pending",
        url=str(payload.url),
        backend=payload.backend,
    )