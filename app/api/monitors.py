"""Monitor endpoints — track URL changes over time."""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.models.job import Job, JobStatus, JobType
from app.models.monitor import Monitor, MonitorStatus
from app.models.schemas import (
    MonitorCheckResponse,
    MonitorCreate,
    MonitorInfo,
)
from app.services.firecrawl import is_configured, scrape
from app.services.summarizer import summarize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["monitors"])


@router.post("/monitors", response_model=MonitorInfo)
async def create_monitor(payload: MonitorCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a recurring monitor for a URL.

    Runs an immediate check, then re-checks every `interval_seconds`.
    On content change, persists a diff job and an AI summary of what changed.
    """
    if not is_configured():
        raise HTTPException(503, "Firecrawl required for monitors (for reliable content + JS render)")

    monitor = Monitor(
        url=str(payload.url),
        name=payload.name,
        interval_seconds=payload.interval_seconds,
        summarize_changes=payload.summarize_changes,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return MonitorInfo.model_validate(monitor)


@router.get("/monitors", response_model=list[MonitorInfo])
async def list_monitors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Monitor).order_by(Monitor.created_at.desc()))
    return [MonitorInfo.model_validate(m) for m in result.scalars().all()]


@router.get("/monitors/{monitor_id}", response_model=MonitorInfo)
async def get_monitor(monitor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Monitor not found")
    return MonitorInfo.model_validate(m)


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Monitor not found")
    await db.delete(m)
    await db.commit()
    return {"deleted": monitor_id}


@router.post("/monitors/{monitor_id}/check", response_model=MonitorCheckResponse)
async def check_monitor_now(
    monitor_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate check of a monitor."""
    result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(404, "Monitor not found")

    job_id_holder = {"id": None}

    async def _run():
        started = time.monotonic()
        try:
            fc = await scrape(monitor.url, formats=["markdown"])
            new_md = fc.get("markdown") or ""
            new_hash = hashlib.sha256(new_md.encode()).hexdigest()

            old_hash = monitor.last_content_hash
            changed = bool(old_hash) and old_hash != new_hash

            # Persist monitor state
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Monitor).where(Monitor.id == monitor.id))
                m = result.scalar_one()
                m.last_checked_at = datetime.now(timezone.utc)
                m.last_content_hash = new_hash
                m.last_markdown = new_md[:80000] if new_md else None
                m.check_count = (m.check_count or 0) + 1
                if changed:
                    m.last_change_at = datetime.now(timezone.utc)
                    m.change_count = (m.change_count or 0) + 1
                await session.commit()

            # If changed, record a change job
            diff_summary = None
            if changed and monitor.summarize_changes:
                # Quick AI summary of what changed
                old_excerpt = monitor.last_markdown[:6000] if monitor.last_markdown else ""
                new_excerpt = new_md[:6000]
                prompt = (
                    "Compare these two versions of a webpage and summarize what changed "
                    "in 2-3 short bullet points. Focus on substantive content changes, "
                    "not formatting.\n\n"
                    f"OLD VERSION:\n{old_excerpt}\n\n"
                    f"NEW VERSION:\n{new_excerpt}"
                )
                try:
                    diff_summary, _ = await summarize(
                        f"Compare OLD vs NEW content below.\n{old_excerpt}\n---\n{new_excerpt}",
                        prompt,
                        max_tokens=400,
                    )
                except Exception as e:
                    diff_summary = f"(diff summarization failed: {e})"

            # Persist a Job record of this check
            duration_ms = int((time.monotonic() - started) * 1000)
            async with AsyncSessionLocal() as session:
                job = Job(
                    type=JobType.MONITOR_CHECK,
                    url=monitor.url,
                    status=JobStatus.COMPLETED,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=duration_ms,
                    title=f"{'CHANGED' if changed else 'NO CHANGE'} - {monitor.url}",
                    markdown=new_md[:50000] if new_md else None,
                    previous_markdown_hash=old_hash,
                    change_detected=changed,
                    diff_summary=diff_summary,
                )
                session.add(job)
                await session.commit()
                await session.refresh(job)
                job_id_holder["id"] = job.id

        except Exception as e:
            logger.exception(f"Monitor {monitor.id} check failed")
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Monitor).where(Monitor.id == monitor.id))
                m = result.scalar_one()
                m.status = MonitorStatus.ERROR
                await session.commit()

    background_tasks.add_task(_run)

    # Return immediately; client polls /jobs/{id} for the change record
    return MonitorCheckResponse(
        monitor_id=monitor.id,
        url=monitor.url,
        changed=False,  # we don't know synchronously
        diff_summary=None,
        job_id=None,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/monitors/run-due")
async def run_due_monitors(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Run all monitors whose interval has elapsed since last_checked_at.
    Returns count of monitors triggered. Safe to call from a cron / GitHub Action.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Monitor).where(Monitor.status == MonitorStatus.ACTIVE)
    )
    monitors = result.scalars().all()

    triggered = []
    for m in monitors:
        last = m.last_checked_at
        if last is None or (now - last).total_seconds() >= m.interval_seconds:
            triggered.append(m.id)

    for mid in triggered:
        # Trigger a check via a background task using the same logic
        background_tasks.add_task(_check_sync, mid)

    return {"checked": len(triggered), "monitor_ids": triggered}


async def _check_sync(monitor_id: int):
    """Synchronous helper to run a monitor check without going through the endpoint."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = result.scalar_one_or_none()
    if not monitor:
        return

    started = time.monotonic()
    try:
        fc = await scrape(monitor.url, formats=["markdown"])
        new_md = fc.get("markdown") or ""
        new_hash = hashlib.sha256(new_md.encode()).hexdigest()

        old_hash = monitor.last_content_hash
        changed = bool(old_hash) and old_hash != new_hash

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Monitor).where(Monitor.id == monitor.id))
            m = result.scalar_one()
            m.last_checked_at = datetime.now(timezone.utc)
            m.last_content_hash = new_hash
            m.last_markdown = new_md[:80000] if new_md else None
            m.check_count = (m.check_count or 0) + 1
            if changed:
                m.last_change_at = datetime.now(timezone.utc)
                m.change_count = (m.change_count or 0) + 1
            await session.commit()

        diff_summary = None
        if changed and monitor.summarize_changes and monitor.last_markdown:
            try:
                diff_summary, _ = await summarize(
                    f"OLD:\n{monitor.last_markdown[:6000]}\n---\nNEW:\n{new_md[:6000]}",
                    "Compare the OLD and NEW versions. Summarize what changed in 2-3 short bullets.",
                    max_tokens=400,
                )
            except Exception as e:
                diff_summary = f"(diff summarization failed: {e})"

        duration_ms = int((time.monotonic() - started) * 1000)
        async with AsyncSessionLocal() as session:
            job = Job(
                type=JobType.MONITOR_CHECK,
                url=monitor.url,
                status=JobStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                title=f"{'CHANGED' if changed else 'NO CHANGE'} - {monitor.url}",
                markdown=new_md[:50000] if new_md else None,
                previous_markdown_hash=old_hash,
                change_detected=changed,
                diff_summary=diff_summary,
            )
            session.add(job)
            await session.commit()
    except Exception as e:
        logger.exception(f"Monitor {monitor_id} sync check failed")