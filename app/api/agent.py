"""Agent endpoint — POST /api/v1/agent."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.job import Job, JobType
from app.models.schemas import AgentRequest, AgentResponse
from app.services.orchestrator import run_agent_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["agent"])
settings = get_settings()


@router.post("/agent", response_model=AgentResponse)
async def agent(
    payload: AgentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a natural-language browser task.

    - Browser-Use drives a real Chromium browser
    - DeepSeek decides each step
    - Final result + full history returned
    """
    if not settings.deepseek_api_key:
        raise HTTPException(
            503,
            "DEEPSEEK_API_KEY not configured. Set it in your environment to use agent mode.",
        )

    job = Job(
        type=JobType.AGENT,
        task=payload.task,
        url=str(payload.start_url) if payload.start_url else None,
        options=json.dumps(
            {"max_steps": payload.max_steps, "screenshot": payload.screenshot}
        ),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        run_agent_job,
        job.id,
        payload.task,
        str(payload.start_url) if payload.start_url else None,
        payload.max_steps,
    )

    return AgentResponse(
        job_id=job.id,
        status="pending",
        task=payload.task,
    )