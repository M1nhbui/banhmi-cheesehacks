# =============================================================================
# pipeline.py — Batch pipeline: ingest → weather enrich → compute features
# =============================================================================
# This module is the "offline" part of the system (described in the README
# under "Offline / batch pipeline").
#
# Steps:
#   1. Ingest raw entities (places + events) from fake_data.py
#   2. Filter to Madison boundary
#   3. Attach a weather snapshot to every entity
#   4. Compute popularity_score and weather_score (pre-baked per entity)
#   5. Compute urgency_score and is_active_event (time-sensitive, done here
#      too for the snapshot — but the API re-computes urgency at request time
#      for accuracy)
#
# Exposed function:
#   build_enriched_entities() -> list[EntityEnriched]

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import List

import config
from fake_data import get_all_entities
from models import EntityRaw, EntityEnriched
from weather import get_madison_weather, enrich_weather
from scoring import popularity_score, weather_score, urgency_score


# =============================================================================
# Geographic boundary filter
# =============================================================================

def _within_madison(entity: EntityRaw) -> bool:
    """
    Return True if the entity's coordinates fall within the Madison bounding box.
    Entities outside this box are silently dropped.
    """
    b = config.MADISON_BOUNDS
    return (
        b["min_lat"] <= entity.lat <= b["max_lat"] and
        b["min_lon"] <= entity.lon <= b["max_lon"]
    )


# =============================================================================
# Main pipeline function
# =============================================================================

def build_enriched_entities() -> List[EntityEnriched]:
    """
    Run the full offline pipeline and return a list of EntityEnriched rows.

    This is called once at startup (or whenever you want to refresh the data).
    The result is cached in-memory and reused for every scoring request.

    Returns:
        List of EntityEnriched, one per valid entity.
    """
    # -----------------------------------------------------------------
    # Step 1: Ingest raw entities (places + events from fake_data.py)
    # -----------------------------------------------------------------
    raw_entities: List[EntityRaw] = get_all_entities()
    print(f"[pipeline] Ingested {len(raw_entities)} raw entities")

    # -----------------------------------------------------------------
    # Step 2: Filter to Madison geographic boundary
    # -----------------------------------------------------------------
    in_madison = [e for e in raw_entities if _within_madison(e)]
    dropped    = len(raw_entities) - len(in_madison)
    print(f"[pipeline] {len(in_madison)} entities in Madison boundary "
          f"({dropped} dropped outside bounds)")

    # -----------------------------------------------------------------
    # Step 3: Get (fake) weather snapshot — city-wide for the demo
    # -----------------------------------------------------------------
    snapshot = get_madison_weather()
    print(f"[pipeline] Weather: {snapshot.condition}, "
          f"{snapshot.temp_f}°F, "
          f"precip={snapshot.precip_prob:.0%}, "
          f"wind={snapshot.wind_mph}mph")

    # -----------------------------------------------------------------
    # Step 4 & 5: For each entity, attach weather and compute scores
    # -----------------------------------------------------------------
    enriched: List[EntityEnriched] = []

    for raw in in_madison:
        # Convert the dataclass to a plain dict so we can mutate it freely
        fields = asdict(raw)

        # -- Attach weather fields to the dict --
        enrich_weather(fields, snapshot)

        # -- Compute popularity_score (static; depends only on rating/reviews) --
        fields["popularity_score"] = popularity_score(
            raw.rating, raw.review_count
        )

        # -- Compute weather_score (static for this run; same snapshot city-wide) --
        fields["weather_score"] = weather_score(
            snapshot.temp_f,
            snapshot.precip_prob,
            snapshot.wind_mph,
        )

        # -- Compute urgency_score (time-sensitive) --
        fields["urgency_score"] = urgency_score(
            raw.event_start, raw.event_end,
            raw.open, raw.close,
        )

        # -- is_active_event: True if the event is currently happening --
        now = datetime.now(timezone.utc)
        if raw.entity_type == "event" and raw.event_start and raw.event_end:
            start = raw.event_start
            end   = raw.event_end
            # Make timezone-aware if naive
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            fields["is_active_event"] = (start <= now <= end)
        else:
            fields["is_active_event"] = False

        # -- Construct the EntityEnriched dataclass from the merged dict --
        enriched.append(EntityEnriched(**fields))

    print(f"[pipeline] Built {len(enriched)} enriched entities")
    return enriched
