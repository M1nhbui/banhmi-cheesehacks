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
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

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
# 1b. Hotness score  (BestTime venue_hotness_final)
# =============================================================================

def hotness_score(hotness_val: Optional[float]) -> float:
    """
    Pass-through for the BestTime venue_hotness_final score.

    The value is already normalised to [0, 1] by compute_hotness_v1.py.
    Returns 0.0 when data is unavailable (closed / not yet crawled).

    Args:
        hotness_val : BestTime venue_hotness_final in [0, 1], or None

    Returns:
        float in [0, 1]
    """
    if hotness_val is None:
        return 0.0
    return round(float(max(0.0, min(hotness_val, 1.0))), 4)


# =============================================================================
# 1c. Crowd score  (BestTime current_busyness / 100)
# =============================================================================

def crowd_score(crowd_val: Optional[float]) -> float:
    """
    Pass-through for the BestTime crowd signal.

    crowd_val should be current_busyness / 100 (i.e. the fullness_score
    from compute_hotness_v1.py), already in [0, 1].
    Returns 0.0 when data is unavailable.

    Args:
        crowd_val : BestTime fullness_score in [0, 1], or None

    Returns:
        float in [0, 1]
    """
    if crowd_val is None:
        return 0.0
    return round(float(max(0.0, min(crowd_val, 1.0))), 4)


# =============================================================================
# 2. Weather score  (kept for reference; no longer used in final_score)
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

# ---------------------------------------------------------------------------
# 3b. Simulated-clock helper
# ---------------------------------------------------------------------------

def _get_now() -> datetime:
    """
    Return the "current" datetime used for all urgency calculations.

    When config.SIMULATED_MADISON_HOUR is set (int 0-23), the hour is
    overridden to that value so urgency scores reflect a chosen time of day
    rather than the real clock.  Useful for demos where the real time is
    late at night and most venues would otherwise score 0.

    Set SIMULATED_MADISON_HOUR = None in config.py to use the real clock.
    """
    now = datetime.now(timezone.utc)
    h = config.SIMULATED_MADISON_HOUR
    if h is not None:
        return now.replace(hour=int(h) % 24, minute=0, second=0, microsecond=0)
    return now

def _exp_decay(remaining_seconds: float, tau_seconds: float) -> float:
    """Exponential decay: 1.0 when remaining→0, decays toward 0 as time grows."""
    if remaining_seconds <= 0:
        return 0.0
    return math.exp(-remaining_seconds / tau_seconds)


# ---------------------------------------------------------------------------
# 3c. Event urgency  (pre-start build-up + live wind-down)
# ---------------------------------------------------------------------------

def _compute_urgency_event(
    t_now: datetime,
    t_start: datetime,
    t_end: datetime,
    H_start_s: float,
    tau_start_s: float,
    tau_event_end_s: float,
) -> float:
    """
    Three-phase urgency curve for a timed event:

      • Too early  (start > H_start away)  → 0.0
      • Pre-start  (within H_start window) → exp_decay(delta_to_start, tau_start)
        Score rises from ~0 at H_start hours out to 1.0 the moment it starts.
      • Live       (start ≤ now < end)      → exp_decay(delta_to_end, tau_event_end)
        Score is highest right after start, decays to 0 as the event ends.
      • Ended                               → 0.0
    """
    if t_end <= t_start:
        return 0.0

    if t_now < t_start:
        delta_s = (t_start - t_now).total_seconds()
        if delta_s > H_start_s:
            return 0.0
        return round(_exp_decay(delta_s, tau_start_s), 4)

    if t_start <= t_now < t_end:
        r_end = (t_end - t_now).total_seconds()
        return round(_exp_decay(r_end, tau_event_end_s), 4)

    return 0.0  # ended


# ---------------------------------------------------------------------------
# 3d. Venue urgency  (closing-time pressure)
# ---------------------------------------------------------------------------

def _hhmm_to_dt(hhmm: str, reference: datetime) -> datetime:
    """Build a UTC-aware datetime on the same calendar day as *reference* at HH:MM."""
    h, m = map(int, hhmm.split(":"))
    return reference.replace(hour=h, minute=m, second=0, microsecond=0)


