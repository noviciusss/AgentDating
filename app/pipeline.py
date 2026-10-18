"""
Pipeline orchestrator — runs the full scrape → analyze → shortlist → date → rank pipeline.
"""

import asyncio
import logging
import re
from typing import Optional

from app.config import SCRAPE_CONCURRENCY
from app.models import Person, Profile, DateResult, PersonRanking, ProgressEvent
from app.scrape.cache import validate_linkedin_url, validate_instagram_url
from app.scrape.linkedin import scrape_linkedin
from app.scrape.instagram import scrape_instagram
from app.analyze import analyze_person
from app.shortlist import compute_shortlist
from app.dating import run_all_dates
from app.ranking import compute_rankings
from app.jobs import emit, update_run, save_run_data, store_run_data

logger = logging.getLogger(__name__)


def _make_slug(name: str, linkedin_url: str, instagram_url: str) -> str:
    """Generate a URL-safe slug from name or URL."""
    if name:
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return slug or "person"

    # Extract from URL
    url = linkedin_url or instagram_url
    parts = url.rstrip('/').split('/')
    return parts[-1].lower() if parts else "person"


async def run_pipeline(run_id: str, people_input: list[dict]):
    """Execute the full pipeline for a run.

    people_input: list of dicts with keys: name (optional), linkedin_url, instagram_url
    """
    try:
        update_run(run_id, status="running")

        # ── Step 1: Validate and create Person objects ─────────────
        people: list[Person] = []
        seen_urls = set()

        for entry in people_input:
            linkedin_url = entry.get("linkedin_url", "").strip()
            instagram_url = entry.get("instagram_url", "").strip()
            name = entry.get("name", "").strip()

            # Dedup by URL pair
            url_key = f"{linkedin_url}|{instagram_url}"
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)

            # Validate URLs
            warnings = []
            if linkedin_url and not validate_linkedin_url(linkedin_url):
                warnings.append(f"Invalid LinkedIn URL: {linkedin_url}")
                linkedin_url = ""
            if instagram_url and not validate_instagram_url(instagram_url):
                warnings.append(f"Invalid Instagram URL: {instagram_url}")
                instagram_url = ""

            if not linkedin_url and not instagram_url:
                slug = _make_slug(name, "", "")
                people.append(Person(
                    id=slug, name=name or slug,
                    status="failed",
                    warnings=["Both LinkedIn and Instagram URLs are missing or invalid"],
                ))
                continue

            slug = _make_slug(name, linkedin_url, instagram_url)

            # Ensure unique slugs
            base_slug = slug
            counter = 2
            while any(p.id == slug for p in people):
                slug = f"{base_slug}-{counter}"
                counter += 1

            people.append(Person(
                id=slug,
                name=name or slug,
                linkedin_url=linkedin_url,
                instagram_url=instagram_url,
                warnings=warnings,
            ))

        update_run(run_id, people=people)

        # ── Step 2: Scrape ─────────────────────────────────────────
        await emit(run_id, ProgressEvent(
            stage="scrape", done=0, total=len(people), message="Starting scrape…"
        ))

        scrape_semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY)
        linkedin_data: dict = {}
        instagram_data: dict = {}

        async def scrape_person(person: Person):
            async with scrape_semaphore:
                if person.status == "failed":
                    return

                li = None
                ig = None

                if person.linkedin_url:
                    li = await scrape_linkedin(person.linkedin_url)
                    if not li:
                        person.warnings.append("LinkedIn scrape failed")

                if person.instagram_url:
                    ig = await scrape_instagram(person.instagram_url)
                    if ig and ig.is_private:
                        person.warnings.append("Instagram is private")
                        ig = None
                    elif not ig:
                        person.warnings.append("Instagram scrape failed")

                if not li and not ig:
                    person.status = "failed"
                    person.warnings.append("Both sources unavailable")
                elif not li or not ig:
                    person.status = "partial"

                # Update name from scraped data if not provided
                if not person.name or person.name == person.id:
                    if li and li.name:
                        person.name = li.name
                    elif ig and ig.full_name:
                        person.name = ig.full_name

                linkedin_data[person.id] = li
                instagram_data[person.id] = ig

        scrape_tasks = [scrape_person(p) for p in people if p.status != "failed"]
        for i, coro in enumerate(asyncio.as_completed(scrape_tasks)):
            await coro
            await emit(run_id, ProgressEvent(
                stage="scrape", done=i + 1, total=len(scrape_tasks),
                message=f"Scraped {i + 1}/{len(scrape_tasks)} people"
            ))

        # ── Step 3: Analyze ────────────────────────────────────────
        active_people = [p for p in people if p.status != "failed"]
        await emit(run_id, ProgressEvent(
            stage="analyze", done=0, total=len(active_people),
            message="Analyzing profiles…"
        ))

        profiles: dict[str, Profile] = {}

        for i, person in enumerate(active_people):
            profile = await analyze_person(
                person.id,
                linkedin_data.get(person.id),
                instagram_data.get(person.id),
            )
            if profile:
                profiles[person.id] = profile
            else:
                person.status = "failed"
                person.warnings.append("Analysis failed")

            await emit(run_id, ProgressEvent(
                stage="analyze", done=i + 1, total=len(active_people),
                message=f"Analyzed {i + 1}/{len(active_people)}"
            ))

        # ── Step 4: Shortlist ──────────────────────────────────────
        await emit(run_id, ProgressEvent(
            stage="shortlist", done=0, total=1, message="Computing shortlist…"
        ))

        pairs, similarities = compute_shortlist(profiles)

        await emit(run_id, ProgressEvent(
            stage="shortlist", done=1, total=1,
            message=f"Shortlisted {len(pairs)} pairs"
        ))

        # ── Step 5: Date ───────────────────────────────────────────
        names = {p.id: p.name for p in people}
        total_turns = len(pairs) * 6
        turns_done = [0]

        async def on_turn(a_id, b_id, turn_no):
            turns_done[0] += 1
            await emit(run_id, ProgressEvent(
                stage="date", done=turns_done[0], total=total_turns,
                message=f"Dating: turn {turns_done[0]}/{total_turns}"
            ))

        dates_done = [0]

        async def on_date_complete(date_result):
            dates_done[0] += 1
            await emit(run_id, ProgressEvent(
                stage="date", done=dates_done[0], total=len(pairs),
                message=f"Completed date {dates_done[0]}/{len(pairs)}"
            ))

        await emit(run_id, ProgressEvent(
            stage="date", done=0, total=len(pairs), message="Starting dates…"
        ))

        dates = await run_all_dates(
            pairs=pairs,
            profiles=profiles,
            names=names,
            on_turn=on_turn,
            on_date_complete=on_date_complete,
        )

        # ── Step 6: Rank ───────────────────────────────────────────
        await emit(run_id, ProgressEvent(
            stage="rank", done=0, total=1, message="Computing rankings…"
        ))

        active_ids = [p.id for p in people if p.status != "failed" and p.id in profiles]
        rankings = compute_rankings(active_ids, dates, similarities)

        await emit(run_id, ProgressEvent(
            stage="rank", done=1, total=1, message="Rankings complete"
        ))

        # ── Save ───────────────────────────────────────────────────
        save_run_data(run_id, people, profiles, dates, rankings)
        store_run_data(run_id, {
            "people": people,
            "profiles": profiles,
            "dates": dates,
            "rankings": rankings,
        })

        update_run(run_id, status="completed", current_stage="done")
        await emit(run_id, ProgressEvent(
            stage="done", done=1, total=1, message="Pipeline complete!"
        ))

    except Exception as e:
        logger.exception(f"Pipeline failed for run {run_id}: {e}")
        update_run(run_id, status="failed", error=str(e))
        await emit(run_id, ProgressEvent(
            stage="done", done=0, total=1, message=f"Pipeline failed: {e}"
        ))
