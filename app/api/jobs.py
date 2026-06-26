"""Job CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.job import Job
from app.models.schemas import JobInfo, JobList

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobList)
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List recent jobs with optional filters."""
    stmt = select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit)
    if status:
        stmt = stmt.where(Job.status == status)
    if type:
        stmt = stmt.where(Job.type == type)

    result = await db.execute(stmt)
    jobs = result.scalars().all()

    # Count total
    count_stmt = select(Job)
    if status:
        count_stmt = count_stmt.where(Job.status == status)
    if type:
        count_stmt = count_stmt.where(Job.type == type)
    total = len((await db.execute(count_stmt)).scalars().all())

    return JobList(
        total=total,
        jobs=[JobInfo.model_validate(j) for j in jobs],
    )


@router.get("/{job_id}", response_model=JobInfo)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single job by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return JobInfo.model_validate(job)


@router.delete("/{job_id}")
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a job and its results."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    await db.delete(job)
    await db.commit()
    return {"deleted": job_id}