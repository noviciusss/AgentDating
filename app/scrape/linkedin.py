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


def _to_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        return (val.get("linkedinText") or val.get("name") or val.get("city") or 
                val.get("title") or val.get("text") or str(val)).strip()
    return str(val).strip()


def _normalize_actor_output(raw: dict, url: str) -> RawLinkedIn:
    """Normalize the actor's raw output into our RawLinkedIn schema.
    Adapt this function when swapping to a different actor.
    """
    first_last = f"{_to_str(raw.get('firstName'))} {_to_str(raw.get('lastName'))}".strip()
    return RawLinkedIn(
        url=url,
        name=_to_str(raw.get("fullName") or raw.get("name") or first_last),
        headline=_to_str(raw.get("headline") or raw.get("title")),
        about=_to_str(raw.get("about") or raw.get("summary") or raw.get("description")),
        location=_to_str(raw.get("location") or raw.get("addressLocality")),
        experience=[
            LinkedInExperience(
                title=_to_str(exp.get("title")),
                company=_to_str(exp.get("companyName") or exp.get("company")),
                description=_to_str(exp.get("description")),
            )
            for exp in (raw.get("experience") or raw.get("positions") or [])
            if isinstance(exp, dict)
        ],
        education=[
            LinkedInEducation(
                school=_to_str(edu.get("schoolName") or edu.get("school")),
                degree=_to_str(edu.get("degreeName") or edu.get("degree")),
            )
            for edu in (raw.get("education") or raw.get("educations") or [])
            if isinstance(edu, dict)
        ],
        skills=[
            (s.get("name") if isinstance(s, dict) else str(s)).strip()
            for s in (raw.get("skills") or [])
            if s
        ][:30],
        posts=[
            (p.get("text") or p.get("postText") or str(p)).strip() if isinstance(p, dict) else str(p).strip()
            for p in (raw.get("posts") or [])
            if p
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
            "urls": [url],
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
