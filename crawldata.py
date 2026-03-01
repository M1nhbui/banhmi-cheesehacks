import os
import json
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BESTTIME_API_KEY")
if not API_KEY:
    raise ValueError("Thiếu BESTTIME_API_KEY trong file .env")

BASE = "https://besttime.app/api/v1"
OUT_DIR = Path("besttime_outputs")
OUT_DIR.mkdir(exist_ok=True)

# -----------------------------
# 1) Cấu hình khu vực trung tâm Madison
# -----------------------------
# Cách A: dùng center + radius (dễ nhất)
CENTER_LAT = 43.0731   # gần downtown/capitol Madison
CENTER_LNG = -89.4012
RADIUS_M = 3500        # tăng/giảm tùy mức "trung tâm" bạn muốn

# Cách B: dùng bounding box (nếu muốn control sát như ảnh)
USE_BOUNDING_BOX = False
BBOX = {
    "lat_min": 43.0570,
    "lng_min": -89.4450,
    "lat_max": 43.0930,
    "lng_max": -89.3550,
}

# -----------------------------
# 2) Category của bạn (để tham chiếu / lọc local sau này)
# -----------------------------
USER_CATEGORIES = [
    "restaurant", "bar", "cafe", "coffee", "pizza", "brewery", "food",
    "nightclub", "music venue", "concert", "theater", "entertainment",
    "sports bar", "pub", "lounge", "comedy", "arcade", "bowling",
    "museum", "gallery"
]

# Nếu muốn thử lọc type trực tiếp bằng BestTime (có thể mismatch):
# NOTE: BestTime có thể không nhận đúng hết các label này.
USE_BESTTIME_TYPES_FILTER = False
BESTTIME_TYPES = "RESTAURANT,CAFE,BAR,FOOD,PUB,BREWERY,NIGHTCLUB,MUSEUM,GALLERY"

# Pagination
PAGE_SIZE = 100   # nếu API báo lỗi, giảm xuống 50 hoặc 20
MAX_PAGES = 50    # chặn an toàn

# Foot traffic mode:
# - "limited": nhẹ hơn
# - "both": debug dễ hơn (có day_raw + day_raw_whole)
FOOT_TRAFFIC_MODE = "both"

# Time mode:
# - now=true => lấy giờ hiện tại local khu vực
USE_NOW = True

# Nếu không dùng now=true, có thể set day/hour:
DAY_INT = 5       # 0=Mon ... 6=Sun
HOUR_MIN = 18
HOUR_MAX = 23


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_json(data, filename):
    path = OUT_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Saved: {path}")
    return path


def build_filter_params(page: int):
    params = {
        "api_key_private": API_KEY,
        "foot_traffic": FOOT_TRAFFIC_MODE,
        "limit": PAGE_SIZE,
        "page": page,
    }

    # Geo filter
    if USE_BOUNDING_BOX:
        params.update(BBOX)
    else:
        params.update({
            "lat": CENTER_LAT,
            "lng": CENTER_LNG,
            "radius": RADIUS_M,
        })

    # Time filter
    if USE_NOW:
        params["now"] = "true"
    else:
        params["day_int"] = DAY_INT
        params["hour_min"] = HOUR_MIN
        params["hour_max"] = HOUR_MAX

    # Optional BestTime type filter
    if USE_BESTTIME_TYPES_FILTER:
        params["types"] = BESTTIME_TYPES

    return params


def extract_venue_key(v):
    """
    Tạo key để dedupe venue giữa các page.
    Ưu tiên venue_id, fallback name+lat+lng
    """
    venue_id = v.get("venue_id")
    if venue_id:
        return f"id::{venue_id}"

    name = v.get("venue_name") or ""
    lat = v.get("venue_lat")
    lng = v.get("venue_lng")
    return f"fallback::{name}::{lat}::{lng}"


