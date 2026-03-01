# =============================================================================
# scoring.py — All scoring / ranking logic
# =============================================================================
# This module is purely functional: every function takes plain numbers / lists
# and returns a float in [0, 1].  No I/O, no side-effects.
#
# Four component scores are defined here:
#   1. popularity_score   — based on rating + review count
#   2. weather_score      — based on temperature, precipitation, wind
#   3. urgency_score      — events only: closeness to their end time
#   4. correlation_scores — batch TF-IDF cosine similarity (keywords vs desc)
#
# And one combiner:
#   final_score           — weighted sum of the four components

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config


# =============================================================================
# 1. Popularity score
# =============================================================================

def popularity_score(rating: float | None, review_count: int | None) -> float:
    """
    Normalise a (rating, review_count) pair into a single 0..1 score.

    Formula (from README):
        rating_score = rating / 5
        count_score  = log(1 + review_count) / log(1 + cap)
        popularity   = 0.7 * rating_score + 0.3 * count_score

    If rating or review_count is None (common for events), we return a
    neutral default of 0.5 so the entity isn't unfairly penalised.

    Args:
        rating       : float 0–5 or None
        review_count : non-negative integer or None

    Returns:
        float in [0, 1]
    """
    # Handle missing data — use neutral 0.5 so the entity isn't penalised
    if rating is None and review_count is None:
        return 0.5

    # --- rating sub-score ---
    if rating is not None:
        # Clamp to [0, 5] in case of bad data, then normalise
        rating_score = max(0.0, min(float(rating), 5.0)) / 5.0
    else:
        rating_score = 0.5   # neutral when missing

    # --- review count sub-score ---
    if review_count is not None:
        cap = config.REVIEW_COUNT_CAP
        # log scale so 10 reviews doesn't score the same as 1000
        count_score = math.log(1 + int(review_count)) / math.log(1 + cap)
        count_score = min(count_score, 1.0)  # cap at 1.0 if count exceeds cap
    else:
        count_score = 0.5   # neutral when missing

    # Weighted combination — rating matters more than raw count
    score = 0.7 * rating_score + 0.3 * count_score
    return round(float(score), 4)


# =============================================================================
# 2. Weather score
# =============================================================================

def weather_score(temp_f: float, precip_prob: float, wind_mph: float) -> float:
    """
    Summarise current weather into a 0..1 "niceness" score.

    Components:
      temp_score    : 1.0 in the ideal temperature range; decays outside it.
      precip_score  : 1 - precip_prob (high rain → low score).
      wind_score    : exponential decay beyond a comfortable wind threshold.

    Args:
        temp_f      : air temperature in Fahrenheit
        precip_prob : probability of precipitation (0..1)
        wind_mph    : wind speed in mph

    Returns:
        float in [0, 1]
    """
    # ---- temperature sub-score ----
    lo   = config.TEMP_IDEAL_LOW_F
    hi   = config.TEMP_IDEAL_HIGH_F
    decay = config.TEMP_DECAY_F

    if lo <= temp_f <= hi:
        # Inside the comfortable range → perfect score
        temp_score = 1.0
    else:
        # How many degrees outside the range?
        deviation = min(abs(temp_f - lo), abs(temp_f - hi))
        # Exponential decay: at deviation == decay, score ≈ 0.37
        temp_score = math.exp(-deviation / decay)

    # ---- precipitation sub-score ----
    # Simple inverse: 0% rain → 1.0 score, 100% rain → 0.0 score
    precip_score = 1.0 - float(precip_prob)

    # ---- wind sub-score ----
    # Comfortable below 10 mph; decays exponentially above that
    wind_comfort_threshold = 10.0   # mph
    excess_wind = max(0.0, wind_mph - wind_comfort_threshold)
    wind_score  = math.exp(-excess_wind / 15.0)   # 15 mph → score ≈ 0.51

    # Equal-weight average of the three components
    score = (temp_score + precip_score + wind_score) / 3.0
    return round(float(score), 4)


# =============================================================================
# 3. Urgency score
# =============================================================================

