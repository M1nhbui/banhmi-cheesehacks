"""
Enrich OSM amenity records with Foursquare Places API data.

For each record in the input JSON, this script:
  1. Searches Foursquare by name + lat/lon (radius 100m)
  2. Fetches full place details (hours, description, categories, rating, etc.)
  3. Merges the Foursquare data into the record under a 'foursquare' key
  4. Saves a checkpoint after every batch so you can resume if interrupted

Free tier limits: 1,000 API calls/day
  Each enriched venue = 2 calls (search + details), so ~500 venues/day on free tier.

Setup:
  1. Go to https://developer.foursquare.com and create a free account
  2. Create a new project and copy the API Key
  3. Paste it into backend/.env:
       FSQ_API_KEY=your_key_here
     (The script loads this file automatically — no export needed)
     Or pass directly via CLI:  python enrich_foursquare.py --api-key "your_key_here"

Usage:
  python enrich_foursquare.py
  python enrich_foursquare.py --input amenities.json --output enriched.json
  python enrich_foursquare.py --limit 100          # enrich only first 100 records
  python enrich_foursquare.py --skip-existing      # skip records already enriched (resume)
"""

import argparse
import json
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ---------------------------------------------------------------------------
# Foursquare API
# ---------------------------------------------------------------------------

FSQ_SEARCH_URL  = "https://places-api.foursquare.com/places/search"
FSQ_DETAILS_URL = "https://places-api.foursquare.com/places/{fsq_id}"

# Fields to request from the details endpoint (reduces response size / latency)
DETAIL_FIELDS = ",".join([
    "fsq_place_id",
    "name",
    "description",
    "categories",
    "hours",
    "hours_popular",
    "rating",
    "stats",
    "price",
    "tel",
    "website",
    "social_media",
    "location",
    "geocodes",
    "photos",
    "tips",
    "tastes",
    "attributes",
    "menu",
    "date_closed",
    "popularity",
])

lets# Delay between API calls to stay well within rate limits
CALL_DELAY_SECONDS = 1.0


def make_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Places-Api-Version": "2025-06-17",
        "Accept": "application/json",
    }


class DailyLimitExceeded(Exception):
    """Raised when Foursquare 429s persist across all retries (daily budget exhausted)."""


def _get(url: str, params: dict, api_key: str, retries: int = 4) -> Optional[requests.Response]:
    """GET with automatic retry on 429 rate-limit responses."""
    for attempt in range(1, retries + 1):
        resp = requests.get(url, params=params, headers=make_headers(api_key), timeout=15)
        if resp.status_code == 429:
            if attempt == retries:
                raise DailyLimitExceeded(
                    "Daily API call budget exhausted. "
                    "Re-run tomorrow with --skip-existing to resume."
                )
            wait = 10 * attempt
            print(f"    [FSQ] Rate limited (429) — waiting {wait}s before retry {attempt}/{retries}")
            time.sleep(wait)
            continue
        return resp
    return None


def search_place(name: str, lat: float, lon: float, api_key: str) -> Optional[str]:
    """
    Search Foursquare for a venue by name near lat/lon.
    Returns the fsq_id of the best match, or None if not found.
    """
    params = {
        "query":  name,
        "ll":     f"{lat},{lon}",
        "radius": 100,
        "limit":  1,
    }
    try:
        resp = _get(FSQ_SEARCH_URL, params=params, api_key=api_key)
        if resp is None:
            return None
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0].get("fsq_place_id") or results[0].get("fsq_id")
    except requests.exceptions.RequestException as exc:
        print(f"    [FSQ search error] {exc}")
    return None


def fetch_details(fsq_id: str, api_key: str) -> Optional[dict]:
    """Fetch full place details from Foursquare."""
    url = FSQ_DETAILS_URL.format(fsq_id=fsq_id)
    try:
        resp = _get(url, params={"fields": DETAIL_FIELDS}, api_key=api_key)
        if resp is None:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"    [FSQ details error] {exc}")
    return None


