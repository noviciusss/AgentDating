"""
Analysis module — converts raw LinkedIn + Instagram data into a structured Profile via LLM.
"""

import json
import logging
from typing import Optional

from app.config import ANALYSIS_MODEL
from app.llm import call_llm, parse_llm_json
from app.models import RawLinkedIn, RawInstagram, Profile
from app.prompts import ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_TEMPLATE

logger = logging.getLogger(__name__)


def _prepare_linkedin_summary(li: Optional[RawLinkedIn]) -> dict:
    if not li:
        return {"note": "LinkedIn data not available"}
    exp = []
    for e in li.experience[:5]:
        exp.append({
            "title": e.title,
            "company": e.company,
            "description": (e.description[:250] + "...") if len(e.description) > 250 else e.description
        })
    edu = [{"school": ed.school, "degree": ed.degree} for ed in li.education[:2]]
    posts = [(p[:250] + "...") if len(p) > 250 else p for p in li.posts[:3]]
    return {
        "name": li.name,
        "headline": li.headline,
        "location": li.location,
        "about": (li.about[:600] + "...") if len(li.about) > 600 else li.about,
        "experience": exp,
        "education": edu,
        "skills": li.skills[:10],
        "recent_posts": posts,
    }


def _prepare_instagram_summary(ig: Optional[RawInstagram]) -> dict:
    if not ig:
        return {"note": "Instagram data not available"}
    if ig.is_private:
        return {
            "username": ig.username,
            "full_name": ig.full_name,
            "bio": ig.bio,
            "is_private": True,
            "followers": ig.followers,
            "following": ig.following,
            "note": "Account is private; no posts accessible."
        }
    posts = []
    for p in ig.posts[:6]:
        posts.append({
            "caption": (p.caption[:250] + "...") if len(p.caption) > 250 else p.caption,
            "likes": p.likes,
            "location": p.location,
            "hashtags": p.hashtags[:5]
        })
    return {
        "username": ig.username,
        "full_name": ig.full_name,
        "bio": (ig.bio[:400] + "...") if len(ig.bio) > 400 else ig.bio,
        "followers": ig.followers,
        "following": ig.following,
        "recent_posts": posts,
    }


async def analyze_person(
    person_id: str,
    linkedin: Optional[RawLinkedIn],
    instagram: Optional[RawInstagram],
) -> Optional[Profile]:
    """Analyze one person from their raw LinkedIn + Instagram data.

    Returns a Profile or None if analysis fails.
    One LLM call per person. Retries once on JSON parse failure.
    """
    linkedin_json = json.dumps(_prepare_linkedin_summary(linkedin), indent=2)
    instagram_json = json.dumps(_prepare_instagram_summary(instagram), indent=2)

    user_prompt = ANALYSIS_USER_TEMPLATE.format(
        linkedin_json=linkedin_json,
        instagram_json=instagram_json,
        person_id=person_id,
    )

    for attempt in range(2):  # retry once on parse failure
        try:
            raw_response, model_used = await call_llm(
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=ANALYSIS_MODEL,
                max_tokens=550,
                temperature=0.4,
                json_mode=True,
                return_model=True,
            )

            data = parse_llm_json(raw_response)

            # Ensure the id and model_used are set correctly
            data["id"] = person_id
            data["model_used"] = model_used

            # Tolerant normalization for dict fields that models might return as lists
            for field in ["communication_style", "lifestyle"]:
                if isinstance(data.get(field), list):
                    items = data[field]
                    desc = "; ".join((it.get("item", "") or it.get("description", "")) for it in items if isinstance(it, dict))
                    ev = "; ".join(it.get("evidence", "") for it in items if isinstance(it, dict) and it.get("evidence"))
                    data[field] = {"description": desc, "evidence": ev}

            if isinstance(data.get("looking_for"), list):
                items = data["looking_for"]
                desc = "; ".join((it.get("item", "") or it.get("description", "")) for it in items if isinstance(it, dict))
                ev = "; ".join(it.get("evidence", "") for it in items if isinstance(it, dict) and it.get("evidence"))
                data["looking_for"] = {"description": desc, "confidence": "medium", "evidence": ev}

            if not data.get("agent_persona"):
                summary_hint = data.get("summary", "")[:120]
                data["agent_persona"] = f"Authentic persona grounded in profile: {summary_hint}."

            profile = Profile(**data)
            logger.info(f"Analysis complete for {person_id}: {len(profile.hobbies)} hobbies, {len(profile.interests)} interests")
            return profile

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failure for {person_id} (attempt {attempt + 1}): {e}")
            if attempt == 0:
                continue
            return None
        except Exception as e:
            logger.error(f"Analysis failed for {person_id}: {e}")
            return None

    return None
