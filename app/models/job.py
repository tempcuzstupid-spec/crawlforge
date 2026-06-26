"""Job model — every crawl/agent run is a job."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobType(str, Enum):
    CRAWL = "crawl"
    AGENT = "agent"
    MAP = "map"
    BATCH = "batch"
    EXTRACT = "extract"
    MONITOR = "monitor"
    MONITOR_CHECK = "monitor_check"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[JobType] = mapped_column(SAEnum(JobType), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True
    )

    # Input
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Output
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # For monitor changes
    previous_markdown_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_detected: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Meta
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Job id={self.id} type={self.type} status={self.status} url={self.url}>"