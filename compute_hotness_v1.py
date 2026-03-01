import json
import math
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================
# OPTIONAL H3 IMPORT
# =========================
H3_AVAILABLE = False
try:
    import h3
    H3_AVAILABLE = True
except Exception:
    H3_AVAILABLE = False


# =========================
# CONFIG
# =========================
# Đổi path này thành file bạn muốn chạy:
# - Có thể là raw filter file: filter_madison_small_*.json
# - Hoặc file bulk merged: filter_madison_central_bulk_*.json

# Auto-detect the newest aggregated file; override by setting explicitly below
_candidates = sorted(Path("besttime_outputs").glob("all_venues_aggregated_*.json"), reverse=True)
INPUT_JSON = str(_candidates[0]) if _candidates else "besttime_outputs/all_venues_aggregated.json"
#INPUT_JSON = "besttime_outputs/filter_madison_small_20260228_213948.json"

# Nếu chưa có H3 / chưa muốn dùng H3 area thì set False
USE_H3_AREA = True

# H3 resolution:
# 8 = to hơn, 9 = hợp downtown, 10 = nhỏ hơn
H3_RESOLUTION = 9

# Trọng số v1 (Venue base)
W_FULLNESS = 0.45
W_RELATIVE = 0.30
W_MOMENTUM = 0.15
W_POPULARITY = 0.10

# Trọng số v1 (Venue final = base + area)
W_VENUE_BASE = 0.70
W_AREA = 0.30

# Cell hotness weights
W_CELL_ACTIVITY = 0.60
W_CELL_ACTIVE_RATIO = 0.25
W_CELL_DENSITY = 0.15

ACTIVE_FULLNESS_THRESHOLD = 0.60
CELL_DENSITY_N_REF = 8
CELL_SHRINKAGE_LAMBDA = 3.0

# Neighbor smoothing
USE_NEIGHBOR_SMOOTHING = True
W_CELL_SELF = 0.70
W_CELL_NEIGHBORS = 0.30

# Output
OUT_DIR = Path("besttime_outputs")
OUT_DIR.mkdir(exist_ok=True)


# =========================
# HELPERS
# =========================
def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def log1p_safe(x):
    return math.log1p(max(x, 0))


def ts_now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

"""
def detect_payload_type(data):
    
    Trả về:
    - "bulk" nếu file merged có {meta, summary, pages_meta, venues}
    - "raw_filter" nếu file raw filter có {status, venues, window,...}
    
    if isinstance(data, dict) and "venues" in data and "meta" in data and "pages_meta" in data:
        return "bulk"
    if isinstance(data, dict) and "venues" in data and "status" in data:
        return "raw_filter"
    return "unknown"
"""
def detect_payload_type(data):
    """
    Trả về:
    - "bulk" nếu file merged có venues + meta (có thể có hoặc không có pages_meta)
    - "raw_filter" nếu file raw filter có status + venues + window
    - "venues_list" nếu top-level là list venues
    """
    if isinstance(data, dict) and "venues" in data and "status" in data:
        return "raw_filter"

    # bulk mới / bulk cũ đều nhận
    if isinstance(data, dict) and "venues" in data and "meta" in data:
        return "bulk"

    if isinstance(data, list):
        return "venues_list"

    return "unknown"
