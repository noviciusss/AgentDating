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


async def analyze_person(
    person_id: str,
    linkedin: Optional[RawLinkedIn],
    instagram: Optional[RawInstagram],
) -> Optional[Profile]:
    """Analyze one person from their raw LinkedIn + Instagram data.

    Returns a Profile or None if analysis fails.
    One LLM call per person. Retries once on JSON parse failure.
    """
    linkedin_json = json.dumps(
        linkedin.model_dump() if linkedin else {"note": "LinkedIn data not available"},
        indent=2
    )
    instagram_json = json.dumps(
        instagram.model_dump() if instagram else {"note": "Instagram data not available"},
        indent=2
    )

    user_prompt = ANALYSIS_USER_TEMPLATE.format(
        linkedin_json=linkedin_json,
        instagram_json=instagram_json,
        person_id=person_id,
    )

    for attempt in range(2):  # retry once on parse failure
        try:
            raw_response = await call_llm(
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=ANALYSIS_MODEL,
                max_tokens=2000,
                temperature=0.5,
                json_mode=True,
            )

            data = parse_llm_json(raw_response)

            # Ensure the id is set correctly
            data["id"] = person_id

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
