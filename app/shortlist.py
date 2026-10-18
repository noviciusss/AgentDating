"""
Shortlisting — embeddings-based pair selection.

Uses sentence-transformers (all-MiniLM-L6-v2) locally.
Falls back to TF-IDF cosine similarity with scikit-learn if sentence-transformers is unavailable.
"""

import logging
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from app.config import TOP_K_SHORTLIST, MAX_PAIRS
from app.models import Profile

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None
_use_tfidf = False


def _get_embedder():
    """Load sentence-transformers model, fall back to TF-IDF."""
    global _model, _use_tfidf
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Loaded sentence-transformers model")
    except Exception as e:
        logger.warning(f"sentence-transformers unavailable ({e}), falling back to TF-IDF")
        _use_tfidf = True
        from sklearn.feature_extraction.text import TfidfVectorizer
        _model = TfidfVectorizer(max_features=5000)

    return _model


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

    embedder = _get_embedder()

    if _use_tfidf:
        # TF-IDF path
        matrix = embedder.fit_transform(texts)
        sim_matrix = sklearn_cosine(matrix)
    else:
        # Sentence-transformers path
        embeddings = embedder.encode(texts, show_progress_bar=False)
        sim_matrix = sklearn_cosine(embeddings)

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
