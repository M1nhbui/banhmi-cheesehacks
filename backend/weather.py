# =============================================================================
# weather.py — Weather enrichment (fake/simulated for demo)
# =============================================================================
# In production you would call a real weather API (OpenWeatherMap, Weatherapi,
# Open-Meteo …) and cache results per grid cell + time bucket.
#
# For the demo we generate a plausible winter/spring weather snapshot for
# Madison, WI and attach it to every entity.
#
# Exposed function:
#   enrich_weather(entity: EntityRaw, snapshot: WeatherSnapshot) -> dict
#   get_madison_weather()  -> WeatherSnapshot (fake but realistic)

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any

# Seed random so results are reproducible across runs within the same session
# (remove or change the seed if you want different weather each run)
_RNG = random.Random(42)


# =============================================================================
# WeatherSnapshot — a simple struct holding a city-wide weather reading
# =============================================================================

@dataclass
class WeatherSnapshot:
    """
    A weather observation at a point in time.
    In a real system this would be looked up per (lat, lon, time) cell.
    For the demo, one snapshot is applied city-wide.
    """
    temp_f:       float   # temperature in Fahrenheit
    precip_prob:  float   # 0..1 probability of precipitation right now
    wind_mph:     float   # wind speed in mph
    condition:    str     # human-readable condition label
    observed_at:  datetime = None

    def __post_init__(self):
        # Auto-fill observation timestamp if not provided
        if self.observed_at is None:
            self.observed_at = datetime.now(timezone.utc)


# =============================================================================
# Pre-built demo snapshots — randomly pick one so each run feels different
# =============================================================================
_DEMO_SNAPSHOTS = [
    # Lovely spring day
    WeatherSnapshot(temp_f=68, precip_prob=0.05, wind_mph=7,  condition="sunny"),
    # Overcast but mild
    WeatherSnapshot(temp_f=60, precip_prob=0.20, wind_mph=10, condition="cloudy"),
    # Rainy and cold
    WeatherSnapshot(temp_f=42, precip_prob=0.80, wind_mph=15, condition="rainy"),
    # Snowy Wisconsin winter
    WeatherSnapshot(temp_f=28, precip_prob=0.70, wind_mph=20, condition="snowy"),
    # Perfect outdoor day
    WeatherSnapshot(temp_f=72, precip_prob=0.02, wind_mph=5,  condition="clear"),
    # Hot summer afternoon
    WeatherSnapshot(temp_f=88, precip_prob=0.10, wind_mph=8,  condition="sunny"),
    # Gentle drizzle
    WeatherSnapshot(temp_f=54, precip_prob=0.60, wind_mph=12, condition="drizzle"),
]


def get_madison_weather(seed: int = None) -> WeatherSnapshot:
    """
    Return a (fake) current weather snapshot for Madison, WI.

    Args:
        seed: Optional integer to pin the random choice for reproducibility.
              If None, uses the module-level RNG (seeded at 42).

    Returns:
        A WeatherSnapshot with realistic-ish Madison weather.
    """
    rng = random.Random(seed) if seed is not None else _RNG
    snapshot = rng.choice(_DEMO_SNAPSHOTS)
    # Return a copy with a fresh timestamp so it always shows "now"
    return WeatherSnapshot(
        temp_f=snapshot.temp_f,
        precip_prob=snapshot.precip_prob,
        wind_mph=snapshot.wind_mph,
        condition=snapshot.condition,
    )


def enrich_weather(entity_fields: Dict[str, Any], snapshot: WeatherSnapshot) -> Dict[str, Any]:
    """
    Merge weather snapshot fields into an entity field dictionary.

    Args:
        entity_fields : a dict representation of an EntityRaw (or its fields).
        snapshot      : the WeatherSnapshot to attach.

    Returns:
        The same dict with weather_* keys added/updated.
    """
    entity_fields["weather_temp_f"]      = snapshot.temp_f
    entity_fields["weather_precip_prob"] = snapshot.precip_prob
    entity_fields["weather_wind_mph"]    = snapshot.wind_mph
    entity_fields["weather_condition"]   = snapshot.condition
    entity_fields["weather_updated_at"]  = snapshot.observed_at
    return entity_fields
