"""Extract endpoint — LLM-driven structured data extraction across URLs."""

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.models.job import Job, JobStatus, JobType
from app.models.schemas import ExtractRequest, ExtractResponse
from app.services.firecrawl import (
    await_extract,
    extract as fc_extract,
    extract_status,
    is_configured,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["extract"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_endpoint(
    payload: ExtractRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    LLM-driven structured extraction from 1+ URLs.

    Give it a natural-language prompt ("extract product names and prices") and
    optionally a JSON schema. Firecrawl handles the LLM call + scraping across
    all URLs in parallel.

    Combine with /map to discover URLs first, then extract from them all.
    """
    if not is_configured():
        raise HTTPException(503, "Firecrawl required for /extract")

    urls = [str(u) for u in payload.urls]

    job = Job(
        type=JobType.EXTRACT,
        url=urls[0] if urls else None,
        options=json.dumps(
            {
                "url_count": len(urls),
                "prompt": payload.prompt,
                "schema": payload.schema_,
                "allow_external_links": payload.allow_external_links,
                "enable_web_search": payload.enable_web_search,
            }
        ),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    async def _run():
        started = time.monotonic()
        try:
            fc_resp = await fc_extract(
                urls,
                prompt=payload.prompt,
                schema=payload.schema_,
                allow_external_links=payload.allow_external_links,
                enable_web_search=payload.enable_web_search,
            )
            fc_job_id = fc_resp.get("id") or (fc_resp.get("data") or {}).get("id")

            if fc_job_id:
                final = await await_extract(fc_job_id)
            else:
                final = fc_resp

            duration_ms = int((time.monotonic() - started) * 1000)

            # Result data lives under data.data or data.json or data
            data = final.get("data", {}) or {}
            result_json = data.get("data") or data.get("json") or data.get("result") or final

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job.id))
                j = result.scalar_one()
                j.status = JobStatus.COMPLETED if final.get("status") in (None, "completed") else JobStatus.FAILED
                j.completed_at = datetime.now(timezone.utc)
                j.duration_ms = duration_ms
                j.title = f"Extract: {payload.prompt[:80]}"
                j.extracted_json = json.dumps(
                    {
                        "firecrawl_job_id": fc_job_id,
                        "prompt": payload.prompt,
                        "result": result_json,
                    }
                )[:200000]
                await session.commit()
        except Exception as e:
            logger.exception(f"Extract {job.id} failed")
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job.id))
                j = result.scalar_one()
                j.status = JobStatus.FAILED
                j.completed_at = datetime.now(timezone.utc)
                j.error = str(e)[:2000]
                await session.commit()

    background_tasks.add_task(_run)
    return ExtractResponse(
        job_id=job.id,
        status="pending",
        firecrawl_job_id=None,
    )