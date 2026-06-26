"""Stealth helpers — patches Playwright to bypass bot detection.

Implements:
- Webdriver property removal
- Chrome runtime spoofing (navigator.webdriver = false)
- Plugin/language spoofing
- Permissions API alignment
- iframe.contentWindow isolation patches
- Random realistic user agents
- Optional: playwright-stealth integration if installed

For sites that fingerprint via Canvas/WebGL/Canvas2D, recommend Firecrawl
backend which uses fresh residential browser fingerprints. Local Playwright
cannot match that fidelity without running a real Chromium binary like
CloakBrowser or Patchright.
"""

import logging
import random

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


STEALTH_SCRIPTS = [
    # Delete webdriver property
    """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """,
    # Spoof plugins length
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ]
    });
    """,
    # Languages
    """
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });
    """,
    # Chrome runtime
    """
    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
    """,
    # Permissions
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    """,
    # iframe contentWindow isolation hint
    """
    const elementDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
    Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', { ...elementDescriptor, get: function() { return elementDescriptor.get.apply(this); } });
    """,
]


USER_AGENTS = [
    # Realistic 2026 desktop Chrome/Firefox/Safari user agents
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def stealth_init_scripts() -> list[str]:
    """Return list of JS snippets to inject on page load for stealth."""
    return STEALTH_SCRIPTS


async def try_apply_stealth(page) -> bool:
    """Apply stealth patches to a Playwright page. Returns True if successful."""
    try:
        # If playwright-stealth is installed, use it
        from playwright_stealth import stealth_async
        await stealth_async(page)
        logger.debug("Applied playwright-stealth patches")
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"playwright-stealth failed: {e}")

    # Fallback: inject our manual scripts
    for script in stealth_init_scripts():
        try:
            await page.add_init_script(script)
        except Exception as e:
            logger.warning(f"Failed to inject stealth script: {e}")
            return False
    logger.debug("Applied manual stealth patches")
    return True