def _compute_urgency_venue(
    t_now: datetime,
    open_str: str,
    close_str: str,
    tau_venue_close_s: float,
) -> float:
    """
    Urgency score for a place based on how close it is to closing.

    Returns 0.0 when the venue is closed or hours are unknown.
    Rises toward 1.0 as closing time approaches (exp-decay with tau_venue_close_s).
    Handles overnight venues (close < open → close is next calendar day).
    """
    # Treat "00:00" for BOTH open and close as "hours unknown" → no urgency
    if open_str == "00:00" and close_str == "00:00":
        return 0.0

    t_open  = _hhmm_to_dt(open_str,  t_now)
    t_close = _hhmm_to_dt(close_str, t_now)

    # Overnight venue: close is after midnight on the next day
    if t_close <= t_open:
        t_close += timedelta(days=1)

    # Venue is closed right now
    if not (t_open <= t_now < t_close):
        return 0.0

    r_close = (t_close - t_now).total_seconds()
    return round(_exp_decay(r_close, tau_venue_close_s), 4)


# ---------------------------------------------------------------------------
# 3e. Public dispatcher — called by pipeline.py and the API
# ---------------------------------------------------------------------------

def urgency_score(
    event_start: Optional[datetime],
    event_end:   Optional[datetime],
    open_str:    Optional[str] = None,
    close_str:   Optional[str] = None,
) -> float:
    """
    Unified urgency score for both events and places.

    Events (event_start + event_end present):
        Uses a three-phase curve — pre-start build-up (within 6 h) then
        live wind-down — both driven by exponential decay.

    Places (open_str + close_str present):
        Closing-time pressure: score rises as the venue approaches closing.

    Default values (from config):
        H_start        = 6 h
        tau_start      = 90 min
        tau_event_end  = 60 min
        tau_venue_close = 60 min

    Returns:
        float in [0, 1]
    """
    now = _get_now()

    # ---- Events --------------------------------------------------------
    if event_start is not None and event_end is not None:
        def _aware(dt: datetime) -> datetime:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return _compute_urgency_event(
            t_now          = now,
            t_start        = _aware(event_start),
            t_end          = _aware(event_end),
            H_start_s      = config.URGENCY_H_START_S,
            tau_start_s    = config.URGENCY_TAU_START_S,
            tau_event_end_s = config.URGENCY_TAU_EVENT_END_S,
        )

    # ---- Places with open/close hours ----------------------------------
    if open_str and close_str:
        return _compute_urgency_venue(
            t_now             = now,
            open_str          = open_str,
            close_str         = close_str,
            tau_venue_close_s = config.URGENCY_TAU_VENUE_CLOSE_S,
        )

    return 0.0


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

    # Remapped sigmoid stretch: creates a clear S-curve so "similar" and
    # "not similar" diverge clearly rather than clustering near 0.
    #
    # Formula:  f(x) = (σ(k·(x−c)) − σ(−k·c)) / (σ(k·(1−c)) − σ(−k·c))
    # This guarantees f(0)=0, f(1)=1, and a steep transition at x=c.
    c = config.SIMILARITY_SIGMOID_CENTER
    k = config.SIMILARITY_SIGMOID_K

    def _sig(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-z))

    sig_lo = _sig(np.array(-k * c))         # σ(k·(0 − c))
    sig_hi = _sig(np.array(k * (1.0 - c)))  # σ(k·(1 − c))
    span = float(sig_hi - sig_lo)

    if span > 1e-9:
        sims = (_sig(k * (sims - c)) - sig_lo) / span
        sims = np.clip(sims, 0.0, 1.0)

    return [round(float(s), 4) for s in sims]


# =============================================================================
# 5. Final weighted score
# =============================================================================

def final_score(
    corr:    float,
    hotness: float,
    crowd:   float,
    urgency: float,
) -> float:
    """
    Combine the four component scores into one final 0..1 ranking score.

    Weights come from config.WEIGHTS and must sum to 1.0.

    Args:
        corr    : keyword ↔ description similarity in [0, 1]
        hotness : BestTime venue_hotness_final in [0, 1]
        crowd   : BestTime current_busyness / 100 in [0, 1]
        urgency : urgency score in [0, 1]

    Returns:
        float in [0, 1]
    """
    w = config.WEIGHTS
    score = (
        w["correlation"] * corr
        + w["hotness"]     * hotness
        + w["crowd"]       * crowd
        + w["urgency"]     * urgency
    )
    # Clamp to [0, 1] to absorb any floating-point drift
    return round(float(max(0.0, min(score, 1.0))), 4)