"""
def extract_venues_and_window(data):
    payload_type = detect_payload_type(data)

    if payload_type == "bulk":
        venues = data.get("venues", [])
        pages_meta = data.get("pages_meta", [])
        # Lấy window từ page đầu tiên có window
        window = {}
        for p in pages_meta:
            w = p.get("window") or {}
            if w:
                window = w
                break
        return venues, window, payload_type

    if payload_type == "raw_filter":
        venues = data.get("venues", [])
        window = data.get("window") or {}
        return venues, window, payload_type

    raise ValueError("Không nhận diện được format JSON. Hãy dùng raw filter hoặc bulk merged file.")
"""
def extract_venues_and_window(data):
    payload_type = detect_payload_type(data)

    if payload_type == "bulk":
        venues = data.get("venues", [])
        window = {}

        # Ưu tiên lấy từ pages_meta (format cũ)
        pages_meta = data.get("pages_meta", [])
        if isinstance(pages_meta, list):
            for p in pages_meta:
                w = p.get("window") or {}
                if w:
                    window = w
                    break

        # Nếu không có pages_meta, thử lấy từ meta (format bạn đang có)
        if not window:
            meta = data.get("meta", {})
            if isinstance(meta, dict):
                # thử nhiều key khả dĩ
                window = (
                    meta.get("window")
                    or meta.get("besttime_window")
                    or {}
                )

        return venues, window, payload_type

    if payload_type == "raw_filter":
        venues = data.get("venues", [])
        window = data.get("window") or {}
        return venues, window, payload_type

    if payload_type == "venues_list":
        venues = data
        window = {}
        return venues, window, payload_type

    raise ValueError("Không nhận diện được format JSON. Hãy dùng raw filter hoặc bulk merged file.")

def get_time_local_info(window):
    """
    BestTime thường trả window.time_local và window.time_local_index.
    Fallback nếu thiếu.
    """
    time_local = window.get("time_local")
    time_local_index = window.get("time_local_index")

    # Fallback nếu file không có window đầy đủ
    if time_local is None:
        time_local = 0
    if time_local_index is None:
        # Nếu thiếu index, tạm dùng giờ local (không hoàn hảo nhưng đủ fallback)
        time_local_index = int(time_local) % 24

    return int(time_local), int(time_local_index)


def get_current_busyness(venue, time_local_index):
    """
    Ưu tiên day_raw[0] (khi now=true), fallback day_raw_whole[time_local_index]
    """
    day_raw = venue.get("day_raw") or []
    if isinstance(day_raw, list) and len(day_raw) > 0 and isinstance(day_raw[0], (int, float)):
        return float(day_raw[0])

    whole = venue.get("day_raw_whole") or []
    if isinstance(whole, list) and len(whole) > time_local_index and isinstance(whole[time_local_index], (int, float)):
        return float(whole[time_local_index])

    return 0.0


def get_prev_forecast_busyness(venue, time_local_index):
    """
    Lấy điểm forecast trước đó từ day_raw_whole (cyclic 24h).
    Đây là FORECAST momentum, không phải live momentum.
    """
    whole = venue.get("day_raw_whole") or []
    if not isinstance(whole, list) or len(whole) == 0:
        return None

    idx = time_local_index % len(whole)
    prev_idx = (idx - 1) % len(whole)

    try:
        return float(whole[prev_idx])
    except Exception:
        return None


def popularity_score(rating, reviews, review_cap=5000):
    rating_norm = clip((rating or 0) / 5.0)
    reviews_norm = clip(log1p_safe(reviews or 0) / log1p_safe(review_cap))
    return rating_norm * reviews_norm


def is_open_now_from_besttime(venue, current_hour_local):
    """
    Dùng day_info.venue_open_close_v2['24h'] nếu có.
    Nếu thiếu thì fallback = 1 (để không làm rớt venue vô lý).
    """
    day_info = venue.get("day_info") or {}
    oc_v2 = (day_info.get("venue_open_close_v2") or {})
    slots = oc_v2.get("24h", [])

    if not slots:
        # fallback: không có info giờ mở cửa -> tạm coi là mở
        return 1

    h = int(current_hour_local) % 24

    for slot in slots:
        opens = slot.get("opens")
        closes = slot.get("closes")
        if opens is None or closes is None:
            continue

        opens = int(opens)
        closes = int(closes)

        # case qua nửa đêm, ví dụ 17 -> 1
        if opens > closes:
            if h >= opens or h < closes:
                return 1
        else:
            if opens <= h < closes:
                return 1

    return 0


