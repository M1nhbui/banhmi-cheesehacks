"""
Fetch amenity data from OpenStreetMap via the Overpass API.

Amenity categories:
  Food & Drink  : bar, biergarten, cafe, fast_food, food_court, ice_cream, pub, restaurant
  Entertainment : arts_centre, brothel, casino, cinema, community_centre, conference_centre,
                  events_venue, exhibition_centre, fountain, gambling, love_hotel,
                  music_venue, nightclub, public_bookcase, social_centre, stage,
                  stripclub, studio, theatre

Output fields:
  name, amenity_type, category, latitude, longitude, description,
  open_time, close_time (food/drink)  |  start_time, end_time (entertainment)
  address, phone, website

Usage:
  python fetch_amenities.py                              # defaults to Madison, WI (bbox)
  python fetch_amenities.py --city "Milwaukee" --state "Wisconsin"
  python fetch_amenities.py --city "Springfield" --state "Illinois"
  python fetch_amenities.py --bbox 43.02 -89.57 43.17 -89.28        # Madison, WI bbox (explicit)
  python fetch_amenities.py --output results.json
  python fetch_amenities.py --format csv --output results.csv
  python fetch_amenities.py --amenities restaurant cafe
  python fetch_amenities.py --amenities food_drink
"""

import argparse
import json
import csv
import re
import sys
import time
from collections import Counter
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Amenity definitions
# ---------------------------------------------------------------------------

FOOD_DRINK_AMENITIES = [
    "bar", "biergarten", "cafe", "fast_food",
    "food_court", "ice_cream", "pub", "restaurant",
]

ENTERTAINMENT_AMENITIES = [
    "arts_centre", "brothel", "casino", "cinema",
    "community_centre", "conference_centre", "events_venue",
    "exhibition_centre", "fountain", "gambling", "love_hotel",
    "music_venue", "nightclub", "public_bookcase", "social_centre",
    "stage", "stripclub", "studio", "theatre",
]

ALL_AMENITIES = FOOD_DRINK_AMENITIES + ENTERTAINMENT_AMENITIES
AMENITY_REGEX = "|".join(ALL_AMENITIES)

# ---------------------------------------------------------------------------
# Overpass API
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query_bbox(bbox: tuple) -> str:
    """Build an Overpass QL query for a bounding box (south, west, north, east)."""
    s, w, n, e = bbox
    bbox_str = f"{s},{w},{n},{e}"
    amenity_filter = f'["amenity"~"^({AMENITY_REGEX})$"]'
    return f"""
[out:json][timeout:300];
(
  node{amenity_filter}({bbox_str});
  way{amenity_filter}({bbox_str});
  relation{amenity_filter}({bbox_str});
);
out center tags;
""".strip()


def build_query_area(city_name: str, state_name: Optional[str] = None) -> str:
    """Build an Overpass QL query for a named city, optionally scoped to a state."""
    amenity_filter = f'["amenity"~"^({AMENITY_REGEX})$"]'
    if state_name:
        # Find the state boundary (admin_level 4 in the US), then the city within it
        return f"""
[out:json][timeout:300];
area["name"="{state_name}"]["admin_level"="4"]->.state;
area["name"="{city_name}"]["boundary"="administrative"]["admin_level"~"6|7|8"](area.state)->.search;
(
  node{amenity_filter}(area.search);
  way{amenity_filter}(area.search);
  relation{amenity_filter}(area.search);
);
out center tags;
""".strip()
    # No state — query by city name only
    return f"""
[out:json][timeout:300];
area["name"="{city_name}"]["boundary"="administrative"]["admin_level"~"6|7|8"]->.search;
(
  node{amenity_filter}(area.search);
  way{amenity_filter}(area.search);
  relation{amenity_filter}(area.search);
);
out center tags;
""".strip()


def run_overpass_query(query: str, retries: int = 3) -> dict:
    """Send the Overpass query and return parsed JSON."""
    for attempt in range(1, retries + 1):
        try:
            print(f"  [Overpass] Sending query (attempt {attempt}/{retries}) …")
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=180,
                headers={"User-Agent": "banhmi-cheesehacks/1.0"},
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            print("  [Overpass] Request timed out.")
        except requests.exceptions.RequestException as exc:
            print(f"  [Overpass] Request error: {exc}")

        if attempt < retries:
            wait = 5 * attempt
            print(f"  Retrying in {wait}s …")
            time.sleep(wait)

    raise RuntimeError("All Overpass query attempts failed.")


# ---------------------------------------------------------------------------
# Opening-hours parser
# ---------------------------------------------------------------------------

_TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})")


def parse_opening_hours(oh_str: Optional[str]):
    """
    Return (open_time, close_time) from an OSM opening_hours string.
    Returns (None, None) if unparseable.
    Examples handled:
      "Mo-Fr 08:00-17:00; Sa 09:00-13:00"  →  ("08:00", "17:00")
      "24/7"                                →  ("00:00", "24:00")
      "08:00-22:00"                         →  ("08:00", "22:00")
    """
    if not oh_str:
        return None, None
    if oh_str.strip() == "24/7":
        return "00:00", "24:00"
    match = _TIME_RANGE_RE.search(oh_str)
    if match:
        return match.group(1), match.group(2)
    return None, None


# ---------------------------------------------------------------------------
# Element → record
# ---------------------------------------------------------------------------

def get_lat_lon(element: dict):
    """Extract latitude/longitude from a node, way (center), or relation (center)."""
    if element["type"] == "node":
        return element.get("lat"), element.get("lon")
    center = element.get("center", {})
    return center.get("lat"), center.get("lon")


