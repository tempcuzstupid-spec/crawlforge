"""Firecrawl-powered endpoints: search + multi-page crawl."""

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.models.job import Job, JobStatus, JobType
from app.models.schemas import SearchRequest, SearchResponse
from app.services.firecrawl import (
    await_crawl,
    get_crawl_status,
    is_configured,
    search,
    start_crawl,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["firecrawl"])


class CrawlSiteRequest(BaseModel):
    url: str = Field(..., min_length=4)
    limit: int = Field(default=10, ge=1, le=100)
    wait: bool = True


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(payload: SearchRequest):
    """
    Search the web via Firecrawl.
    Requires FIRECRAWL_API_KEY. Returns web results.
    """
    if not is_configured():
        raise HTTPException(
            503,
            "Firecrawl not configured. Set FIRECRAWL_API_KEY to use search.",
        )
    try:
        data = await search(payload.query, limit=payload.limit, sources=payload.sources)
    except Exception as e:
        raise HTTPException(502, f"Search failed: {e}") from e

    # Flatten sources into a single result list
    results = []
    for source, items in data.items():
        if isinstance(items, list):
            for item in items:
                item["_source"] = source
                results.append(item)
    return SearchResponse(query=payload.query, results=results, total=len(results))


@router.post("/crawl-site")
async def crawl_site(
    payload: CrawlSiteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Multi-URL crawl via Firecrawl. If wait=true, blocks until done.
    Otherwise returns the job ID to poll via /api/v1/jobs/{id}.
    """
    if not is_configured():
        raise HTTPException(503, "Firecrawl not configured")

    job = Job(
        type=JobType.CRAWL,
        url=payload.url,
        options=json.dumps({"limit": payload.limit, "multi_page": True, "wait": payload.wait}),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    async def _run():
        started = time.monotonic()
        try:
            fc_job_id = await start_crawl(payload.url, limit=payload.limit)
            if payload.wait:
                status = await await_crawl(fc_job_id)
            else:
                status = await get_crawl_status(fc_job_id)
            duration_ms = int((time.monotonic() - started) * 1000)

            pages = status.get("data", []) if isinstance(status.get("data"), list) else []
            markdown = "\n\n---\n\n".join(
                p.get("markdown", "") for p in pages if p.get("markdown")
            )

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job.id))
                j = result.scalar_one()
                j.status = (
                    JobStatus.COMPLETED
                    if status.get("status") == "completed"
                    else JobStatus.FAILED
                )
                j.completed_at = datetime.now(timezone.utc)
                j.duration_ms = duration_ms
                j.markdown = markdown[:50000] if markdown else None
                j.title = f"Crawled {len(pages)} pages from {payload.url}"
                j.extracted_json = json.dumps(
                    {
                        "page_count": len(pages),
                        "firecrawl_job_id": fc_job_id,
                        "pages": [
                            {
                                "url": p.get("metadata", {}).get("url"),
                                "title": p.get("metadata", {}).get("title"),
                            }
                            for p in pages[:50]
                        ],
                    }
                )
                await session.commit()
        except Exception as e:
            logger.exception(f"Multi-page crawl {job.id} failed")
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job.id))
                j = result.scalar_one()
                j.status = JobStatus.FAILED
                j.completed_at = datetime.now(timezone.utc)
                j.error = str(e)[:2000]
                await session.commit()

    background_tasks.add_task(_run)
    return {
        "job_id": job.id,
        "status": "pending",
        "url": payload.url,
        "limit": payload.limit,
    }