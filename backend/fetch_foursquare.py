"""
fetch_foursquare.py
-------------------
Fetch places directly from Foursquare Places API for Madison, WI.
No dependency on any prior OSM/amenities file.

Output: foursquare_places.json  (array of raw FSQ place objects)

Usage:
    python fetch_foursquare.py
    python fetch_foursquare.py --output my_file.json
    python fetch_foursquare.py --ne 43.18,-89.27 --sw 43.02,-89.55
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

FSQ_API_KEY = os.getenv("FSQ_API_KEY", "")
FSQ_SEARCH_URL = "https://places-api.foursquare.com/places/search"
API_VERSION = "2025-06-17"

# Madison, WI bounding box  (south,west  →  north,east)
DEFAULT_SW = "43.020,-89.550"
DEFAULT_NE = "43.180,-89.270"

# Keyword queries to sweep.  Each term is sent as the `query` parameter.
# Using keywords avoids needing hard-coded category IDs (which differ between
# legacy and new Places API versions).
SEARCH_QUERIES = [
    "restaurant",
    "bar",
    "cafe",
    "coffee",
    "pizza",
    "brewery",
    "food",
    "nightclub",
    "music venue",
    "concert",
    "theater",
    "entertainment",
    "sports bar",
    "pub",
    "lounge",
    "comedy",
    "arcade",
    "bowling",
    "museum",
    "gallery",
]

LIMIT_PER_REQUEST = 50  # FSQ maximum

# All Pro fields (returned by default) + Premium fields (must be requested explicitly)
# Pro:     fsq_place_id, name, categories, location, latitude, longitude, distance,
#          tel, email, website, social_media, link, chains, store_id, related_places,
#          extended_location, date_created, date_refreshed, date_closed, placemaker_url
# Premium: description, hours, hours_popular, rating, price, popularity, photos,
#          tips, tastes, menu, attributes, place_actions, stats, veracity_rating
ALL_FIELDS = ",".join([
    # Pro fields
    "fsq_place_id", "name", "categories", "location", "latitude", "longitude",
    "distance", "tel", "email", "website", "social_media", "link", "chains",
    "store_id", "related_places", "extended_location", "date_created",
    "date_refreshed", "date_closed", "placemaker_url",
    # Premium fields
    "description", "hours", "hours_popular", "rating", "price", "popularity",
    "photos", "tips", "tastes", "menu", "attributes", "place_actions", "stats",
    "veracity_rating",
])


# Grid size — number of rows and columns to split the bbox into.
# 3×3 = 9 zones × 20 keywords = 180 calls per run.
GRID = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def split_bbox(sw: str, ne: str, rows: int = GRID, cols: int = GRID) -> list:
    """
    Split a bounding box into rows×cols sub-boxes.
    Returns list of (sw_str, ne_str) tuples.
    """
    s, w = map(float, sw.split(","))
    n, e = map(float, ne.split(","))
    lat_step = (n - s) / rows
    lon_step = (e - w) / cols
    zones = []
    for r in range(rows):
        for c in range(cols):
            zone_s = s + r * lat_step
            zone_n = s + (r + 1) * lat_step
            zone_w = w + c * lon_step
            zone_e = w + (c + 1) * lon_step
            zones.append(
                (f"{zone_s:.6f},{zone_w:.6f}", f"{zone_n:.6f},{zone_e:.6f}")
            )
    return zones

def make_headers() -> dict:
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {FSQ_API_KEY}",
        "X-Places-Api-Version": API_VERSION,
    }


def _get(url: str, params: dict, retries: int = 5, base_wait: int = 60) -> dict:
    """GET with exponential back-off on 429."""
    for attempt in range(retries):
        resp = requests.get(url, headers=make_headers(), params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            wait = base_wait * (attempt + 1)
            print(f"  [429] Rate-limited. Waiting {wait}s before retry {attempt + 1}/{retries - 1}…")
            time.sleep(wait)
            continue
        # Any other error — abort
        print(f"  [ERROR] HTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
    raise RuntimeError("Still rate-limited after all retries — wait a few minutes and try again.")


def fetch_query(query: str, sw: str, ne: str) -> list:
    """
    Fetch up to LIMIT_PER_REQUEST results for one keyword query inside the
    bounding box.  The new FSQ Places API does not support offset pagination
    (it returns the same page regardless of offset), so we do a single request.
    """
    params = {
        "sw": sw,
        "ne": ne,
        "query": query,
        "limit": LIMIT_PER_REQUEST,
        "sort": "POPULARITY",
        "fields": ALL_FIELDS,
    }
    print(f"\n  Fetching query='{query}'…")
    data = _get(FSQ_SEARCH_URL, params)
    results = data.get("results", [])
    print(f"    got {len(results)} results")
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch Madison, WI places from Foursquare")
    parser.add_argument("--sw", default=DEFAULT_SW, help="South/West corner  lat,lon")
    parser.add_argument("--ne", default=DEFAULT_NE, help="North/East corner  lat,lon")
    parser.add_argument("--output", default="foursquare_places.json", help="Output JSON file")
    args = parser.parse_args()

    if not FSQ_API_KEY:
        sys.exit("ERROR: FSQ_API_KEY not set. Add it to backend/.env")

    zones = split_bbox(args.sw, args.ne)
    total_calls = len(zones) * len(SEARCH_QUERIES)
    print(f"Bounding box  SW={args.sw}  NE={args.ne}")
    print(f"Grid          {GRID}×{GRID} = {len(zones)} zones × {len(SEARCH_QUERIES)} queries = {total_calls} API calls")
    print(f"Output file   → {args.output}")

    all_places: list = []
    seen_ids: set = set()

    for z_idx, (z_sw, z_ne) in enumerate(zones, 1):
        print(f"\n── Zone {z_idx}/{len(zones)}  SW={z_sw}  NE={z_ne}")
        for q in SEARCH_QUERIES:
            places = fetch_query(q, z_sw, z_ne)
            added = 0
            for p in places:
                pid = p.get("fsq_place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_places.append(p)
                    added += 1
            print(f"  → {added} unique new places for '{q}'. Running total: {len(all_places)}")
            time.sleep(0.5)  # gentle pacing between requests

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).parent.parent / output_path  # project root

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_places, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Saved {len(all_places)} places to {output_path}")


if __name__ == "__main__":
    main()
