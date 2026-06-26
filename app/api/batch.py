"""Batch scrape — async multi-URL processing."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.models.job import Job, JobStatus, JobType
from app.models.schemas import BatchRequest, BatchResponse
from app.services.firecrawl import (
    await_batch,
    batch_scrape,
    batch_status,
    is_configured,
)
from app.services.summarizer import summarize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["batch"])


@router.post("/batch", response_model=BatchResponse)
async def batch_scrape_endpoint(
    payload: BatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Scrape up to 500 URLs at once via Firecrawl /v2/batch/scrape.
    Returns a job_id; poll /api/v1/jobs/{id} for status.
    """
    if not is_configured():
        raise HTTPException(503, "Firecrawl required for /batch")

    urls = [str(u) for u in payload.urls]

    job = Job(
        type=JobType.BATCH,
        url=urls[0] if urls else None,
        options=json.dumps(
            {
                "url_count": len(urls),
                "summarize": payload.summarize,
                "summary_prompt": payload.summary_prompt,
                "formats": payload.formats,
            }
        ),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    async def _run():
        started = time.monotonic()
        try:
            fc_job = await batch_scrape(urls, formats=payload.formats)
            fc_job_id = fc_job.get("id") or (fc_job.get("data") or {}).get("id")
            status = await await_batch(fc_job_id) if fc_job_id else {"data": []}

            pages = status.get("data", []) if isinstance(status.get("data"), list) else []
            summaries = []

            # Optionally summarize each page
            total_tokens = 0
            for page in pages:
                md = page.get("markdown", "")
                if payload.summarize and md:
                    try:
                        s, t = await summarize(md[:8000], payload.summary_prompt, max_tokens=300)
                        summaries.append(s)
                        total_tokens += t
                    except Exception:
                        summaries.append(None)

            # Aggregate all markdown
            combined = "\n\n---\n\n".join(
                f"## {p.get('metadata', {}).get('title', p.get('metadata', {}).get('url', 'page'))}\n\n{p.get('markdown', '')}"
                for p in pages if p.get("markdown")
            )

            duration_ms = int((time.monotonic() - started) * 1000)

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job.id))
                j = result.scalar_one()
                j.status = JobStatus.COMPLETED
                j.completed_at = datetime.now(timezone.utc)
                j.duration_ms = duration_ms
                j.tokens_used = total_tokens or None
                j.title = f"Batch of {len(pages)} pages"
                j.markdown = combined[:80000] if combined else None
                j.extracted_json = json.dumps(
                    {
                        "firecrawl_batch_id": fc_job_id,
                        "page_count": len(pages),
                        "summaries": summaries,
                        "pages": [
                            {
                                "url": p.get("metadata", {}).get("url"),
                                "title": p.get("metadata", {}).get("title"),
                                "markdown_length": len(p.get("markdown", "")),
                                "summary": summaries[i] if i < len(summaries) else None,
                            }
                            for i, p in enumerate(pages[:100])
                        ],
                    }
                )
                await session.commit()
        except Exception as e:
            logger.exception(f"Batch {job.id} failed")
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job.id))
                j = result.scalar_one()
                j.status = JobStatus.FAILED
                j.completed_at = datetime.now(timezone.utc)
                j.error = str(e)[:2000]
                await session.commit()

    background_tasks.add_task(_run)
    return BatchResponse(
        job_id=job.id,
        status="pending",
        url_count=len(urls),
        firecrawl_batch_id=None,
    )