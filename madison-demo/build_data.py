import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ----------------------------
# 1) Madison bounding box (demo)
# ----------------------------
BOUNDS = {
    "min_lat": 43.00,
    "min_lon": -89.55,
    "max_lat": 43.16,
    "max_lon": -89.25,
}

CENTER = {"lat": 43.0731, "lon": -89.4012}

# ----------------------------
# 2) Grid resolution
# ----------------------------
GRID_ROWS = 60
GRID_COLS = 60

# ----------------------------
# 3) Demo user preferences (one user)
# ----------------------------
USER_PREFERENCES = {
    "category_weights": [
        {"key": "ramen", "weight": 1.0},
        {"key": "coffee", "weight": 0.6},
        {"key": "museum", "weight": 0.2},
        {"key": "park", "weight": 0.3},
    ]
}

# Global weights for final score
WEIGHTS = {"pref": 0.60, "popularity": 0.25, "event": 0.10, "weather": 0.05}

# Cap for review_count normalization
REVIEW_CAP = 2000

# ----------------------------
# Helpers
# ----------------------------
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def haversine_m(lat1, lon1, lat2, lon2):
    # distance in meters
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def lerp(a, b, t):
    return a + (b - a) * t

# ----------------------------
# Fake data generation
# ----------------------------
ALL_CATEGORIES = [
    "ramen", "japanese", "coffee", "bubble_tea", "museum", "park", "hiking", "bar",
    "pizza", "burger", "thai", "mexican", "dessert", "bookstore", "live_music"
]

OUTDOOR_CATS = {"park", "hiking"}
INDOOR_CATS = {"museum", "bookstore"}

def pick_indoor_outdoor(cats):
    if any(c in OUTDOOR_CATS for c in cats) and not any(c in INDOOR_CATS for c in cats):
        return "OUTDOOR"
    if any(c in INDOOR_CATS for c in cats) and not any(c in OUTDOOR_CATS for c in cats):
        return "INDOOR"
    if any(c in OUTDOOR_CATS for c in cats) and any(c in INDOOR_CATS for c in cats):
        return "MIXED"
    # default: FOOD tends to be indoor-ish for demo
    return "INDOOR"

def generate_places(n=250, seed=42):
    random.seed(seed)
    places = []
    for i in range(n):
        lat = random.uniform(BOUNDS["min_lat"], BOUNDS["max_lat"])
        lon = random.uniform(BOUNDS["min_lon"], BOUNDS["max_lon"])
        cats = random.sample(ALL_CATEGORIES, k=random.choice([1, 2, 3]))
        indoor_outdoor = pick_indoor_outdoor(cats)

        rating = round(random.uniform(3.4, 4.9), 1)
        review_count = int(random.triangular(5, REVIEW_CAP, 120))
        price_tier = random.choice([1, 2, 2, 3, 3, 4])

        places.append({
            "id": f"p_{i:04d}",
            "name": f"Place {i:04d}",
            "lat": lat,
            "lon": lon,
            "categories": cats,
            "rating": rating,
            "review_count": review_count,
            "price_tier": price_tier,
            "indoor_outdoor": indoor_outdoor
        })
    return places

def generate_events(seed=99):
    random.seed(seed)
    now = datetime.now(timezone.utc)
    events = []

    # 1 active event near downtown-ish
    events.append({
        "id": "e_active_1",
        "title": "Live Music Night",
        "lat": CENTER["lat"] + 0.005,
        "lon": CENTER["lon"] - 0.004,
        "start_time": (now - timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(hours=2)).isoformat(),
        "importance": 0.9
    })

    # 2 events starting soon
    for k in range(2):
        events.append({
            "id": f"e_soon_{k+1}",
            "title": f"Pop-up Event {k+1}",
            "lat": random.uniform(BOUNDS["min_lat"], BOUNDS["max_lat"]),
            "lon": random.uniform(BOUNDS["min_lon"], BOUNDS["max_lon"]),
            "start_time": (now + timedelta(hours=random.choice([2, 4, 6]))).isoformat(),
            "end_time": (now + timedelta(hours=random.choice([4, 7, 9]))).isoformat(),
            "importance": random.choice([0.4, 0.6, 0.8])
        })

    # 1 later event (low urgency)
    events.append({
        "id": "e_later_1",
        "title": "Weekend Market",
        "lat": CENTER["lat"] - 0.02,
        "lon": CENTER["lon"] + 0.03,
        "start_time": (now + timedelta(hours=36)).isoformat(),
        "end_time": (now + timedelta(hours=40)).isoformat(),
        "importance": 0.7
    })

    return events

