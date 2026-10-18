"""
Shortlisting — TF-IDF cosine similarity pair selection using scikit-learn.
"""

import logging
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from app.config import TOP_K_SHORTLIST, MAX_PAIRS
from app.models import Profile

logger = logging.getLogger(__name__)


def _profile_to_text(profile: Profile) -> str:
    """Build one text blob from a Profile for embedding."""
    parts = [profile.summary]
    for item in profile.needs:
        parts.append(item.item)
    for item in profile.hobbies:
        parts.append(item.item)
    for item in profile.interests:
        parts.append(item.item)
    for item in profile.values:
        parts.append(item.item)
    if profile.looking_for.description:
        parts.append(profile.looking_for.description)
    return " ".join(parts)


def compute_shortlist(
    profiles: dict[str, Profile],
    top_k: int = TOP_K_SHORTLIST,
    max_pairs: int = MAX_PAIRS,
) -> tuple[list[tuple[str, str]], dict[tuple[str, str], float]]:
    """Compute shortlisted pairs from profiles using embeddings.

    Returns:
        pairs: list of (id_a, id_b) tuples (order-independent, min__max)
        similarities: dict mapping each pair to its similarity score
    """
    if len(profiles) < 2:
        return [], {}

    ids = sorted(profiles.keys())
    texts = [_profile_to_text(profiles[pid]) for pid in ids]

    vectorizer = TfidfVectorizer(max_features=5000)
    matrix = vectorizer.fit_transform(texts)
    sim_matrix = sklearn_cosine(matrix)

    # Zero out self-similarity
    np.fill_diagonal(sim_matrix, 0)

    # For each person, take top-K most similar
    pair_set = set()
    similarities: dict[tuple[str, str], float] = {}

    for i, pid in enumerate(ids):
        top_indices = np.argsort(sim_matrix[i])[::-1][:top_k]
        for j in top_indices:
            if i == j:
                continue
            a, b = min(ids[i], ids[j]), max(ids[i], ids[j])
            pair_set.add((a, b))
            similarities[(a, b)] = float(sim_matrix[i][j])

    # Also store ALL pairwise similarities for non-dated fallback
    all_similarities: dict[tuple[str, str], float] = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            all_similarities[(a, b)] = float(sim_matrix[i][j])

    # Safety cap
    pairs = list(pair_set)[:max_pairs]

    logger.info(f"Shortlisted {len(pairs)} pairs from {len(ids)} people (top-{top_k})")
    return pairs, all_similarities
