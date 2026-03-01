"""One-shot script: add hotness + crowd to every event in data/events.json."""
import json, pathlib, numpy as np

HOTNESS_CROWD = {
    # ── Big / stadium events ──────────────────────────────────────────────────
    "demo_event_038": (0.96, 0.94),  # Camp Randall Stadium Concert
    "demo_event_010": (0.92, 0.91),  # State Street Spring Block Party
    "demo_event_008": (0.88, 0.85),  # UW Badgers Basketball Game
    "demo_event_048": (0.85, 0.82),  # Downtown Madison Pride Parade
    "demo_event_037": (0.82, 0.80),  # Badger Tailgate at Union South
    # ── High-energy / well-attended ───────────────────────────────────────────
    "demo_event_020": (0.78, 0.72),  # UW Memorial Union Terrace Live Music
    "demo_event_006": (0.74, 0.70),  # Great Dane Downtown Beer Fest
    "demo_event_025": (0.73, 0.76),  # Madison Night Market on State Street
    "demo_event_003": (0.72, 0.68),  # Indie Rock Show at The Sylvee
    "demo_event_011": (0.71, 0.65),  # Monona Terrace Rooftop Concert
    "demo_event_016": (0.70, 0.68),  # Breese Stevens Field Soccer Match
    # ── Medium-popular ────────────────────────────────────────────────────────
    "demo_event_036": (0.68, 0.65),  # Williamson Street Block Party
    "demo_event_015": (0.65, 0.60),  # Capitol Square Art Fair
    "demo_event_043": (0.60, 0.55),  # Henry Vilas Zoo After-Hours Adult Night
    "demo_event_001": (0.58, 0.62),  # Madison Winter Farmers Market
    "demo_event_046": (0.56, 0.54),  # State Street Buskers Showcase
    "demo_event_013": (0.56, 0.55),  # East Side Food Truck Rally
    "demo_event_028": (0.55, 0.60),  # Middleton Good Neighbor Festival Parade
    "demo_event_019": (0.55, 0.57),  # Atwood Avenue Porch Fest
    "demo_event_022": (0.52, 0.50),  # Hilldale Summer Night Market
    "demo_event_039": (0.52, 0.48),  # Olbrich Gardens Summer Concert Series
    "demo_event_000": (0.52, 0.45),  # Live Jazz Night at The Bur Oak
    "demo_event_018": (0.50, 0.52),  # Tenney Park Winter Skate Night
    "demo_event_033": (0.50, 0.58),  # Madison Children's Museum Free Family Night
    # ── Medium-low (casual / niche / bar nights) ──────────────────────────────
    "demo_event_017": (0.48, 0.38),  # Madison Craft Coffee Crawl
    "demo_event_041": (0.48, 0.50),  # Cap Centre Ice Public Skate DJ Night
    "demo_event_050": (0.48, 0.30),  # Capitol City Beer & Cheese Pairing
    "demo_event_021": (0.44, 0.38),  # Monroe Street Wine Walk
    "demo_event_005": (0.46, 0.48),  # Comedy Open Mic at Comedy on State
    "demo_event_027": (0.46, 0.42),  # Madison Jazz Jam at Cafe Coda
    "demo_event_035": (0.44, 0.46),  # Elver Park Sledding Party
    "demo_event_040": (0.44, 0.46),  # State Street Improv Comedy Night
    "demo_event_002": (0.44, 0.50),  # Trivia Night at Merchant
    "demo_event_032": (0.45, 0.42),  # Union South Outdoor Film Series
    "demo_event_009": (0.42, 0.45),  # Outdoor Film Screening at Vilas Park
    "demo_event_042": (0.42, 0.40),  # Madison Makers Spring Craft Fair
    "demo_event_047": (0.42, 0.18),  # Monona Bubbler Boats & Brunch (small group)
    "demo_event_023": (0.43, 0.36),  # Downtown Madison Gallery Night
    "demo_event_014": (0.41, 0.35),  # Barrymore Theater Film Festival Night
    "demo_event_034": (0.40, 0.38),  # Madison Vegan Pop-Up Market
    # ── Low / relaxed / quiet ────────────────────────────────────────────────
    "demo_event_007": (0.39, 0.32),  # Yoga & Wine Night at Olbrich Gardens
    "demo_event_012": (0.38, 0.18),  # Lake Mendota Sunset Paddle (small group)
    "demo_event_045": (0.38, 0.35),  # Madison Science Pub at Local Brewery
    "demo_event_030": (0.35, 0.28),  # Wingra Park Canoe Rentals & Music
    "demo_event_029": (0.34, 0.40),  # Monona Lake Loop Fun Run
    "demo_event_031": (0.32, 0.22),  # State Capitol Building Night Tour
    "demo_event_026": (0.30, 0.24),  # Warner Park Community Drum Circle
    "demo_event_004": (0.28, 0.22),  # Yoga in the Park at Tenney Park
    "demo_event_049": (0.28, 0.16),  # Madison Lakes Astronomy Night
    "demo_event_024": (0.26, 0.18),  # Olin Park Lakeside Yoga
    "demo_event_044": (0.22, 0.30),  # Library Late Night Study & Snacks
}

path = pathlib.Path(__file__).parent / "data" / "events.json"
events = json.loads(path.read_text())

missing = []
for ev in events:
    sid = ev["source_id"]
    if sid in HOTNESS_CROWD:
        ev["hotness"] = HOTNESS_CROWD[sid][0]
        ev["crowd"]   = HOTNESS_CROWD[sid][1]
    else:
        missing.append(sid)

if missing:
    print("WARNING — no mapping for:", missing)

path.write_text(json.dumps(events, indent=2, ensure_ascii=False))

hs = [e["hotness"] for e in events]
cs = [e["crowd"]   for e in events]
print(f"Patched {len(events)} events  (missing={len(missing)})")
print(f"hotness  min={min(hs):.2f}  max={max(hs):.2f}  mean={sum(hs)/len(hs):.2f}  std={float(np.std(hs)):.2f}")
print(f"crowd    min={min(cs):.2f}  max={max(cs):.2f}  mean={sum(cs)/len(cs):.2f}  std={float(np.std(cs)):.2f}")
