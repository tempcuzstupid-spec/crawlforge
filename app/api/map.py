"""Map endpoint — sitemap + URL discovery."""

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import MapRequest, MapResponse
from app.services.firecrawl import is_configured, map_site

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["map"])


@router.post("/map", response_model=MapResponse)
async def site_map(payload: MapRequest):
    """
    Discover all URLs on a site via Firecrawl /v2/map.

    This is the "where do I start?" endpoint — returns every discoverable
    URL on a domain, filterable by substring. Use this before a /crawl-site
    to know what you're about to scrape.
    """
    if not is_configured():
        raise HTTPException(503, "Firecrawl required for /map")

    try:
        urls = await map_site(
            str(payload.url),
            limit=payload.limit,
            search=payload.search,
            include_subdomains=payload.include_subdomains,
        )
    except Exception as e:
        raise HTTPException(502, f"Map failed: {e}") from e

    return MapResponse(
        base_url=str(payload.url),
        discovered_urls=urls,
        total=len(urls),
    )