"""HTML pages — dashboard."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.job import Job

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """Dashboard home — recent jobs + quick actions."""
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).limit(20)
    )
    jobs = result.scalars().all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "jobs": jobs, "title": "CrawlForge"},
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Single job detail page."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "title": "Not Found"},
            status_code=404,
        )
    return templates.TemplateResponse(
        "job.html",
        {"request": request, "job": job, "title": f"Job #{job_id}"},
    )