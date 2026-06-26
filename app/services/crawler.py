"""Crawl4AI-based URL extraction with stealth + proxy support."""

import logging
from typing import Any

from app.core.config import get_settings
from app.services import proxy as proxy_svc
from app.services.stealth import random_user_agent, try_apply_stealth as try_apply_stealth_fn

logger = logging.getLogger(__name__)
settings = get_settings()


async def crawl_url(
    url: str,
    *,
    wait_for_selector: str | None = None,
    screenshot: bool = False,
    extraction_schema: dict[str, Any] | None = None,
    use_stealth: bool | None = None,
    proxy: str | None = None,
) -> dict[str, Any]:
    """
    Crawl a single URL with Crawl4AI, optionally with stealth patches + proxy rotation.
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.extraction_strategy import LLMExtractionStrategy

    stealth_enabled = use_stealth if use_stealth is not None else settings.stealth_mode
    proxy_url = proxy or proxy_svc.next_proxy()

    # Build browser config with stealth-friendly defaults
    browser_kwargs: dict[str, Any] = {
        "headless": settings.playwright_headless,
        "user_agent": random_user_agent() if stealth_enabled else None,
        "verbose": False,
    }
    if proxy_url:
        browser_kwargs["proxy"] = proxy_url
        logger.info(f"Crawling {url} via proxy {proxy_url}")

    config_kwargs: dict[str, Any] = {
        "word_count_threshold": 10,
        "exclude_external_links": True,
        "screenshot": screenshot,
    }
    if wait_for_selector:
        config_kwargs["wait_for"] = wait_for_selector

    if extraction_schema:
        config_kwargs["extraction_strategy"] = LLMExtractionStrategy(
            llm_config={
                "provider": "openai/" + settings.deepseek_model,
                "api_token": settings.deepseek_api_key,
                "base_url": settings.deepseek_base_url,
            },
            schema=extraction_schema,
        )

    config = CrawlerRunConfig(**config_kwargs)

    # Crawl4AI AsyncWebCrawler hooks accept hooks for stealth injection
    async with AsyncWebCrawler(config=BrowserConfig(**browser_kwargs)) as crawler:
        # If stealth requested, run on crawler-ready hook
        if stealth_enabled:
            try:
                crawler.crawler_strategy.set_hook(
                    "on_page_context_created",
                    lambda context, **kw: __import__("asyncio").create_task(
                        _apply_stealth_to_context(context)
                    ),
                )
            except Exception as e:
                logger.warning(f"Could not register stealth hook: {e}")

        result = await crawler.arun(url=url, config=config)

        if not result.success:
            raise RuntimeError(f"Crawl failed: {result.error_message}")

        extracted = None
        if result.extracted_content and extraction_schema:
            import json
            try:
                extracted = json.loads(result.extracted_content)
            except (json.JSONDecodeError, TypeError):
                extracted = result.extracted_content

        return {
            "title": result.metadata.get("title") if result.metadata else None,
            "markdown": result.markdown,
            "extracted_json": extracted,
            "screenshot_path": result.screenshot if screenshot else None,
            "proxy_used": proxy_url,
            "stealth_used": stealth_enabled,
        }


async def _apply_stealth_to_context(context) -> None:
    """Inject stealth scripts into all pages in a context."""
    try:
        page = await context.new_page()
        await try_apply_stealth(page)
        await page.close()
    except Exception as e:
        logger.warning(f"Stealth injection failed: {e}")