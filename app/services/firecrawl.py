"""Firecrawl v2 API client — premium scraping/crawl/search backend.

Provides:
  - scrape(url) → clean markdown + optional JSON extraction
  - crawl(url, limit) → multi-page crawl as async job
  - search(query) → web search results
  - get_crawl_status(job_id) → poll crawl job

Used as primary backend when FIRECRAWL_API_KEY is set — handles JS rendering,
anti-bot bypass, captchas out of the box. Falls back to local Playwright +
Crawl4AI if not configured.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _headers() -> dict[str, str]:
    if not settings.firecrawl_api_key:
        raise ValueError("FIRECRAWL_API_KEY not configured")
    return {
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
        "Content-Type": "application/json",
    }


async def scrape(
    url: str,
    *,
    formats: list[str | dict] | None = None,
    only_main_content: bool = True,
    wait_for: int | None = None,
    timeout: int = 60,
    **extra: Any,
) -> dict[str, Any]:
    """
    Firecrawl /v2/scrape — single URL → markdown (+ optional JSON / summary / screenshot).

    formats can be strings ("markdown", "html", "summary", "links", "screenshot")
    or dicts like {"type": "json", "prompt": "...", "schema": {...}}
    """
    if formats is None:
        formats = ["markdown"]

    body: dict[str, Any] = {
        "url": url,
        "formats": formats,
        "onlyMainContent": only_main_content,
    }
    if wait_for is not None:
        body["waitFor"] = wait_for
    body.update(extra)

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{settings.firecrawl_base_url}/v2/scrape",
            headers=_headers(),
            json=body,
        )
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Firecrawl scrape failed: {data.get('error', r.text)}")

    payload = data.get("data", {})
    return {
        "title": payload.get("metadata", {}).get("title"),
        "markdown": payload.get("markdown") or payload.get("summary"),
        "html": payload.get("html"),
        "summary": payload.get("summary"),
        "links": payload.get("links"),
        "screenshot": payload.get("screenshot"),
        "json": payload.get("json"),
        "metadata": payload.get("metadata", {}),
        "credits_used": payload.get("metadata", {}).get("creditsUsed", 0),
    }


async def start_crawl(
    url: str,
    *,
    limit: int = 10,
    formats: list[str] | None = None,
    only_main_content: bool = True,
    **extra: Any,
) -> str:
    """
    Firecrawl /v2/crawl — start a multi-URL crawl, returns job ID.
    Poll with get_crawl_status().
    """
    if formats is None:
        formats = ["markdown"]

    body: dict[str, Any] = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {"formats": formats, "onlyMainContent": only_main_content},
    }
    body.update(extra)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.firecrawl_base_url}/v2/crawl",
            headers=_headers(),
            json=body,
        )
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Firecrawl crawl start failed: {data.get('error', r.text)}")
    return data["id"]


async def get_crawl_status(job_id: str, *, timeout: int = 30) -> dict[str, Any]:
    """Poll a crawl job. Returns status + data when complete."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            f"{settings.firecrawl_base_url}/v2/crawl/{job_id}",
            headers=_headers(),
        )
        data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl crawl status failed: {data.get('error', r.text)}")
    return data


async def await_crawl(
    job_id: str,
    *,
    poll_interval: float = 3.0,
    max_wait_seconds: int = 600,
) -> dict[str, Any]:
    """Block until crawl job completes (or timeout). Returns final status."""
    elapsed = 0.0
    while elapsed < max_wait_seconds:
        status = await get_crawl_status(job_id)
        if status.get("status") in ("completed", "failed", "cancelled"):
            return status
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"Crawl {job_id} did not complete in {max_wait_seconds}s")


