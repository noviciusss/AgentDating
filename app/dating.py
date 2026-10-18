"""
Date engine — the part graded hardest.

For each shortlisted pair, runs a first date between Agent A and Agent B.
Two separate LLM call streams: Agent A only sees A's profile, Agent B only sees B's.
3 rounds = 6 turns, alternating A then B.
After the transcript, each agent gets a private scoring call.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

from app.config import DATE_MODEL, ANALYSIS_MODEL, MAX_CONCURRENCY
from app.llm import call_llm, call_llm_with_messages, parse_llm_json
from app.models import Profile, DateResult, TranscriptTurn, Verdict
from app.prompts import (
    DATE_AGENT_SYSTEM_TEMPLATE,
    DATE_SCORING_TEMPLATE,
    get_opening_or_closing_hint,
)

logger = logging.getLogger(__name__)


def make_compact_profile(profile: Profile) -> dict:
    """Compact profile for dating: omits evidence strings and keeps top items to save tokens."""
    return {
        "summary": profile.summary,
        "needs": [n.item for n in profile.needs[:4]],
        "values": [v.item for v in profile.values[:4]],
        "hobbies": [h.item for h in profile.hobbies[:4]],
        "interests": [i.item for i in profile.interests[:4]],
        "dealbreakers": [d.item for d in profile.dealbreakers[:3]],
        "looking_for": profile.looking_for.description if hasattr(profile.looking_for, "description") else str(profile.looking_for),
        "agent_persona": profile.agent_persona,
    }


def _build_system_prompt(name: str, profile: Profile, turn_no: int) -> str:
    """Build the date agent system prompt for a specific turn."""
    compact = make_compact_profile(profile)
    return DATE_AGENT_SYSTEM_TEMPLATE.format(
        name=name,
        profile_json=json.dumps(compact, indent=2),
        agent_persona=profile.agent_persona,
        turn_no=turn_no,
        opening_or_closing_hint=get_opening_or_closing_hint(turn_no),
    )


async def run_date(
    a_id: str,
    b_id: str,
    a_name: str,
    b_name: str,
    a_profile: Profile,
    b_profile: Profile,
    on_turn: Optional[Callable] = None,
) -> DateResult:
    """Run a full first date between two agents.

    Returns a DateResult with transcript and verdicts.
    on_turn is called after each completed turn with (a_id, b_id, turn_no).
    """
    transcript: list[TranscriptTurn] = []
    total_turns = 4

    date_model_used = DATE_MODEL
    try:
        for turn_no in range(1, total_turns + 1):
            # Determine whose turn it is
            is_a_turn = (turn_no % 2 == 1)
            speaker = "a" if is_a_turn else "b"
            speaker_name = a_name if is_a_turn else b_name
            speaker_profile = a_profile if is_a_turn else b_profile

            # Build system prompt for this turn
            system_prompt = _build_system_prompt(speaker_name, speaker_profile, turn_no)

            # Build message history from the speaker's perspective
            messages = [{"role": "system", "content": system_prompt}]

            for t in transcript:
                if t.speaker == speaker:
                    messages.append({"role": "assistant", "content": t.text})
                else:
                    messages.append({"role": "user", "content": t.text})

            # If this speaker hasn't spoken yet, add a user prompt
            if not any(t.speaker == speaker for t in transcript):
                if is_a_turn:
                    messages.append({"role": "user", "content": "The date is starting. Say hello."})
                else:
                    # B's first turn — the last transcript entry is A's opening
                    pass  # A's message is already added as a user message

            response, turn_model = await call_llm_with_messages(
                messages=messages,
                model=DATE_MODEL,
                max_tokens=150,
                temperature=0.9,
                return_model=True,
            )
            date_model_used = turn_model

            # Clean the response
            text = response.strip().strip('"').strip('*').strip()
            transcript.append(TranscriptTurn(speaker=speaker, text=text))

            logger.info(f"Date {a_id}__{b_id} turn {turn_no}/{total_turns}: {speaker_name}")
            if on_turn:
                await _safe_callback(on_turn, a_id, b_id, turn_no)

        # ── Scoring ────────────────────────────────────────────────
        a_verdict, b_verdict = await asyncio.gather(
            _score_date(a_name, a_profile, transcript, "a"),
            _score_date(b_name, b_profile, transcript, "b"),
        )

        # ── Final score calculation (Section 10) ──────────────────
        mean = (a_verdict.score + b_verdict.score) / 2
        asym_pen = 0.3 * abs(a_verdict.score - b_verdict.score)
        bonus = 5 if (a_verdict.would_second_date and b_verdict.would_second_date) else 0
        final = max(0, min(100, mean - asym_pen + bonus))

        return DateResult(
            a=a_id,
            b=b_id,
            transcript=transcript,
            a_verdict=a_verdict,
            b_verdict=b_verdict,
            final_score=round(final, 1),
            model_used=date_model_used,
        )

    except Exception as e:
        logger.error(f"Date {a_id}__{b_id} failed: {e}")
        return DateResult(
            a=a_id,
            b=b_id,
            transcript=transcript,
            date_failed=True,
            model_used=date_model_used,
        )


async def _score_date(
    name: str,
    profile: Profile,
    transcript: list[TranscriptTurn],
    speaker: str,
) -> Verdict:
    """Private scoring call for one agent after the date."""
    # Build the transcript text from this agent's perspective
    transcript_text = "\n".join(
        f"{'You' if t.speaker == speaker else 'Them'}: {t.text}"
        for t in transcript
    )

    compact = make_compact_profile(profile)
    system_prompt = f"""You privately evaluate this date for {name}.
