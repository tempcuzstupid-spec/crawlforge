"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


# ===== Crawl =====


class CrawlRequest(BaseModel):
    url: HttpUrl
    summarize: bool = True
    summary_prompt: str = Field(
        default="Provide a concise summary of the main content in 3-5 bullet points."
    )
    extract_schema: dict[str, Any] | None = None  # optional structured extraction
    wait_for_selector: str | None = None
    screenshot: bool = False
    backend: Literal["auto", "local", "firecrawl"] = Field(
        default="auto",
        description="auto=firecrawl if configured else local, local=playwright+crawl4ai, firecrawl=API only",
    )


class CrawlResponse(BaseModel):
    job_id: int
    status: str
    url: str
    backend: str = "local"  # which engine actually ran it
    title: str | None = None
    markdown: str | None = None
    extracted: dict[str, Any] | None = None
    summary: str | None = None
    tokens_used: int | None = None
    duration_ms: int | None = None


# ===== Search (Firecrawl) =====


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    sources: list[Literal["web", "news", "images"]] = ["web"]


class SearchResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]
    total: int


# ===== Map (sitemap + URL discovery) =====


class MapRequest(BaseModel):
    url: HttpUrl
    limit: int = Field(default=100, ge=1, le=5000)
    search: str | None = None  # filter URLs containing this substring
    include_subdomains: bool = False


class MapResponse(BaseModel):
    base_url: str
    discovered_urls: list[str]
    total: int


# ===== Batch scrape =====


class BatchRequest(BaseModel):
    urls: list[HttpUrl] = Field(..., min_length=1, max_length=500)
    summarize: bool = True
    summary_prompt: str = "Provide a concise summary of the main content."
    formats: list[str] = ["markdown"]


class BatchResponse(BaseModel):
    job_id: int
    status: str
    url_count: int
    firecrawl_batch_id: str | None = None


# ===== Extract (LLM-driven structured extraction) =====


class ExtractRequest(BaseModel):
    urls: list[HttpUrl] = Field(..., min_length=1)
    prompt: str = Field(
        ...,
        min_length=10,
        description="What to extract in natural language, e.g. 'Extract product name, price, and rating from each page'",
    )
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    allow_external_links: bool = False
    enable_web_search: bool = False


class ExtractResponse(BaseModel):
    job_id: int
    status: str
    firecrawl_job_id: str | None = None
    result: dict[str, Any] | None = None


# ===== Monitor (change tracking) =====


class MonitorCreate(BaseModel):
    url: HttpUrl
    name: str | None = None
    interval_seconds: int = Field(default=86400, ge=300, le=2592000)  # 5min to 30days
    summarize_changes: bool = True


class MonitorInfo(BaseModel):
    id: int
    url: str
    name: str | None
    status: str
    interval_seconds: int
    summarize_changes: bool
    last_checked_at: str | None
    last_change_at: str | None
    check_count: int
    change_count: int
    created_at: str

    model_config = {"from_attributes": True}


class MonitorCheckResponse(BaseModel):
    monitor_id: int
    url: str
    changed: bool
    diff_summary: str | None
    job_id: int | None
    checked_at: str


# ===== Agent =====


class AgentRequest(BaseModel):
    task: str = Field(..., min_length=5, max_length=2000)
    start_url: HttpUrl | None = None
    max_steps: int = Field(default=15, ge=1, le=50)
    screenshot: bool = False


class AgentResponse(BaseModel):
    job_id: int
    status: str
    task: str
    final_result: str | None = None
    steps_taken: int | None = None
    tokens_used: int | None = None
    duration_ms: int | None = None
    history: list[dict[str, Any]] | None = None


# ===== Job =====


class JobInfo(BaseModel):
    id: int
    type: str
    status: str
    url: str | None
    task: str | None
    title: str | None
    summary: str | None
    duration_ms: int | None
    tokens_used: int | None
    created_at: datetime
    completed_at: datetime | None
    error: str | None = None

    model_config = {"from_attributes": True}


class JobList(BaseModel):
    total: int
    jobs: list[JobInfo]