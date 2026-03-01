# =============================================================================
# models.py — Data models for the Madison Interest Map
# =============================================================================
# We use Python dataclasses for the internal pipeline and Pydantic BaseModel
# for the FastAPI request/response objects.
#
# Two main internal structs:
#   EntityRaw       – a normalized row straight from an ingestion source
#   EntityEnriched  – EntityRaw + computed numeric features (scores)

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


# =============================================================================
# Internal pipeline models (dataclasses — lightweight, no validation overhead)
# =============================================================================

@dataclass
class EntityRaw:
    """
    A single place or event after ingestion and normalization.

    This is the canonical, source-agnostic representation.  Fields map 1-to-1
    to the `entities_raw` schema described in the README.
    """

    # ---- identity --------------------------------------------------------
    entity_id:    str              # unique internal ID (UUID)
    entity_type:  str              # "place" or "event"
    source:       str              # data source name, e.g. "yelp", "fake"
    source_id:    str              # ID from the original source

    # ---- display ---------------------------------------------------------
    name:         str
    lat:          float
    lon:          float
    address:      str

    # ---- text — THIS is what gets compared to user keywords --------------
    description:  str              # rich text: categories + vibe words + blurb
    categories:   str              # comma-separated tags, e.g. "ramen,japanese,cozy"

    # ---- popularity signals (nullable) -----------------------------------
    rating:       Optional[float]  # 0–5; None for events without ratings
    review_count: Optional[int]    # number of reviews; None if unknown
    price_tier:   Optional[int]    # 1–4 (like $ to $$$$)

    # ---- event-specific (nullable for places) ----------------------------
    event_start:  Optional[datetime]
    event_end:    Optional[datetime]

    # ---- venue hours (optional; places from Foursquare have these) --------
    open:         Optional[str] = None   # "HH:MM" local open time,  e.g. "09:00"
    close:        Optional[str] = None   # "HH:MM" local close time, e.g. "23:00"

    # ---- BestTime hotness / crowd signals (optional; None = data not available) ----
    hotness:      Optional[float] = None  # BestTime venue_hotness_final  0..1
    crowd:        Optional[float] = None  # BestTime current_busyness / 100  0..1

    # ---- metadata --------------------------------------------------------
    created_at:   datetime = field(default_factory=datetime.utcnow)
    updated_at:   datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def make_id() -> str:
        """Generate a random UUID string to use as entity_id."""
        return str(uuid.uuid4())


@dataclass
class EntityEnriched(EntityRaw):
    """
    EntityRaw with weather data and pre-computed score components added.

    Inherits every field from EntityRaw and appends:
      - weather_* : current weather snapshot at this entity's coordinates
      - *_score   : normalised 0..1 features computed by scoring.py
    """

    # ---- weather snapshot ------------------------------------------------
    weather_temp_f:      float = 72.0   # temperature in Fahrenheit
    weather_precip_prob: float = 0.1    # 0..1 probability of precipitation
    weather_wind_mph:    float = 5.0    # wind speed
    weather_condition:   str   = "clear"
    weather_updated_at:  Optional[datetime] = None

    # ---- pre-computed score components -----------------------------------
    # These are computed by pipeline.py so the API doesn't redo them per request.
    hotness_score:    float = 0.0   # 0..1 (BestTime venue_hotness_final)
    crowd_score:      float = 0.0   # 0..1 (BestTime current_busyness / 100)
    urgency_score:    float = 0.0   # 0..1 (events: closeness to ending)
    is_active_event:  bool  = False  # True if event is currently happening


# =============================================================================
# API / Pydantic models (used by FastAPI for serialization and validation)
# =============================================================================

class ScoreRequest(BaseModel):
    """
    Body for POST /score.

    Example:
        {
            "keywords": ["ramen", "coffee", "cozy", "study-friendly"]
        }
    """
    keywords: List[str]   # list of interest keywords from the user


class ScoreBreakdown(BaseModel):
    """
    Breakdown of the four components that make up the final score.
    Returned per row so the frontend can show a tooltip or debug panel.
    """
    similarity:  float   # keyword ↔ description cosine similarity
    hotness:     float   # BestTime venue_hotness_final (0..1)
    crowd:       float   # BestTime current_busyness / 100 (0..1)
    urgency:     float   # event urgency (0 for places)


class ScoredRow(BaseModel):
    """
    A single map marker returned to the frontend.
    """
    name:        str
    type:        str             # "place" or "event"
    lat:         float
    lon:         float
    address:     str
    description: str
    score:       float           # final combined score in [0, 1]
    breakdown:   ScoreBreakdown  # per-component breakdown


class ScoreMeta(BaseModel):
    """
    Metadata block included at the top of the /score response.
    """
    city:          str
    keywords:      List[str]
    rows_returned: int


class ScoreResponse(BaseModel):
    """
    Full response body for POST /score.
    """
    meta: ScoreMeta
    rows: List[ScoredRow]
