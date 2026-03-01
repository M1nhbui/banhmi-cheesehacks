"""
merge_hotness.py -- Merge BestTime hotness scores into places.json

Usage:
    python3 merge_hotness.py                  # auto-finds newest ranked CSV
    python3 merge_hotness.py <csv_path>       # explicit CSV path

Workflow:
    1. crawldata.py          ->  besttime_outputs/all_venues_aggregated_*.json
    2. compute_hotness_v1.py ->  besttime_outputs/hotness_v1_ranked_*.csv
    3. merge_hotness.py      ->  updates backend/data/places.json in-place
         (backup saved to backend/data/places.json.bak)

CSV columns used:
    venue_name           -> name for tiebreaking
    venue_lat / venue_lng -> geo matching
    venue_hotness_final  -> written as "hotness" (0..1)
    current_busyness     -> divided by 100, written as "crowd" (0..1)

Matching strategy (tried in order):
    1. Best name similarity among venues within GEO_CONFIRM_M (200 m)
    2. Pure geo proximity fallback (<= MAX_DIST_M = 80 m)
"""

from __future__ import annotations

import csv
import difflib
import json
import math
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).parent
HOTNESS_DIR = REPO_ROOT / "besttime_outputs"
PLACES_FILE = REPO_ROOT / "backend" / "data" / "places.json"
BACKUP_FILE = PLACES_FILE.with_suffix(".json.bak")

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------
GEO_CONFIRM_M = 200   # max metres to consider a candidate by name
MAX_DIST_M    = 80    # max metres for pure geo fallback (no name check)


# ---------------------------------------------------------------------------
# Geo helper
# ---------------------------------------------------------------------------
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------
def find_newest_csv() -> Path:
    candidates = sorted(HOTNESS_DIR.glob("hotness_v1_ranked_*.csv"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No hotness_v1_ranked_*.csv found in {HOTNESS_DIR}.\n"
            "Run compute_hotness_v1.py first."
        )
    return candidates[0]


def load_hotness_venues(path: Path) -> list[dict]:
    """Read the ranked CSV and return a list of plain dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Build indexes
# ---------------------------------------------------------------------------
def build_geo_index(venues: list[dict]) -> list[dict]:
    """
    Build a flat list of scored venues from the CSV rows.
    Each entry has: name, lat, lng, hotness, crowd.
    """
    geo_index: list[dict] = []
    for v in venues:
        lat      = v.get("venue_lat")
        lng      = v.get("venue_lng")
        hotness  = v.get("venue_hotness_final")
        busyness = v.get("current_busyness")
        if not lat or not lng or not hotness:
            continue
        geo_index.append({
            "name":    v.get("venue_name", ""),
            "lat":     float(lat),
            "lng":     float(lng),
            "hotness": round(float(hotness), 6),
            "crowd":   round(float(busyness) / 100.0, 6) if busyness not in (None, "") else 0.0,
        })
    return geo_index


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def find_best_match(
    place_name: str,
    place_lat: float,
    place_lon: float,
    geo_index: list,
) -> tuple[dict | None, str]:
    """
    Match a places.json entry to a BestTime CSV row.

    Strategies tried in order:
      1. Best name similarity among venues within GEO_CONFIRM_M (200 m)
      2. Closest venue within MAX_DIST_M (80 m) regardless of name
    """
    # Collect nearby candidates
    nearby = []
    for entry in geo_index:
        dist = haversine_m(place_lat, place_lon, entry["lat"], entry["lng"])
        if dist <= GEO_CONFIRM_M:
            nearby.append((dist, entry))

    if not nearby:
        return None, "none"

    # Strategy 1: best name match within GEO_CONFIRM_M
    best_entry, best_sim = None, 0.0
    for _, entry in nearby:
        sim = difflib.SequenceMatcher(
            None, place_name.lower(), entry["name"].lower()
        ).ratio()
        if sim > best_sim:
            best_sim, best_entry = sim, entry
    if best_sim >= 0.6:   # reasonable name overlap
        return best_entry, "name"

    # Strategy 2: pure geo fallback within MAX_DIST_M
    closest = min(nearby, key=lambda x: x[0])
    if closest[0] <= MAX_DIST_M:
        return closest[1], "geo"

    return None, "none"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    hotness_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else find_newest_csv()
    )
    print(f"[merge] Hotness source : {hotness_path}")

    venues = load_hotness_venues(hotness_path)
    geo_index = build_geo_index(venues)
    print(f"[merge] Hotness index  : {len(geo_index)} scored venues")

    with open(PLACES_FILE, encoding="utf-8") as f:
        places = json.load(f)
    print(f"[merge] places.json    : {len(places)} places")

    shutil.copy2(PLACES_FILE, BACKUP_FILE)
    print(f"[merge] Backup saved   : {BACKUP_FILE}")

    counts: dict[str, int] = {"name": 0, "geo": 0, "none": 0}
    unmatched_names: list[str] = []

    for place in places:
        hit, strategy = find_best_match(
            place.get("name", ""),
            float(place.get("lat", 0)),
            float(place.get("lon", 0)),
            geo_index,
        )
        counts[strategy] += 1
        if hit:
            place["hotness"] = hit["hotness"]
            place["crowd"]   = hit["crowd"]
        else:
            place["hotness"] = None
            place["crowd"]   = None
            unmatched_names.append(place.get("name", ""))

    with open(PLACES_FILE, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

    total   = len(places)
    matched = total - counts["none"]
    pct     = matched / total * 100 if total else 0
    print(f"\n[merge] Done")
    print(f"[merge]   Matched   : {matched}/{total} ({pct:.1f}%)")
    print(f"[merge]     name match   : {counts['name']}")
    print(f"[merge]     geo fallback : {counts['geo']}")
    print(f"[merge]   Unmatched : {counts['none']}")
    for n in unmatched_names[:10]:
        print(f"            - {n}")
    if counts["none"] > 10:
        print(f"            ... and {counts['none'] - 10} more")
    print(f"[merge]   Output    : {PLACES_FILE}")


if __name__ == "__main__":
    main()