async def search(
    query: str,
    *,
    limit: int = 10,
    sources: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Firecrawl /v2/search — web search across multiple sources."""
    if sources is None:
        sources = ["web"]

    body: dict[str, Any] = {"query": query, "limit": limit, "sources": sources}
    body.update(extra)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.firecrawl_base_url}/v2/search",
            headers=_headers(),
            json=body,
        )
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Firecrawl search failed: {data.get('error', r.text)}")
    return data.get("data", {})


def is_configured() -> bool:
    """Quick check whether Firecrawl backend can be used."""
    return bool(settings.firecrawl_api_key)


async def map_site(
    url: str,
    *,
    limit: int = 100,
    search: str | None = None,
    include_subdomains: bool = False,
    timeout: int = 120,
) -> list[str] | dict[str, Any]:
    """
    Firecrawl /v2/map — sitemap + URL discovery.

    In v2 this returns BOTH:
      - sync: data.links[] with {url, title, description}
      - async: data.id (pollable job)

    We return the parsed link list when available, else the raw dict
    so the caller can decide whether to poll.
    """
    body: dict[str, Any] = {"url": url, "limit": limit, "includeSubdomains": include_subdomains}
    if search:
        body["search"] = search

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{settings.firecrawl_base_url}/v2/map",
            headers=_headers(),
            json=body,
        )
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Firecrawl map failed: {data.get('error', r.text)}")
    # v2 may return links at top level OR nested under data
    links = data.get("links") or (data.get("data") or {}).get("links") or []
    if links and isinstance(links[0], dict):
        return [link["url"] for link in links if "url" in link]
    return links


async def batch_scrape(
    urls: list[str],
    *,
    formats: list[str | dict] | None = None,
    only_main_content: bool = True,
    timeout: int = 600,
) -> dict[str, Any]:
    """
    Firecrawl /v2/batch/scrape — async batch scrape (up to 500 URLs at once).
    Returns job ID + URLs mapping.
    """
    if formats is None:
        formats = ["markdown"]
    if len(urls) > 500:
        raise ValueError("Batch scrape max is 500 URLs per call")

    body = {
        "urls": urls,
        "formats": formats,
        "onlyMainContent": only_main_content,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.firecrawl_base_url}/v2/batch/scrape",
            headers=_headers(),
            json=body,
        )
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Firecrawl batch scrape failed: {data.get('error', r.text)}")
    return data


async def batch_status(job_id: str, *, timeout: int = 30) -> dict[str, Any]:
    """Poll batch scrape status."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            f"{settings.firecrawl_base_url}/v2/batch/scrape/{job_id}",
            headers=_headers(),
        )
        data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl batch status failed: {data.get('error', r.text)}")
    return data


async def await_batch(job_id: str, *, poll_interval: float = 4.0, max_wait: int = 900) -> dict[str, Any]:
    """Block until batch scrape completes."""
    elapsed = 0.0
    while elapsed < max_wait:
        status = await batch_status(job_id)
        s = status.get("status")
        if s in ("completed", "failed", "cancelled"):
            return status
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"Batch {job_id} did not complete in {max_wait}s")


async def extract(
    urls: list[str] | str,
    *,
    prompt: str | None = None,
    schema: dict[str, Any] | None = None,
    allow_external_links: bool = False,
    enable_web_search: bool = False,
    timeout: int = 600,
) -> dict[str, Any]:
    """
    LLM-driven structured extraction across URLs.

    Strategy:
    - If 1 URL → call /v2/scrape with json format directly (synchronous, fast)
    - If >1 URLs → call /v2/extract (async, returns job id, caller polls)

    Returns a unified dict with either inline data or a job id to poll.
    """
    url_list = urls if isinstance(urls, list) else [urls]

    if len(url_list) == 1:
        # Synchronous path: scrape with json format
        formats: list[Any] = ["markdown"]
        if prompt or schema:
            json_format: dict[str, Any] = {"type": "json"}
            if prompt:
                json_format["prompt"] = prompt
            if schema:
                json_format["schema"] = schema
            formats.append(json_format)
        result = await scrape(url_list[0], formats=formats)
        return {
            "success": True,
            "synchronous": True,
            "data": {
                "json": result.get("json"),
                "markdown": result.get("markdown"),
                "metadata": result.get("metadata", {}),
            },
        }

    # Multi-URL path: async extract job
    body: dict[str, Any] = {"urls": url_list}
    if prompt:
        body["prompt"] = prompt
    if schema:
        body["schema"] = schema
    if allow_external_links:
        body["allowExternalLinks"] = True
    if enable_web_search:
        body["enableWebSearch"] = True

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.firecrawl_base_url}/v2/extract",
            headers=_headers(),
            json=body,
        )
        data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl extract failed: {data.get('error', r.text)}")
    return data


async def extract_status(job_id: str, *, timeout: int = 30) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            f"{settings.firecrawl_base_url}/v2/extract/{job_id}",
            headers=_headers(),
        )
        return r.json()


async def await_extract(job_id: str, *, poll_interval: float = 4.0, max_wait: int = 900) -> dict[str, Any]:
    elapsed = 0.0
    while elapsed < max_wait:
        status = await extract_status(job_id)
        s = status.get("status") or status.get("data", {}).get("status")
        if s in ("completed", "failed", "cancelled"):
            return status
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"Extract {job_id} did not complete in {max_wait}s")