def compute_venue_base_hotness(venue, current_hour_local, time_local_index):
    current = get_current_busyness(venue, time_local_index)
    day_info = venue.get("day_info") or {}
    day_mean = float(day_info.get("day_mean") or 0)

    # A) Fullness
    fullness_score = clip(current / 100.0)

    # B) Relative (so với day_mean)
    rel_ratio = current / max(day_mean, 1.0)
    relative_score = clip(rel_ratio / 1.5)

    # C) Expected momentum (forecast slope)
    prev_forecast = get_prev_forecast_busyness(venue, time_local_index)
    if prev_forecast is None:
        expected_momentum_score = 0.0
    else:
        delta = max(0.0, current - prev_forecast)
        # chia 40 để scale tương đối (tune sau)
        expected_momentum_score = clip(delta / 40.0)

    # D) Popularity prior (nhẹ)
    pop_score = popularity_score(
        rating=venue.get("rating"),
        reviews=venue.get("reviews")
    )

    # E) Open now gate
    open_now = is_open_now_from_besttime(venue, current_hour_local)

    base = open_now * (
        W_FULLNESS * fullness_score +
        W_RELATIVE * relative_score +
        W_MOMENTUM * expected_momentum_score +
        W_POPULARITY * pop_score
    )

    return {
        "open_now": int(open_now),
        "current_busyness": round(current, 4),
        "day_mean": round(day_mean, 4),
        "fullness_score": round(fullness_score, 6),
        "relative_score": round(relative_score, 6),
        "expected_momentum_score": round(expected_momentum_score, 6),
        "popularity_score": round(pop_score, 6),
        "venue_base_hotness": round(clip(base), 6),
    }


# =========================
# H3 HELPERS (optional)
# =========================
def h3_latlng_to_cell(lat, lng, res):
    """Hỗ trợ cả h3 v3/v4 API."""
    if not H3_AVAILABLE:
        return None
    try:
        # h3 v4
        return h3.latlng_to_cell(lat, lng, res)
    except Exception:
        try:
            # h3 v3
            return h3.geo_to_h3(lat, lng, res)
        except Exception:
            return None


def h3_neighbors(cell):
    """Hỗ trợ cả h3 v3/v4 API."""
    if not H3_AVAILABLE or cell is None:
        return []
    try:
        # h3 v4
        return list(h3.grid_disk(cell, 1))
    except Exception:
        try:
            # h3 v3
            return list(h3.k_ring(cell, 1))
        except Exception:
            return []


# =========================
# MAIN PIPELINE
# =========================
def enrich_venues_with_base_hotness(venues, current_hour_local, time_local_index):
    enriched = []
    for v in venues:
        vv = dict(v)
        hot = compute_venue_base_hotness(vv, current_hour_local, time_local_index)
        vv["hotness_v1"] = hot

        # thêm H3 cell nếu dùng H3
        lat = vv.get("venue_lat")
        lng = vv.get("venue_lng")
        if USE_H3_AREA and H3_AVAILABLE and isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            vv["h3_cell"] = h3_latlng_to_cell(float(lat), float(lng), H3_RESOLUTION)
        else:
            vv["h3_cell"] = None

        enriched.append(vv)
    return enriched


