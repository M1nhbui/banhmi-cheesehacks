import os
import json
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BESTTIME_API_KEY")
if not API_KEY:
    raise ValueError("Thiếu BESTTIME_API_KEY trong file .env")

BASE = "https://besttime.app/api/v1"
OUT_DIR = Path("besttime_outputs")
OUT_DIR.mkdir(exist_ok=True)


def save_json(data, prefix):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"{prefix}_{ts}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Saved raw JSON -> {path}")
    return path


def pretty_print_filter_summary(data):
    venues = data.get("venues", [])
    print("\n=== FILTER SUMMARY ===")
    print("status:", data.get("status"))
    print("venues_n:", data.get("venues_n"))
    print("returned venues:", len(venues))

    for i, v in enumerate(venues[:10], start=1):
        name = v.get("venue_name") or v.get("venue_info", {}).get("venue_name")
        lat = v.get("venue_lat")
        lng = v.get("venue_lng")
        day_raw = v.get("day_raw", [])
        day_info = v.get("day_info", {}) or {}
        current_forecast = day_raw[0] if isinstance(day_raw, list) and len(day_raw) > 0 else None
        day_mean = day_info.get("day_mean")
        day_max = day_info.get("day_max")
        print(f"{i:02d}. {name}")
        print(f"    lat/lng: {lat}, {lng}")
        print(f"    day_raw(now): {day_raw}")
        print(f"    current_forecast_busyness: {current_forecast}")
        print(f"    day_mean={day_mean}, day_max={day_max}")


def pretty_print_live_summary(data):
    print("\n=== LIVE SUMMARY ===")
    print("status:", data.get("status"))
    analysis = data.get("analysis", {})
    venue_info = data.get("venue_info", {})

    print("venue_name:", venue_info.get("venue_name"))
    print("venue_address:", venue_info.get("venue_address"))
    print("venue_id:", venue_info.get("venue_id"))
    print("local_time:", venue_info.get("venue_current_localtime"))
    print("open_status:", venue_info.get("venue_open"))

    print("forecasted_busyness:", analysis.get("venue_forecasted_busyness"))
    print("live_busyness:", analysis.get("venue_live_busyness"))
    print("delta_live_vs_forecast:", analysis.get("venue_live_forecasted_delta"))
    print("live_available:", analysis.get("venue_live_busyness_available"))
    print("forecast_available:", analysis.get("venue_forecast_busyness_available"))


def call_filter_near_madison():
    """
    Filter quanh khu vực nhỏ ở downtown Madison / Capitol.
    Dùng now=true để lấy giờ hiện tại local của khu vực.
    foot_traffic=both để debug dễ hơn (day_raw + day_raw_whole).
    """
    url = f"{BASE}/venues/filter"
    params = {
        "api_key_private": API_KEY,
        "lat": 43.0747,      # gần Wisconsin State Capitol
        "lng": -89.3844,
        "radius": 600,       # mét, nhỏ thôi để test
        "types": "RESTAURANT,CAFE,BAR",
        "now": "true",
        "foot_traffic": "both",
        "limit": 10,
        "page": 0,
    }

    print("\n➡️ Calling Venue Filter...")
    resp = requests.get(url, params=params, timeout=30)
    print("HTTP:", resp.status_code)
    resp.raise_for_status()

    data = resp.json()
    save_json(data, "filter_madison_small")
    pretty_print_filter_summary(data)
    return data


def call_live_for_famous_madison_place():
    """
    Live Traffic cho 1 địa điểm nổi tiếng ở Madison.
    Dùng venue_name + venue_address cho lần test đầu.
    Docs example dùng /forecasts/live (plural).
    """
    # Docs có chỗ ghi /forecast/live nhưng ví dụ dùng /forecasts/live.
    # Ta thử plural trước theo ví dụ docs.
    candidate_urls = [
        f"{BASE}/forecasts/live",
        f"{BASE}/forecast/live",  # fallback nếu API của tài khoản bạn dùng đường này
    ]

    params = {
        "api_key_private": API_KEY,
        "venue_name": "Memorial Union",
        "venue_address": "800 Langdon St, Madison, WI",
    }

    last_error = None
    for url in candidate_urls:
        try:
            print(f"\n➡️ Calling Live Traffic at: {url}")
            # Theo docs example: POST với params trên query string
            resp = requests.post(url, params=params, timeout=30)
            print("HTTP:", resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            save_json(data, "live_memorial_union")
            pretty_print_live_summary(data)
            return data
        except Exception as e:
            print(f"❌ Failed on {url}: {e}")
            last_error = e

    raise RuntimeError(f"Live endpoint failed on both candidate URLs. Last error: {last_error}")


if __name__ == "__main__":
    print("=== BestTime quick test ===")
    print("1) Filter quanh Madison")
    print("2) Live Traffic cho 1 địa điểm nổi tiếng\n")

    try:
        filter_data = call_filter_near_madison()
    except Exception as e:
        print(f"\n[Filter Error] {e}")

    try:
        live_data = call_live_for_famous_madison_place()
    except Exception as e:
        print(f"\n[Live Error] {e}")

    print("\nDone.")