def generate_weather():
    # super simple: one city-wide snapshot
    # (you can replace with real API later)
    return {
        "summary": "Cloudy",
        "temperature_f": 38,
        "precip_prob": 0.15,
        "wind_mph": 9,
        "weather_score": 0.75
    }

# ----------------------------
# Scoring
# ----------------------------
def build_pref_weight_map(user_prefs):
    return {x["key"]: float(x["weight"]) for x in user_prefs["category_weights"]}

def pref_match_score(place, pref_map):
    # sum weights for matched categories, normalize by total possible
    total_possible = sum(pref_map.values()) if pref_map else 1.0
    matched = sum(pref_map.get(c, 0.0) for c in place["categories"])
    return clamp(matched / total_possible)

def popularity_score(place):
    rating = place.get("rating", None)
    review_count = place.get("review_count", None)
    if rating is None:
        rating_score = 0.6
    else:
        rating_score = clamp(rating / 5.0)

    if review_count is None:
        count_score = 0.3
    else:
        count_score = clamp(math.log(1 + review_count) / math.log(1 + REVIEW_CAP))

    return clamp(0.7 * rating_score + 0.3 * count_score)

def parse_time(s):
    return datetime.fromisoformat(s)

def event_score(place, events, now_utc):
    # Match event if within 300m
    # urgency:
    # - active: 1
    # - future: exp(-hours_to_start / 6)
    # - past: 0
    best = 0.0
    for e in events:
        d = haversine_m(place["lat"], place["lon"], e["lat"], e["lon"])
        if d > 300:
            continue

        start = parse_time(e["start_time"])
        end = parse_time(e["end_time"])
        imp = float(e.get("importance", 0.5))

        if start <= now_utc <= end:
            urg = 1.0
        elif now_utc < start:
            hours = (start - now_utc).total_seconds() / 3600.0
            urg = math.exp(-hours / 6.0)
        else:
            urg = 0.0

        best = max(best, clamp(imp * urg))
    return best

def weather_suitability_score(place, weather_score_city):
    t = place.get("indoor_outdoor", "INDOOR")
    if t == "INDOOR":
        return 0.90
    if t == "OUTDOOR":
        return clamp(weather_score_city)
    # MIXED
    return clamp(0.5 * (0.90 + weather_score_city))

def final_place_score(place, pref_map, events, weather_city, now_utc):
    s_pref = pref_match_score(place, pref_map)
    s_pop = popularity_score(place)
    s_evt = event_score(place, events, now_utc)
    s_wx = weather_suitability_score(place, weather_city["weather_score"])

    score = (
        WEIGHTS["pref"] * s_pref
        + WEIGHTS["popularity"] * s_pop
        + WEIGHTS["event"] * s_evt
        + WEIGHTS["weather"] * s_wx
    )

    return clamp(score), {
        "pref": round(s_pref, 3),
        "popularity": round(s_pop, 3),
        "event": round(s_evt, 3),
        "weather": round(s_wx, 3),
    }

# ----------------------------
# Grid building
# ----------------------------
def build_grid_cells(bounds, rows, cols):
    min_lat = bounds["min_lat"]
    max_lat = bounds["max_lat"]
    min_lon = bounds["min_lon"]
    max_lon = bounds["max_lon"]

    dlat = (max_lat - min_lat) / rows
    dlon = (max_lon - min_lon) / cols

    cells = []
    for r in range(rows):
        for c in range(cols):
            lat0 = min_lat + r * dlat
            lat1 = lat0 + dlat
            lon0 = min_lon + c * dlon
            lon1 = lon0 + dlon

            center_lat = (lat0 + lat1) / 2
            center_lon = (lon0 + lon1) / 2

            polygon = {
                "type": "Polygon",
                "coordinates": [[
                    [lon0, lat0],
                    [lon1, lat0],
                    [lon1, lat1],
                    [lon0, lat1],
                    [lon0, lat0],
                ]]
            }

            cells.append({
                "cell_id": f"r{r}c{c}",
                "r": r,
                "c": c,
                "center": {"lat": center_lat, "lon": center_lon},
                "polygon": polygon,
            })
    return cells

