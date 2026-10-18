"""
LinkedIn adapter — normalizes Apify actor output into RawLinkedIn.
Wraps the actor behind an adapter so swapping actors is a one-file change.
"""

import logging
from typing import Optional

from app.config import APIFY_LINKEDIN_ACTOR
from app.models import RawLinkedIn, LinkedInExperience, LinkedInEducation
from app.scrape.apify_client import run_actor
from app.scrape.cache import get_cached, set_cached, normalize_url

logger = logging.getLogger(__name__)


def _normalize_actor_output(raw: dict, url: str) -> RawLinkedIn:
    """Normalize the actor's raw output into our RawLinkedIn schema.
    Adapt this function when swapping to a different actor.
    """
    return RawLinkedIn(
        url=url,
        name=raw.get("fullName") or raw.get("name") or "",
        headline=raw.get("headline") or raw.get("title") or "",
        about=raw.get("about") or raw.get("summary") or raw.get("description") or "",
        location=raw.get("location") or raw.get("addressLocality") or "",
        experience=[
            LinkedInExperience(
                title=exp.get("title") or "",
                company=exp.get("companyName") or exp.get("company") or "",
                description=exp.get("description") or "",
            )
            for exp in (raw.get("experience") or raw.get("positions") or [])
            if isinstance(exp, dict)
        ],
        education=[
            LinkedInEducation(
                school=edu.get("schoolName") or edu.get("school") or "",
                degree=edu.get("degreeName") or edu.get("degree") or "",
            )
            for edu in (raw.get("education") or raw.get("educations") or [])
            if isinstance(edu, dict)
        ],
        skills=raw.get("skills") or [],
        posts=[
            p.get("text") or p.get("postText") or ""
            for p in (raw.get("posts") or [])
            if isinstance(p, dict)
        ][:10],
    )


async def scrape_linkedin(url: str) -> Optional[RawLinkedIn]:
    """Scrape a LinkedIn profile. Returns None if scraping fails."""
    url = normalize_url(url)

    # Check cache
    cached = get_cached(url)
    if cached:
        return RawLinkedIn(**cached)

    # Run Apify actor
    results = await run_actor(
        actor_id=APIFY_LINKEDIN_ACTOR,
        run_input={
            "profileUrls": [url],
            "proxyConfiguration": {"useApifyProxy": True},
        },
    )

    if not results:
        logger.warning(f"LinkedIn scrape returned no results for {url}")
        return None

    raw = results[0] if isinstance(results, list) else results
    normalized = _normalize_actor_output(raw, url)

    # Cache the result
    set_cached(url, normalized.model_dump())
    return normalized
