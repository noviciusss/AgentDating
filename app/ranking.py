"""
Ranking — scoring formula and per-person ranked match lists.
"""

import logging
from typing import Optional

from app.config import TOP_N_RANKING
from app.models import DateResult, PersonRanking, MatchEntry

logger = logging.getLogger(__name__)


def compute_rankings(
    people_ids: list[str],
    dates: list[DateResult],
    similarities: dict[tuple[str, str], float],
    top_n: int = TOP_N_RANKING,
) -> list[PersonRanking]:
    """Compute per-person ranked match lists.

    Dated pairs use the final_score from the date.
    Non-dated pairs use embedding_similarity * 60 as fallback.
    """
    # Index dates by pair
    date_by_pair: dict[tuple[str, str], DateResult] = {}
    for d in dates:
        key = (min(d.a, d.b), max(d.a, d.b))
        date_by_pair[key] = d

    rankings = []
    for pid in people_ids:
        matches: list[MatchEntry] = []

        for other_id in people_ids:
            if other_id == pid:
                continue

            pair_key = (min(pid, other_id), max(pid, other_id))
            date = date_by_pair.get(pair_key)

            if date and not date.date_failed:
                # Dated pair — use final score
                # Get this person's chemistry + concerns as reason
                if date.a == pid:
                    reason_parts = []
                    if date.a_verdict.chemistry:
                        reason_parts.append(date.a_verdict.chemistry)
                    if date.a_verdict.concerns:
                        reason_parts.append(f"Concerns: {date.a_verdict.concerns}")
                    reason = " ".join(reason_parts)
                else:
                    reason_parts = []
                    if date.b_verdict.chemistry:
                        reason_parts.append(date.b_verdict.chemistry)
                    if date.b_verdict.concerns:
                        reason_parts.append(f"Concerns: {date.b_verdict.concerns}")
                    reason = " ".join(reason_parts)

                matches.append(MatchEntry(
                    other_id=other_id,
                    score=date.final_score,
                    dated=True,
                    reason=reason,
                    date_ref=f"{date.a}__{date.b}",
                ))
            else:
                # Non-dated pair — use embedding similarity * 60
                sim = similarities.get(pair_key, 0.0)
                score = round(sim * 60, 1)

                if date and date.date_failed:
                    reason = "Date failed (similarity estimate)"
                else:
                    reason = "Not dated (similarity estimate)"

                matches.append(MatchEntry(
                    other_id=other_id,
                    score=score,
                    dated=False,
                    reason=reason,
                    date_ref=f"{pair_key[0]}__{pair_key[1]}" if date else "",
                ))

        # Sort descending by score, keep top N
        matches.sort(key=lambda m: m.score, reverse=True)
        matches = matches[:top_n]

        rankings.append(PersonRanking(person_id=pid, matches=matches))

    logger.info(f"Computed rankings for {len(rankings)} people")
    return rankings