def compute_area_hotness_h3(enriched_venues):
    """
    Tính cell_hotness từ venue_base_hotness.
    Có shrinkage + optional neighbor smoothing.
    """
    # group by cell
    cell_to_venues = defaultdict(list)
    for v in enriched_venues:
        cell = v.get("h3_cell")
        if cell:
            cell_to_venues[cell].append(v)

    if not cell_to_venues:
        return {}, {}

    # raw cell features
    cell_raw = {}
    for cell, vs in cell_to_venues.items():
        n = len(vs)
        if n == 0:
            continue

        base_vals = [float(v["hotness_v1"]["venue_base_hotness"]) for v in vs]
        fullness_vals = [float(v["hotness_v1"]["fullness_score"]) for v in vs]

        cell_activity = sum(base_vals) / max(len(base_vals), 1)
        cell_active_ratio = sum(1 for x in fullness_vals if x >= ACTIVE_FULLNESS_THRESHOLD) / max(len(fullness_vals), 1)
        cell_density = clip(n / CELL_DENSITY_N_REF)

        cell_hotness_raw = (
            W_CELL_ACTIVITY * cell_activity +
            W_CELL_ACTIVE_RATIO * cell_active_ratio +
            W_CELL_DENSITY * cell_density
        )

        cell_raw[cell] = {
            "n_venues": n,
            "cell_activity": cell_activity,
            "cell_active_ratio": cell_active_ratio,
            "cell_density": cell_density,
            "cell_hotness_raw": cell_hotness_raw
        }

    # city baseline để shrinkage
    raw_vals = [x["cell_hotness_raw"] for x in cell_raw.values()]
    city_mean_cell_hotness = sum(raw_vals) / max(len(raw_vals), 1)

    # shrinkage
    cell_shrunk = {}
    for cell, d in cell_raw.items():
        n = d["n_venues"]
        raw = d["cell_hotness_raw"]
        lam = CELL_SHRINKAGE_LAMBDA

        shrunk = (n / (n + lam)) * raw + (lam / (n + lam)) * city_mean_cell_hotness
        cell_shrunk[cell] = {
            **d,
            "city_mean_cell_hotness": city_mean_cell_hotness,
            "cell_hotness_shrunk": shrunk,
        }

    # optional neighbor smoothing
    cell_final = {}
    if USE_NEIGHBOR_SMOOTHING and H3_AVAILABLE:
        for cell, d in cell_shrunk.items():
            neighs = [c for c in h3_neighbors(cell) if c != cell and c in cell_shrunk]
            if neighs:
                neigh_mean = sum(cell_shrunk[n]["cell_hotness_shrunk"] for n in neighs) / len(neighs)
            else:
                neigh_mean = d["cell_hotness_shrunk"]

            smoothed = W_CELL_SELF * d["cell_hotness_shrunk"] + W_CELL_NEIGHBORS * neigh_mean
            cell_final[cell] = {
                **d,
                "neighbor_count_used": len(neighs),
                "neighbor_mean_hotness": neigh_mean,
                "cell_hotness_smoothed": smoothed
            }
    else:
        for cell, d in cell_shrunk.items():
            cell_final[cell] = {
                **d,
                "neighbor_count_used": 0,
                "neighbor_mean_hotness": d["cell_hotness_shrunk"],
                "cell_hotness_smoothed": d["cell_hotness_shrunk"]
            }

    return cell_final, cell_to_venues


def attach_final_hotness(enriched_venues, cell_final):
    out = []
    for v in enriched_venues:
        vv = dict(v)
        base = float(vv["hotness_v1"]["venue_base_hotness"])
        cell = vv.get("h3_cell")

        if cell and cell in cell_final:
            area_hot = clip(float(cell_final[cell]["cell_hotness_smoothed"]))
            final = clip(W_VENUE_BASE * base + W_AREA * area_hot)
            vv["hotness_v1"]["area_hotness_smoothed"] = round(area_hot, 6)
        else:
            area_hot = None
            final = clip(base)
            vv["hotness_v1"]["area_hotness_smoothed"] = None

        vv["hotness_v1"]["venue_hotness_final"] = round(final, 6)
        out.append(vv)

    return out


def build_flat_rows(enriched_venues):
    rows = []
    for v in enriched_venues:
        h = v.get("hotness_v1", {})
        rows.append({
            "venue_id": v.get("venue_id"),
            "venue_name": v.get("venue_name"),
            "venue_type": v.get("venue_type"),
            "venue_lat": v.get("venue_lat"),
            "venue_lng": v.get("venue_lng"),
            "rating": v.get("rating"),
            "reviews": v.get("reviews"),
            "price_level": v.get("price_level"),
            "h3_cell": v.get("h3_cell"),
            "open_now": h.get("open_now"),
            "current_busyness": h.get("current_busyness"),
            "day_mean": h.get("day_mean"),
            "fullness_score": h.get("fullness_score"),
            "relative_score": h.get("relative_score"),
            "expected_momentum_score": h.get("expected_momentum_score"),
            "popularity_score": h.get("popularity_score"),
            "venue_base_hotness": h.get("venue_base_hotness"),
            "area_hotness_smoothed": h.get("area_hotness_smoothed"),
            "venue_hotness_final": h.get("venue_hotness_final"),
        })
    rows.sort(key=lambda x: (x["venue_hotness_final"] is not None, x["venue_hotness_final"]), reverse=True)
    return rows