def element_to_record(element: dict) -> Optional[dict]:
    """Convert a raw Overpass element to a record dict.

    Core derived fields are kept at the top level for easy access.
    Every raw OSM tag is preserved inside 'tags' — nothing is dropped.
    """
    tags = element.get("tags", {})
    amenity_type = tags.get("amenity")
    if not amenity_type:
        return None

    lat, lon = get_lat_lon(element)
    if lat is None or lon is None:
        return None

    category = "food_drink" if amenity_type in FOOD_DRINK_AMENITIES else "entertainment"

    # --- parsed opening hours (convenience) ---
    oh_raw = tags.get("opening_hours") or tags.get("service_times")
    open_t, close_t = parse_opening_hours(oh_raw)

    start_time = tags.get("event:start") or tags.get("start_date") or open_t
    end_time   = tags.get("event:end")   or tags.get("end_date")   or close_t

    record: dict = {
        # --- core derived fields ---
        "osm_id":       element.get("id"),
        "osm_type":     element.get("type"),
        "amenity_type": amenity_type,
        "category":     category,
        "latitude":     lat,
        "longitude":    lon,
        # --- parsed time fields (convenience, sourced from tags below) ---
        "open_time":    open_t    if category == "food_drink" else None,
        "close_time":   close_t   if category == "food_drink" else None,
        "start_time":   start_time if category == "entertainment" else None,
        "end_time":     end_time   if category == "entertainment" else None,
        # --- ALL raw OSM tags, completely unfiltered ---
        "tags":         tags,
    }

    return record


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def save_json(records: list, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"  Saved {len(records):,} records → {path}")


def save_csv(records: list, path: str) -> None:
    if not records:
        print("  No records to save.")
        return
    # Flatten nested 'tags' dict into a JSON string for CSV compatibility
    flat_records = []
    for r in records:
        row = {k: v for k, v in r.items() if k != "tags"}
        row["tags"] = json.dumps(r.get("tags", {}), ensure_ascii=False)
        flat_records.append(row)
    fieldnames = list(flat_records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_records)
    print(f"  Saved {len(flat_records):,} records → {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch OSM amenity data (food/drink & entertainment) via Overpass API."
    )
    location = parser.add_mutually_exclusive_group()
    location.add_argument(
        "--city",
        default="Madison",
        help='Named city to query, e.g. "Milwaukee" or "Chicago" (default: Madison)',
    )
    parser.add_argument(
        "--state",
        default="Wisconsin",
        help='US state name to scope the city lookup, e.g. "Wisconsin" (default: Wisconsin). Ignored when --bbox is used.',
    )
    location.add_argument(
        "--bbox",
        nargs=4,
        metavar=("SOUTH", "WEST", "NORTH", "EAST"),
        type=float,
        help="Bounding box in decimal degrees: south west north east",
    )
    parser.add_argument(
        "--output",
        default="amenities.json",
        help="Output file path (default: amenities.json)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format: json or csv (default: json)",
    )
    parser.add_argument(
        "--amenities",
        nargs="+",
        metavar="AMENITY",
        help=(
            "Filter to specific amenity types or category shortcuts "
            "'food_drink' / 'entertainment'. Defaults to all. "
            f"Available: {', '.join(ALL_AMENITIES)}"
        ),
    )
    return parser.parse_args()


def resolve_amenity_filter(amenities_arg: Optional[list]) -> Optional[list]:
    if not amenities_arg:
        return None  # all
    result = []
    for a in amenities_arg:
        if a == "food_drink":
            result.extend(FOOD_DRINK_AMENITIES)
        elif a == "entertainment":
            result.extend(ENTERTAINMENT_AMENITIES)
        elif a in ALL_AMENITIES:
            result.append(a)
        else:
            print(f"  [WARN] Unknown amenity '{a}' — skipping.")
    return list(dict.fromkeys(result))  # deduplicate, preserve order


def main() -> None:
    args = parse_args()

    # Build query
    # Default to Madison, WI bounding box when no location args given
    if not args.bbox and args.city == "Madison" and getattr(args, "state", None) == "Wisconsin":
        args.bbox = [43.020, -89.550, 43.180, -89.270]

    if args.bbox:
        s, w, n, e = args.bbox
        print(f"Querying bbox: S={s} W={w} N={n} E={e}")
        query = build_query_bbox(tuple(args.bbox))
    else:
        state = getattr(args, "state", None)
        label = f"{args.city}, {state}" if state else args.city
        print(f"Querying area: {label}")
        query = build_query_area(args.city, state)

    # Fetch from Overpass
    data = run_overpass_query(query)
    elements = data.get("elements", [])
    print(f"  Received {len(elements):,} raw elements from Overpass.")

    # Parse elements
    allowed = resolve_amenity_filter(args.amenities)
    records = []
    skipped = 0
    for el in elements:
        rec = element_to_record(el)
        if rec is None:
            skipped += 1
            continue
        if allowed and rec["amenity_type"] not in allowed:
            continue
        records.append(rec)

    print(f"  Parsed {len(records):,} records ({skipped} skipped — missing coords or amenity tag).")

    # Summary breakdown
    counts = Counter(r["amenity_type"] for r in records)
    print("\n  Breakdown by amenity type:")
    for amenity, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {amenity:<25} {count:>6,}")

    # Save output
    print(f"\n  Writing {args.format.upper()} output …")
    if args.format == "csv":
        save_csv(records, args.output)
    else:
        save_json(records, args.output)

    print("\nDone.")


if __name__ == "__main__":
    main()