# =============================================================================
# 5b. Mode-aware scoring  (POST /score?mode=...)
# =============================================================================

def tri(x: float, center: float, width: float) -> float:
    """Triangular membership function — peaks at 1.0 at `center`, drops to 0 at ±`width`."""
    return max(0.0, 1.0 - abs(x - center) / width)


def mode_scores(
    rel:      float,
    hot:      float,
    crowd:    float,
    urg:      float,
    open_now: int = 1,
) -> dict:
    """
    Compute all four mode scores at once.

    Returns a dict with keys: best_match, hot_right_now, hidden_gems, chill.
    All values are in [0, 1], or -1.0 when the venue is closed (open_now=0).

    Args:
        rel      : keyword ↔ description similarity [0, 1]
        hot      : BestTime venue_hotness_final [0, 1]
        crowd    : BestTime current_busyness / 100 [0, 1]
        urg      : urgency score [0, 1]
        open_now : 1 if venue is open, 0 if closed (hard gate)
    """
    if not open_now:
        return {
            "best_match":    -1.0,
            "hot_right_now": -1.0,
            "hidden_gems":   -1.0,
            "chill":         -1.0,
        }

    # Clamp inputs
    rel   = max(0.0, min(1.0, rel))
    hot   = max(0.0, min(1.0, hot))
    crowd = max(0.0, min(1.0, crowd))
    urg   = max(0.0, min(1.0, urg))

    # Derived helper scores
    mid_hot      = tri(hot,   center=0.50, width=0.25)   # peaks at moderate hotness
    calm_hot     = tri(hot,   center=0.30, width=0.25)   # peaks at low-ish hotness
    gentle_crowd = tri(crowd, center=0.28, width=0.22)   # peaks at comfortable crowd
    low_crowd    = 1.0 - crowd
    low_urg      = 1.0 - urg

    # 1) Best Match
    s_best = (
        0.80 * rel
        + 0.02 * hot
        + 0.08 * crowd
        + 0.08 * urg
    )

    # 2) Hot Right Now
    s_hot = (
        0.08 * rel
        + 0.76 * hot
        + 0.08 * crowd
        + 0.08 * urg
    )

    # 3) Hidden Gems
    s_hidden = (
        0.55 * rel
        + 0.20 * mid_hot
        + 0.18 * gentle_crowd
        + 0.07 * low_urg
    )
    if crowd > 0.75:
        s_hidden *= 0.75
    if hot > 0.85:
        s_hidden *= 0.85

    # 4) Chill / Not Crowded
    s_chill = (
        0.5 * rel
        + 0.05 * low_crowd
        + 0.05 * low_urg
        + 0.4 * calm_hot
    )
    if crowd > 0.65:
        s_chill *= 0.60
    if urg > 0.80:
        s_chill *= 0.70

    return {
        "best_match":    round(s_best,   6),
        "hot_right_now": round(s_hot,    6),
        "hidden_gems":   round(s_hidden, 6),
        "chill":         round(s_chill,  6),
    }


def modal_score(
    corr:    float,
    hotness: float,
    crowd:   float,
    urgency: float,
    mode,                 # ScoreMode — imported locally to avoid circular refs
    open_now: int = 1,
) -> float:
    """
    Return the single score for the requested mode by delegating to mode_scores().
    Returns -1.0 (venue closed) or a value in [0, 1].
    """
    from models import ScoreMode  # local import to avoid circular dependency

    scores = mode_scores(corr, hotness, crowd, urgency, open_now=open_now)

    mapping = {
        ScoreMode.relevant:    "best_match",
        ScoreMode.hottest:     "hot_right_now",
        ScoreMode.hidden_gems: "hidden_gems",
        ScoreMode.chill:       "chill",
    }
    key = mapping.get(mode, "best_match")
    s = scores[key]
    if s < 0:
        return s   # -1.0 sentinel for closed venues
    return round(float(max(0.0, min(s, 1.0))), 4)