def save_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_top(rows, topn=20):
    print(f"\n=== TOP {topn} VENUES BY venue_hotness_final ===")
    for i, r in enumerate(rows[:topn], start=1):
        print(
            f"{i:02d}. {r['venue_name']} "
            f"| final={r['venue_hotness_final']:.3f} "
            f"| base={r['venue_base_hotness']:.3f} "
            f"| area={r['area_hotness_smoothed'] if r['area_hotness_smoothed'] is not None else 'NA'} "
            f"| full={r['current_busyness']} "
            f"| mean={r['day_mean']} "
            f"| open={r['open_now']}"
        )


def main():
    input_path = Path(INPUT_JSON)
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {input_path}")

    data = load_json(input_path)
    venues, window, payload_type = extract_venues_and_window(data)
    current_hour_local, time_local_index = get_time_local_info(window)

    print("=== HOTNESS V1 (Filter-only) ===")
    print("Input file:", input_path)
    print("Payload type:", payload_type)
    print("Venues:", len(venues))
    print("Window:", window if window else "(none found)")
    print("current_hour_local:", current_hour_local)
    print("time_local_index:", time_local_index)
    print("H3 enabled:", USE_H3_AREA, "| H3 available:", H3_AVAILABLE)

    # 1) Venue base hotness
    enriched = enrich_venues_with_base_hotness(venues, current_hour_local, time_local_index)

    # 2) Area hotness (optional H3)
    if USE_H3_AREA and H3_AVAILABLE:
        cell_final, _ = compute_area_hotness_h3(enriched)
    else:
        cell_final = {}

    # 3) Final hotness
    enriched = attach_final_hotness(enriched, cell_final)

    # 4) Flat rows + sort
    rows = build_flat_rows(enriched)

    # 5) Save outputs
    run_ts = ts_now()
    out_json = OUT_DIR / f"hotness_v1_enriched_{run_ts}.json"
    out_csv = OUT_DIR / f"hotness_v1_ranked_{run_ts}.csv"
    out_cells = OUT_DIR / f"hotness_v1_h3_cells_{run_ts}.json"

    payload_out = {
        "meta": {
            "input_file": str(input_path),
            "payload_type": payload_type,
            "window": window,
            "current_hour_local": current_hour_local,
            "time_local_index": time_local_index,
            "use_h3_area": USE_H3_AREA,
            "h3_available": H3_AVAILABLE,
            "h3_resolution": H3_RESOLUTION if (USE_H3_AREA and H3_AVAILABLE) else None,
            "weights": {
                "venue": {
                    "fullness": W_FULLNESS,
                    "relative": W_RELATIVE,
                    "expected_momentum": W_MOMENTUM,
                    "popularity": W_POPULARITY,
                },
                "final": {
                    "venue_base": W_VENUE_BASE,
                    "area": W_AREA,
                },
                "cell": {
                    "activity": W_CELL_ACTIVITY,
                    "active_ratio": W_CELL_ACTIVE_RATIO,
                    "density": W_CELL_DENSITY,
                }
            }
        },
        "venues": enriched
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload_out, f, ensure_ascii=False, indent=2)

    save_csv(rows, out_csv)

    if cell_final:
        with open(out_cells, "w", encoding="utf-8") as f:
            json.dump(cell_final, f, ensure_ascii=False, indent=2)
    else:
        out_cells = None

    print_top(rows, topn=20)

    print("\n✅ DONE")
    print("Saved JSON:", out_json)
    print("Saved CSV :", out_csv)
    if out_cells:
        print("Saved H3 cells:", out_cells)


if __name__ == "__main__":
    main()