def urgency_score(event_start: datetime | None, event_end: datetime | None) -> float:
    """
    Compute how "urgent" it is to visit an event.

    Rules:
      - If entity is a place (no start/end) → 0.0
      - If the event hasn't started yet     → 0.0
      - If the event has already ended      → 0.0
      - If the event is in progress:
            remaining_hours = (event_end - now).total_seconds / 3600
            urgency = clamp(1 - remaining_hours / horizon_hours, 0, 1)
        So an event ending in horizon_hours → urgency ≈ 0
           an event ending right now        → urgency = 1

    Args:
        event_start : start datetime (timezone-aware preferred)
        event_end   : end datetime (timezone-aware preferred)

    Returns:
        float in [0, 1]
    """
    # Not an event (no times) → no urgency
    if event_start is None or event_end is None:
        return 0.0

    now = datetime.now(timezone.utc)

    # Ensure both times are timezone-aware so we can compare them to `now`
    def _make_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    start = _make_aware(event_start)
    end   = _make_aware(event_end)

    # Event hasn't started yet or has already ended → no urgency
    if now < start or now >= end:
        return 0.0

    # Event is currently active — compute remaining time
    remaining_hours = (end - now).total_seconds() / 3600.0
    horizon = config.URGENCY_HORIZON_HOURS

    # urgency rises from 0 (horizon hours left) to 1 (ending right now)
    raw = 1.0 - (remaining_hours / horizon)
    score = max(0.0, min(raw, 1.0))   # clamp to [0, 1]
    return round(float(score), 4)


# =============================================================================
# 4. Correlation scores — TF-IDF cosine similarity (batch)
# =============================================================================

def correlation_scores(
    keywords: List[str],
    descriptions: List[str],
) -> List[float]:
    """
    Compute TF-IDF cosine similarity between the user's keywords and each
    entity description.

    How it works:
      1. Build a TF-IDF vocabulary from ALL descriptions (so IDF is meaningful).
      2. Transform the keyword string and each description into a TF-IDF vector.
      3. Compute cosine similarity between the keyword vector and each desc vector.

    Args:
        keywords     : list of keyword strings from the user (e.g. ["ramen","cozy"])
        descriptions : list of entity description strings (one per entity)

    Returns:
        List of floats in [0, 1], same length and order as `descriptions`.
    """
    # Edge case: no keywords → no correlation for anyone
    if not keywords or not descriptions:
        return [0.0] * len(descriptions)

    # Join the user's keywords into a single "query document"
    query = " ".join(keywords)

    # Combine query + all descriptions into one corpus so TF-IDF
    # learns a shared vocabulary and IDF weights from the whole dataset.
    corpus = [query] + descriptions

    # TfidfVectorizer settings:
    #   analyzer='word'  : tokenise by whitespace / punctuation
    #   ngram_range=(1,2): consider single words AND two-word phrases
    #   min_df=1         : include even rare terms (small corpus)
    #   sublinear_tf=True: dampen very frequent terms (log scale TF)
    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )

    # Fit and transform the whole corpus at once
    tfidf_matrix = vectorizer.fit_transform(corpus)   # shape: (1 + N, vocab)

    # The first row is the query vector; the rest are entity vectors
    query_vec = tfidf_matrix[0:1]          # shape: (1, vocab)
    desc_vecs  = tfidf_matrix[1:]          # shape: (N, vocab)

    # Cosine similarity between query and each description
    # Result shape: (1, N) — we flatten to a 1-D list
    sims = cosine_similarity(query_vec, desc_vecs).flatten()

    return [round(float(s), 4) for s in sims]


# =============================================================================
# 5. Final weighted score
# =============================================================================

def final_score(
    corr: float,
    pop:  float,
    weather: float,
    urgency: float,
) -> float:
    """
    Combine the four component scores into one final 0..1 ranking score.

    Weights come from config.WEIGHTS and must sum to 1.0.

    Args:
        corr    : keyword ↔ description similarity in [0, 1]
        pop     : popularity score in [0, 1]
        weather : weather niceness score in [0, 1]
        urgency : urgency score in [0, 1]

    Returns:
        float in [0, 1]
    """
    w = config.WEIGHTS
    score = (
        w["correlation"] * corr
        + w["popularity"]  * pop
        + w["weather"]     * weather
        + w["urgency"]     * urgency
    )
    # Clamp to [0, 1] to absorb any floating-point drift
    return round(float(max(0.0, min(score, 1.0))), 4)