Profile: {json.dumps(compact, indent=2)}

Date transcript:
{transcript_text}"""

    scoring_prompt = DATE_SCORING_TEMPLATE.format(name=name)

    try:
        response = await call_llm(
            system_prompt=system_prompt,
            user_prompt=scoring_prompt,
            model=DATE_MODEL,
            max_tokens=300,
            temperature=0.5,
            json_mode=False,
        )
        data = parse_llm_json(response)
        return Verdict(
            score=max(0, min(100, int(data.get("score", 50)))),
            chemistry=data.get("chemistry", ""),
            concerns=data.get("concerns", ""),
            would_second_date=bool(data.get("would_second_date", False)),
        )
    except Exception as e:
        logger.warning(f"Scoring failed for {name}: {e}")
        return Verdict(score=50, chemistry="Scoring unavailable", concerns=str(e))


async def run_all_dates(
    pairs: list[tuple[str, str]],
    profiles: dict[str, Profile],
    names: dict[str, str],
    on_turn: Optional[Callable] = None,
    on_date_complete: Optional[Callable] = None,
) -> list[DateResult]:
    """Run all dates concurrently with a semaphore.

    on_turn: callback(a_id, b_id, turn_no)
    on_date_complete: callback(date_result)
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def _run_one(a_id: str, b_id: str) -> DateResult:
        async with semaphore:
            result = await run_date(
                a_id=a_id, b_id=b_id,
                a_name=names.get(a_id, a_id),
                b_name=names.get(b_id, b_id),
                a_profile=profiles[a_id],
                b_profile=profiles[b_id],
                on_turn=on_turn,
            )
            if on_date_complete:
                await _safe_callback(on_date_complete, result)
            return result

    results = await asyncio.gather(
        *[_run_one(a, b) for a, b in pairs],
        return_exceptions=True,
    )

    # Convert exceptions to failed dates
    final_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            a, b = pairs[i]
            logger.error(f"Date {a}__{b} raised exception: {r}")
            final_results.append(DateResult(a=a, b=b, date_failed=True))
        else:
            final_results.append(r)

    return final_results


async def _safe_callback(fn, *args):
    """Safely call a callback, catching exceptions."""
    try:
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.warning(f"Callback error: {e}")
