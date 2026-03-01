"""
merge_hotness.py — Merge BestTime hotness scores into places.json
=================================================================
Usage:
    python3 merge_hotness.py                         # auto-finds newest hotness file
    python3 merge_hotness.py <hotness_json_path>     # explicit hotness file

Workflow:
    1. Run crawldata.py  →  besttime_outputs/all_venues_aggregated_*.json
    2. Run compute_hotness_v1.py  →  besttime_outputs/hotness_v1_enriched_*.json
    3. Run this script  →  updates backend/data/places.json in-place
         (a backup is saved to backend/data/places.json.bak first)

Matching strategy:
    Primary  : geographic proximity — nearest BestTime venue within MAX_DIST_M metres
    Tiebreak : if two BestTime venues are equidistant, pick the one whose name
               has more characters in common with the place name (difflib ratio)

Output:
    - Updates places.json with "hotness" and "crowd" fields on matched entries
    - Prints a summary: matched / total / unmatched
"""

from __future__ import annotations

import difflib
import json
import math
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT    = Path(__file__).parent
HOTNESS_DIR  = REPO_ROOT / "besttime_outputs"
PLACES_FILE  = REPO_ROOT / "backend" / "data" / "places.json"
BACKUP_FILE  = PLACES_FILE.with_suffix(".json.bak")

# Maximum distance (metres) to consider a BestTime venue a match for a place
MAX_DIST_M = 80   # ~80 m — tight enough to avoid false matches in dense areas


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two (lat, lon) points."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------
def find_newest_hotness_file() -> Path:
    candidates = sorted(HOTNESS_DIR.glob("hotness_v1_enriched_*.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No hotness_v1_enriched_*.json found in {HOTNESS_DIR}.\n"
            "Run compute_hotness_v1.py first."
        )
    return candidates[0]


def load_hotness_venues(path: Path) -> list[dict]:
    """
    Load enriched venues from compute_hotness_v1.py JSON output.

    Accepts two formats:
      - {meta: ..., venues: [...]}    (output from compute_hotness_v1.py main())
      - [...]                          (plain list, just in case)

    Returns a flat list of venue dicts, each guaranteed to have:
        venue_name, venue_lat, venue_lng,
        hotness_v1.venue_hotness_final, hotness_v1.fullness_score
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "venues" in data:
        return data["venues"]
    raise ValueError(f"Unrecognised hotness JSON format in {path}")


# ---------------------------------------------------------------------------
# Build a lightweight spatial index for fast nearest-neighbour lookup
# ---------------------------------------------------------------------------
def build_index(venues: list[dict]) -> list[dict]:
    """
    Return a list of dicts with pre-extracted lat/lng/hotness/crowd
    for every venue that has valid coordinates and a final hotness score.
    """
    index = []
    for v in venues:
        lat = v.get("venue_lat")
        lng = v.get("venue_lng")
        h   = v.get("hotness_v1") or {}
        hotness = h.get("venue_hotness_final")
        crowd   = h.get("fullness_score")

        # Skip venues without coordinates or scores
        if lat is None or lng is None or hotness is None:
            continue

        index.append({
            "name":    v.get("venue_name", ""),
            "lat":     float(lat),
            "lng":     float(lng),
            "hotness": round(float(hotness), 6),
            "crowd":   round(float(crowd), 6) if crowd is not None else 0.0,
        })
    return index


def find_best_match(
    place_name: str,
    place_lat: float,
    place_lon: float,
    index: list[dict],
) -> dict | None:
    """
    Return the best-matching hotness entry for a place, or None if no
    entry falls within MAX_DIST_M metres.

    Among candidates within range, the closest wins.  If two entries
    share the same distance (rare), we use name similarity as a tiebreak.
    """
    best = None
    best_dist = float("inf")
    best_name_sim = 0.0

    for entry in index:
        dist = haversine_m(place_lat, place_lon, entry["lat"], entry["lng"])
        if dist > MAX_DIST_M:
            continue

        name_sim = difflib.SequenceMatcher(
            None,
            place_name.lower(),
            entry["name"].lower(),
        ).ratio()

        # Prefer closer; use name similarity only to break ties at same distance
        if dist < best_dist or (dist == best_dist and name_sim > best_name_sim):
            best       = entry
            best_dist  = dist
            best_name_sim = name_sim

    return best


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # 1. Locate the hotness file
    if len(sys.argv) > 1:
        hotness_path = Path(sys.argv[1])
    else:
        hotness_path = find_newest_hotness_file()
    print(f"[merge] Hotness source : {hotness_path}")

    # 2. Load hotness venues and build spatial index
    venues = load_hotness_venues(hotness_path)
    index  = build_index(venues)
    print(f"[merge] Hotness index  : {len(index)} venues with scores (of {len(venues)} total)")

    # 3. Load places.json
    with open(PLACES_FILE, encoding="utf-8") as f:
        places = json.load(f)
    print(f"[merge] places.json    : {len(places)} places")

    # 4. Back up places.json before modifying
    shutil.copy2(PLACES_FILE, BACKUP_FILE)
    print(f"[merge] Backup saved   : {BACKUP_FILE}")

    # 5. Match and annotate
    matched   = 0
    unmatched = 0
    unmatched_names: list[str] = []

    for place in places:
        name = place.get("name", "")
        lat  = float(place.get("lat", 0))
        lon  = float(place.get("lon", 0))

        hit = find_best_match(name, lat, lon, index)

        if hit is not None:
            place["hotness"] = hit["hotness"]
            place["crowd"]   = hit["crowd"]
            matched += 1
        else:
            # Explicitly set to null so the field exists in every record
            place["hotness"] = None
            place["crowd"]   = None
            unmatched += 1
            unmatched_names.append(name)

    # 6. Write updated places.json (pretty, same indent as original)
    with open(PLACES_FILE, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

    # 7. Summary
    total = len(places)
    pct   = matched / total * 100 if total else 0
    print(f"\n[merge] ✅ Done")
    print(f"[merge]   Matched   : {matched}/{total} ({pct:.1f}%)")
    print(f"[merge]   Unmatched : {unmatched}")

    if unmatched_names:
        preview = unmatched_names[:10]
        print(f"[merge]   Sample unmatched (first {len(preview)}):")
        for n in preview:
            print(f"            - {n}")
        if unmatched > len(preview):
            print(f"            ... and {unmatched - len(preview)} more")

    print(f"[merge]   Output    : {PLACES_FILE}")


if __name__ == "__main__":
    main()
