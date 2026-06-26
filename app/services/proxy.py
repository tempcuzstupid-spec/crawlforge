"""Proxy rotation + stealth helpers for local Playwright."""

import itertools
import logging
import random
from typing import Iterator

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_proxies: list[str] = []
_cycle: Iterator[str] | None = None


def _parse_proxies(raw: str) -> list[str]:
    out = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        # Normalize to dict format Playwright expects
        if not entry.startswith("http://") and not entry.startswith("https://") and not entry.startswith("socks5://"):
            entry = "http://" + entry
        out.append(entry)
    return out


def init() -> None:
    """Parse proxy list once at startup."""
    global _proxies, _cycle
    _proxies = _parse_proxies(settings.proxy_list)
    if _proxies:
        _cycle = itertools.cycle(_proxies)
        logger.info(f"Proxy rotation enabled with {len(_proxies)} proxies")
    else:
        logger.info("No proxies configured")


def next_proxy() -> str | None:
    """Return the next proxy in rotation, or None if disabled."""
    if not settings.proxy_rotation or not _proxies:
        return None
    if _cycle is None:
        return None
    return next(_cycle)


def random_proxy() -> str | None:
    if not settings.proxy_rotation or not _proxies:
        return None
    return random.choice(_proxies)


def has_proxies() -> bool:
    return bool(_proxies)