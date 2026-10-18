"""
Instagram adapter — normalizes Apify actor output into RawInstagram.
Wraps the actor behind an adapter so swapping actors is a one-file change.
"""

import logging
from typing import Optional

from app.config import APIFY_INSTAGRAM_ACTOR, MAX_INSTAGRAM_POSTS
from app.models import RawInstagram, InstagramPost
from app.scrape.apify_client import run_actor
from app.scrape.cache import get_cached, set_cached, normalize_url

logger = logging.getLogger(__name__)


def _normalize_actor_output(raw: dict, url: str) -> RawInstagram:
    """Normalize the actor's raw output into our RawInstagram schema.
    Adapt this function when swapping to a different actor.
    """
    # Extract posts, keep at most 20
    raw_posts = (raw.get("latestPosts") or raw.get("posts") or [])[:MAX_INSTAGRAM_POSTS]
    posts = [
        InstagramPost(
            caption=p.get("caption") or p.get("text") or "",
            hashtags=p.get("hashtags") or [],
            location=p.get("locationName") or p.get("location") or "",
            likes=p.get("likesCount") or p.get("likes") or 0,
            timestamp=p.get("timestamp") or p.get("date") or "",
        )
        for p in raw_posts
        if isinstance(p, dict)
    ]

    return RawInstagram(
        url=url,
        username=raw.get("username") or "",
        full_name=raw.get("fullName") or raw.get("full_name") or "",
        bio=raw.get("biography") or raw.get("bio") or "",
        is_private=raw.get("isPrivate") or raw.get("private") or False,
        followers=raw.get("followersCount") or raw.get("followers") or 0,
        following=raw.get("followsCount") or raw.get("following") or 0,
        posts=posts,
    )


async def scrape_instagram(url: str) -> Optional[RawInstagram]:
    """Scrape an Instagram profile. Returns None if scraping fails."""
    url = normalize_url(url)

    # Check cache
    cached = get_cached(url)
    if cached:
        return RawInstagram(**cached)

    # Extract username from URL
    username = url.rstrip('/').split('/')[-1]

    # Run Apify actor
    results = await run_actor(
        actor_id=APIFY_INSTAGRAM_ACTOR,
        run_input={
            "usernames": [username],
        },
    )

    if not results:
        logger.warning(f"Instagram scrape returned no results for {url}")
        return None

    raw = results[0] if isinstance(results, list) else results
    normalized = _normalize_actor_output(raw, url)

    # Check if private
    if normalized.is_private:
        logger.info(f"Instagram profile {username} is private")

    # Cache the result
    set_cached(url, normalized.model_dump())
    return normalized