def fetch_all_pages():
    url = f"{BASE}/venues/filter"
    all_venues = []
    seen = set()
    page_responses = []

    print("=== BestTime Venue Filter: Central Madison ===")
    print(f"USE_BOUNDING_BOX={USE_BOUNDING_BOX}")
    if not USE_BOUNDING_BOX:
        print(f"center=({CENTER_LAT}, {CENTER_LNG}), radius={RADIUS_M}m")
    else:
        print(f"bbox={BBOX}")

    print(f"USE_NOW={USE_NOW}, FOOT_TRAFFIC_MODE={FOOT_TRAFFIC_MODE}")
    print(f"USE_BESTTIME_TYPES_FILTER={USE_BESTTIME_TYPES_FILTER}")
    if USE_BESTTIME_TYPES_FILTER:
        print(f"BESTTIME_TYPES={BESTTIME_TYPES}")
    print("-" * 60)

    for page in range(MAX_PAGES):
        params = build_filter_params(page)
        print(f"\n➡️ Fetch page={page} ...")
        resp = requests.get(url, params=params, timeout=45)
        print("HTTP:", resp.status_code)

        # In lỗi rõ ràng nếu fail
        if resp.status_code >= 400:
            try:
                err_json = resp.json()
                print("Error JSON:", json.dumps(err_json, indent=2, ensure_ascii=False))
            except Exception:
                print("Error text:", resp.text[:1000])
            resp.raise_for_status()

        data = resp.json()
        page_responses.append(data)

        venues = data.get("venues", []) or []
        venues_n = data.get("venues_n")
        status = data.get("status")

        print(f"status={status}, venues_n={venues_n}, returned_this_page={len(venues)}")

        # Lưu raw từng page để bạn soi schema
        save_json(data, f"filter_page_{page}_{timestamp()}.json")

        if not venues:
            print("⏹️ Không còn venue ở page này. Dừng.")
            break

        new_count = 0
        for v in venues:
            k = extract_venue_key(v)
            if k not in seen:
                seen.add(k)
                all_venues.append(v)
                new_count += 1

        print(f"added_new={new_count}, total_unique={len(all_venues)}")

        # Nếu trả ít hơn page size thì gần như hết trang
        if len(venues) < PAGE_SIZE:
            print("⏹️ Page cuối (returned < PAGE_SIZE). Dừng.")
            break

    return {
        "meta": {
            "fetched_at": datetime.now().isoformat(),
            "use_bounding_box": USE_BOUNDING_BOX,
            "bbox": BBOX if USE_BOUNDING_BOX else None,
            "center_lat": None if USE_BOUNDING_BOX else CENTER_LAT,
            "center_lng": None if USE_BOUNDING_BOX else CENTER_LNG,
            "radius_m": None if USE_BOUNDING_BOX else RADIUS_M,
            "use_now": USE_NOW,
            "foot_traffic": FOOT_TRAFFIC_MODE,
            "use_besttime_types_filter": USE_BESTTIME_TYPES_FILTER,
            "besttime_types": BESTTIME_TYPES if USE_BESTTIME_TYPES_FILTER else None,
            "user_categories_reference": USER_CATEGORIES,
            "page_size": PAGE_SIZE,
            "max_pages": MAX_PAGES,
        },
        "venues_count_unique": len(all_venues),
        "venues": all_venues,
    }


def print_quick_preview(aggregated):
    venues = aggregated.get("venues", [])
    print("\n=== QUICK PREVIEW ===")
    print("unique venues:", len(venues))

    for i, v in enumerate(venues[:15], start=1):
        name = v.get("venue_name")
        lat = v.get("venue_lat")
        lng = v.get("venue_lng")
        day_raw = v.get("day_raw", [])
        current_now = day_raw[0] if isinstance(day_raw, list) and day_raw else None
        vtype = v.get("venue_type")
        print(f"{i:02d}. {name} | type={vtype} | lat/lng=({lat},{lng}) | now={current_now}")


if __name__ == "__main__":
    aggregated = fetch_all_pages()

    out_name = f"all_venues_aggregated_{timestamp()}.json"
    save_json(aggregated, out_name)

    print_quick_preview(aggregated)

    print("\nDone. Bạn mở file JSON trong besttime_outputs để xem raw output.")