def enrich_record(record: dict, api_key: str) -> dict:
    """
    Add a 'foursquare' key to the record with all data returned by FSQ.
    Returns the record unchanged (with foursquare=None) if no match found.
    """
    name = record.get("tags", {}).get("name") or ""
    lat  = record.get("latitude")
    lon  = record.get("longitude")

    if not name or lat is None or lon is None:
        record["foursquare"] = None
        return record

    # Step 1: search
    time.sleep(CALL_DELAY_SECONDS)
    fsq_id = search_place(name, lat, lon, api_key)

    if not fsq_id:
        record["foursquare"] = None
        return record

    # Step 2: fetch details
    time.sleep(CALL_DELAY_SECONDS)
    details = fetch_details(fsq_id, api_key)
    record["foursquare"] = details
    return record


# ---------------------------------------------------------------------------
# Checkpoint helpers (allows resuming interrupted runs)
# ---------------------------------------------------------------------------

def checkpoint_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return base + ".checkpoint.json"


def load_checkpoint(output_path: str) -> dict:
    """Returns {osm_id: foursquare_data} for already-processed records."""
    cp = checkpoint_path(output_path)
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_checkpoint(output_path: str, done: dict) -> None:
    cp = checkpoint_path(output_path)
    with open(cp, "w", encoding="utf-8") as fh:
        json.dump(done, fh, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich OSM amenity records with Foursquare Places data."
    )
    parser.add_argument(
        "--input",  default="amenities.json",
        help="Input JSON file from fetch_amenities.py (default: amenities.json)",
    )
    parser.add_argument(
        "--output", default="enriched.json",
        help="Output JSON file (default: enriched.json)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Foursquare API key. Falls back to FSQ_API_KEY environment variable.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of records to enrich (useful for testing)",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip records that already have a foursquare key (resume mode)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Save checkpoint every N records (default: 50)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # --- resolve API key ---
    api_key = args.api_key or os.environ.get("FSQ_API_KEY")
    if not api_key:
        print(
            "ERROR: No Foursquare API key found.\n"
            "  Set env var:  export FSQ_API_KEY='your_key'\n"
            "  Or use flag:  --api-key 'your_key'\n"
            "  Get a free key at https://developer.foursquare.com"
        )
        raise SystemExit(1)

    # --- load input ---
    print(f"Loading {args.input} …")
    with open(args.input, encoding="utf-8") as fh:
        records: list = json.load(fh)
    print(f"  {len(records):,} records loaded.")

    # --- load checkpoint ---
    done_map = load_checkpoint(args.output)
    if done_map:
        print(f"  Resuming — {len(done_map):,} records already processed from checkpoint.")

    # --- apply limit ---
    to_process = records[:args.limit] if args.limit else records

    enriched_count = 0
    skipped_count  = 0

    try:
        for i, record in enumerate(to_process, 1):
            osm_id = str(record.get("osm_id", ""))

            # Resume: reuse checkpoint data
            if osm_id in done_map:
                record["foursquare"] = done_map[osm_id]
                skipped_count += 1
                continue

            # Skip records that already have foursquare data in the input
            if args.skip_existing and record.get("foursquare") is not None:
                skipped_count += 1
                continue

            name = record.get("tags", {}).get("name") or "(unnamed)"
            print(f"  [{i}/{len(to_process)}] {name}")

            record = enrich_record(record, api_key)

            # Store in checkpoint map
            done_map[osm_id] = record.get("foursquare")
            enriched_count += 1

            # Periodic checkpoint save
            if enriched_count % args.batch_size == 0:
                save_checkpoint(args.output, done_map)
                print(f"    ✓ Checkpoint saved ({enriched_count} enriched so far)")

    except DailyLimitExceeded as exc:
        print(f"\n  [STOP] {exc}")
        print(f"  Progress saved — {enriched_count} new records enriched this run.")
        save_checkpoint(args.output, done_map)
        print(f"  Re-run tomorrow with: python enrich_foursquare.py --skip-existing")
        raise SystemExit(0)

    # Final checkpoint save
    save_checkpoint(args.output, done_map)

    # Rebuild full records list with FSQ data applied
    for record in records:
        osm_id = str(record.get("osm_id", ""))
        if "foursquare" not in record and osm_id in done_map:
            record["foursquare"] = done_map[osm_id]

    # Save output
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)

    matched = sum(1 for r in to_process if r.get("foursquare") is not None)
    print(f"\nDone.")
    print(f"  Enriched:   {enriched_count:,} new records")
    print(f"  Skipped:    {skipped_count:,} (already processed)")
    print(f"  FSQ match:  {matched:,} / {len(to_process):,} records have Foursquare data")
    print(f"  Output:     {args.output}")


if __name__ == "__main__":
    main()
