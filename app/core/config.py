"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "production"
    secret_key: str = "change-me"
    log_level: str = "INFO"
    version: str = "0.1.0"

    # Database
    database_url: str = "postgresql+asyncpg://localhost/crawlforge"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Firecrawl (premium backend — optional but recommended)
    firecrawl_api_key: str = ""
    firecrawl_base_url: str = "https://api.firecrawl.dev"
    firecrawl_default_backend: bool = True  # use Firecrawl first if key set

    # Playwright
    playwright_browsers_path: str = "/ms-playwright"
    playwright_headless: bool = True
    max_concurrent_browsers: int = 2

    # Stealth mode (drop-in replacement for Playwright Chrome)
    stealth_mode: bool = False  # uses playwright-stealth if True
    # Proxy rotation for local Playwright (comma-separated host:port:user:pass or host:port)
    proxy_list: str = ""  # e.g. "http://user:pass@p1.example.com:8000,http://p2.example.com:8000"
    proxy_rotation: bool = False  # rotate per-request if proxy_list set

    # Crawl4AI
    crawl4ai_max_concurrency: int = 3
    crawl4ai_timeout_seconds: int = 60

    # Agent
    agent_max_steps: int = 20
    agent_timeout_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()