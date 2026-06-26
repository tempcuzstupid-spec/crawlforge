"""Monitor model — recurring URL change detection."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MonitorStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[MonitorStatus] = mapped_column(
        SAEnum(MonitorStatus), default=MonitorStatus.ACTIVE, nullable=False, index=True
    )

    # Schedule: interval in seconds (e.g. 3600 = hourly, 86400 = daily)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=86400, nullable=False)

    # Optional AI summarization of changes
    summarize_changes: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # State
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )