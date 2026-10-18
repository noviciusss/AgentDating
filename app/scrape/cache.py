"""
Disk cache for scrape results, keyed by sha1(normalized_url).
A cache hit must never touch the network.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

from app.config import CACHE_DIR

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize URL: lowercase host, strip query strings & trailing slashes."""
    url = url.strip()
    parsed = urlparse(url)
    # Lowercase the host
    netloc = parsed.netloc.lower()
    # Strip query and fragment, strip trailing slash from path
    path = parsed.path.rstrip('/')
    normalized = urlunparse((parsed.scheme.lower(), netloc, path, '', '', ''))
    return normalized


def url_to_cache_key(url: str) -> str:
    """Return sha1 hash of the normalized URL."""
    normalized = normalize_url(url)
    return hashlib.sha1(normalized.encode()).hexdigest()


def get_cached(url: str) -> Optional[dict]:
    """Return cached data for a URL, or None if not cached."""
    key = url_to_cache_key(url)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        logger.info(f"Cache hit for {url} -> {key}")
        return json.loads(cache_file.read_text(encoding='utf-8'))
    return None


def set_cached(url: str, data: dict) -> None:
    """Cache data for a URL."""
    key = url_to_cache_key(url)
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f"Cached {url} -> {key}")


def validate_linkedin_url(url: str) -> bool:
    """Check that URL contains linkedin.com/in/."""
    return 'linkedin.com/in/' in url.lower()


def validate_instagram_url(url: str) -> bool:
    """Check that URL has a username (path segment after instagram.com)."""
    parsed = urlparse(url)
    return 'instagram.com' in parsed.netloc.lower() and len(parsed.path.strip('/')) > 0