def compute_cell_scores(cells, places, pref_map, events, weather_city, now_utc,
                        radius_m=800, top_k=3):
    # Precompute place scores once (for speed)
    place_scores = {}
    place_breakdowns = {}
    for p in places:
        s, breakdown = final_place_score(p, pref_map, events, weather_city, now_utc)
        place_scores[p["id"]] = s
        place_breakdowns[p["id"]] = breakdown

    scored_cells = []
    for cell in cells:
        clat = cell["center"]["lat"]
        clon = cell["center"]["lon"]

        candidates = []
        for p in places:
            d = haversine_m(clat, clon, p["lat"], p["lon"])
            if d <= radius_m:
                candidates.append((place_scores[p["id"]], p["id"]))

        candidates.sort(reverse=True, key=lambda x: x[0])
        top = candidates[:top_k]
        if top:
            score = sum(x[0] for x in top) / len(top)
            top_ids = [x[1] for x in top]
        else:
            score = 0.0
            top_ids = []

        scored_cells.append({
            "cell_id": cell["cell_id"],
            "score": round(score, 4),
            "place_count_used": len(candidates),
            "top_place_ids": top_ids,
            "polygon": cell["polygon"],
        })

    return scored_cells, place_scores, place_breakdowns

# ----------------------------
# Main
# ----------------------------
def main():
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)

    places = generate_places(n=250, seed=42)
    events = generate_events(seed=99)
    weather = generate_weather()

    # write raw fake inputs
    (out_dir / "places_madison.json").write_text(json.dumps(places, indent=2))
    (out_dir / "events_madison.json").write_text(json.dumps(events, indent=2))
    (out_dir / "weather_madison.json").write_text(json.dumps(weather, indent=2))

    pref_map = build_pref_weight_map(USER_PREFERENCES)
    now_utc = datetime.now(timezone.utc)

    cells = build_grid_cells(BOUNDS, GRID_ROWS, GRID_COLS)
    scored_cells, place_scores, place_breakdowns = compute_cell_scores(
        cells, places, pref_map, events, weather, now_utc,
        radius_m=800, top_k=3
    )

    # pick top places for markers (keep payload small)
    places_sorted = sorted(places, key=lambda p: place_scores[p["id"]], reverse=True)
    top_places = []
    for p in places_sorted[:30]:
        top_places.append({
            "id": p["id"],
            "name": p["name"],
            "lat": p["lat"],
            "lon": p["lon"],
            "categories": p["categories"],
            "rating": p["rating"],
            "review_count": p["review_count"],
            "price_tier": p["price_tier"],
            "score": round(place_scores[p["id"]], 4),
            "score_breakdown": place_breakdowns[p["id"]],
            "why": [
                f"Matched preference score: {place_breakdowns[p['id']]['pref']}",
                f"Popularity score: {place_breakdowns[p['id']]['popularity']}",
                f"Event score: {place_breakdowns[p['id']]['event']}",
                f"Weather suitability: {place_breakdowns[p['id']]['weather']}",
            ]
        })

    final = {
        "meta": {
            "city": "Madison, WI",
            "generated_at": now_utc.isoformat(),
            "bounds": BOUNDS,
            "grid": {"rows": GRID_ROWS, "cols": GRID_COLS},
            "scoring_weights": WEIGHTS,
            "user_preferences": USER_PREFERENCES,
            "weather": weather
        },
        "top_places": top_places,
        "cells": scored_cells
    }

    (out_dir / "madison_map_data.json").write_text(json.dumps(final, indent=2))
    print("✅ Generated:")
    print(" - data/places_madison.json")
    print(" - data/events_madison.json")
    print(" - data/weather_madison.json")
    print(" - data/madison_map_data.json  (frontend consumes this)")

if __name__ == "__main__":
    main()