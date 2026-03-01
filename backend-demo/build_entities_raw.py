#!/usr/bin/env python3
"""
build_entities_raw.py

Reads foursquare_places.json (the only valid data source) and outputs
data/entities_raw.json in the canonical entities_raw schema.

The `description` field is built from every Foursquare field that carries
useful semantic content for keyword similarity:
  - original description text
  - category names (+ short names when distinct)
  - chain names
  - tastes (curated user keywords)
  - human-readable attributes (wifi, outdoor seating, delivery, etc.)
  - hours display string
  - all customer tip texts

Fields such as name, address, rating, review_count, price_tier, lat/lon,
and dates are stored in their own dedicated schema columns and are therefore
intentionally excluded from the description.

Output: data/entities_raw.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent  # project root
NOW_ISO = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_json(rel_path: str):
    with open(BASE_DIR / rel_path, "r", encoding="utf-8") as f:
        return json.load(f)


_id_counter = 0

def make_id() -> str:
    global _id_counter
    _id_counter += 1
    return str(_id_counter)


# Readable labels for the attributes object
_ATTR_LABELS = {
    "outdoor_seating":   "outdoor seating",
    "wifi":              "wifi",
    "delivery":          "delivery",
    "reservations":      "reservations accepted",
    "takes_credit_card": "credit cards accepted",
    "live_music":        "live music",
    "dj":                "dj",
    "happy_hour":        "happy hour",
    "serves_beer":       "serves beer",
    "serves_wine":       "serves wine",
    "cocktails":         "cocktails",
    "full_bar":          "full bar",
    "breakfast":         "breakfast",
    "brunch":            "brunch",
    "lunch":             "lunch",
    "dinner":            "dinner",
    "coffee":            "coffee",
    "dessert":           "dessert",
    "vegan":             "vegan options",
    "vegetarian":        "vegetarian options",
    "gluten_free":       "gluten free options",
    "dog_friendly":      "dog friendly",
    "good_for_groups":   "good for groups",
    "good_for_kids":     "good for kids",
}


def _attr_truthy(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("t", "true", "yes", "1")
    return False


def build_description(p: dict) -> str:
    """
    Assemble a rich description from all semantically useful Foursquare
    fields. Sections are separated by ' | '.
    Does NOT repeat name, address, rating, review_count, price_tier,
    lat/lon, or dates -- those live in their own schema fields.
    """
    parts: list[str] = []

    # 1. Original description text
    desc = (p.get("description") or "").strip()
    if desc:
        parts.append(desc)

    # 2. Category names (+ short name when it adds information)
    cat_terms: list[str] = []
    for c in (p.get("categories") or []):
        if not isinstance(c, dict):
            continue
        name = c.get("name", "").strip()
        short = c.get("short_name", "").strip()
        if name:
            cat_terms.append(name)
        if short and short.lower() != name.lower():
            cat_terms.append(short)
    if cat_terms:
        parts.append(", ".join(dict.fromkeys(cat_terms)))

    # 3. Chain affiliation
    chains = [
        c.get("name", "").strip()
        for c in (p.get("chains") or [])
        if isinstance(c, dict) and c.get("name")
    ]
    if chains:
        parts.append("chain: " + ", ".join(chains))

    # 4. Tastes -- curated user keywords, very high value for similarity
    tastes = [t for t in (p.get("tastes") or []) if isinstance(t, str) and t.strip()]
    if tastes:
        parts.append("known for: " + ", ".join(tastes))

    # 5. Attributes -> human-readable feature labels
    attrs = p.get("attributes") or {}
    feature_labels: list[str] = []
    for key, label in _ATTR_LABELS.items():
        val = attrs.get(key)
        if val is not None and _attr_truthy(val):
            feature_labels.append(label)
    # Catch any extra attribute keys not in our map
    for key, val in attrs.items():
        if key not in _ATTR_LABELS and isinstance(val, (bool, str)) and _attr_truthy(val):
            feature_labels.append(key.replace("_", " "))
    if feature_labels:
        parts.append("features: " + ", ".join(feature_labels))

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def ingest_foursquare() -> list[dict]:
    raw = load_json("foursquare_places.json")
    rows: list[dict] = []

    for p in raw:
        cat_names = [
            c.get("name", "").strip()
            for c in (p.get("categories") or [])
            if isinstance(c, dict) and c.get("name")
        ]

        address = (p.get("location") or {}).get("formatted_address", "").strip()

        # Foursquare rating is 0–10; normalize to 0–5
        fsq_rating = p.get("rating")
        rating = round(fsq_rating / 2, 2) if fsq_rating is not None else None

        review_count = (p.get("stats") or {}).get("total_ratings")

        # Derive operating window from hours.regular:
        # event_start = earliest open time, event_end = latest close time
        # with a minimum 3-hour spread; if the gap is < 3 h, walk down the
        # sorted close list until the spread is >= 3 h (or use whatever is left).
        regular = (p.get("hours") or {}).get("regular") or []
        def hhmm(s):
            s = str(s).zfill(4)
            return f"{s[:2]}:{s[2:]}"
        def to_minutes(hhmm_int):
            return (hhmm_int // 100) * 60 + (hhmm_int % 100)
        opens  = [int(r["open"])  for r in regular if isinstance(r, dict) and r.get("open")]
        closes = sorted(
            [int(r["close"]) for r in regular if isinstance(r, dict) and r.get("close")],
            reverse=True,
        )
        if opens and closes:
            earliest_open = min(opens)
            open_mins = to_minutes(earliest_open)
            event_start = hhmm(earliest_open)
            event_end = None
            for close in closes:
                close_mins = to_minutes(close)
                # treat close <= open as next-day (add 24 h)
                if close_mins <= open_mins:
                    close_mins += 24 * 60
                if (close_mins - open_mins) >= 180:  # 3 hours in minutes
                    event_end = hhmm(close)
                    break
            if event_end is None:
                event_end = hhmm(closes[0])  # best available even if still < 3 h
        else:
            event_start = None
            event_end   = None

        row = {
            "entity_id":    make_id(),
            "entity_type":  "place",
            "source":       "foursquare",
            "source_id":    p.get("fsq_place_id", ""),
            "name":         p.get("name", ""),
            "lat":          p.get("latitude"),
            "lon":          p.get("longitude"),
            "address":      address,
            "description":  build_description(p),
            "categories":   cat_names,
            "rating":       rating,
            "review_count": review_count,
            "price_tier":   p.get("price"),
            "event_start":  event_start,
            "event_end":    event_end,
            "created_at":   p.get("date_created", NOW_ISO),
            "updated_at":   p.get("date_refreshed", NOW_ISO),
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Ingesting foursquare_places.json ...")
    rows = ingest_foursquare()

    out_path = BASE_DIR / "data" / "entities_raw.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    print(f"Done. Wrote {len(rows)} entities -> {out_path}")

    if rows:
        sample = rows[0]
        print(f"\nSample -- '{sample['name']}':")
        print(f"  address:      {sample['address']}")
        print(f"  rating:       {sample['rating']}")
        print(f"  review_count: {sample['review_count']}")
        print(f"  categories:   {sample['categories']}")
        print(f"  description snippet:\n  {sample['description'][:500]} ...")


if __name__ == "__main__":
    main()
