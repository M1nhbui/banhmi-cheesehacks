# Madison Interest Map (Keyword-Driven Scoring)

An end-to-end backend that ingests **places** and **events** for **Madison, WI**, enriches each row with **weather**, computes a **keyword-to-description correlation** (cosine similarity), plus **popularity**, **weather**, and **urgency** signals, then returns a **final ranked table** of scored map points for a frontend interactive map.

> Goal: keep the system simple, explainable, and easy to extend when you plug in additional real-time data sources.

---

## Demo scope

* **City:** Madison, WI only (fixed bounding box).
* **User:** single demo user — only input is a keyword list at request time.
* **Entities:** two types:

  * **Place** (1,708 real Foursquare venues): has rating/reviews, `open`/`close` hours, static info.
  * **Event** (15 hand-crafted): has `event_start`/`event_end`; urgency builds before the event starts and decays as it winds down.
* **No personalization:** the only user input is a list of keywords.
* **Data files:** `data/places.json` and `data/events.json` — swap either file to update the dataset without touching code.

---

## What the frontend receives

The backend returns a list of rows sorted by `score` descending. Each row is ready to plot as a map marker:

* `name`
* `lat`, `lon`
* `address`
* `description`
* `score` — **min-max normalised to `[0, 1]`** across all returned results (see [Final score](#final-score))

Optional debug/UI fields:

* `type` (`place` or `event`)
* `breakdown` (raw component scores: similarity / popularity / weather / urgency)

---

## Architecture at a glance

### Offline / batch pipeline

1. **Ingest places** from online sources → normalize into schema.
2. **Ingest events** from online sources → normalize into schema.
3. **Enrich weather** at each entity coordinate.
4. **Compute enriched features** (popularity/weather; urgency can be runtime).

Output:

* `entities_raw` → normalized, source-agnostic rows
* `entities_enriched` → rows with computed numeric features

### Runtime API

1. User sends **keyword list**.
2. Backend computes **cosine similarity** between keywords and entity descriptions.
3. Backend combines similarity + popularity + weather + urgency → `final_score`.
4. Backend returns the **final table** to the frontend.

---

## Data model (schema)

The system uses a unified concept called an **Entity**.

### 1) `entities_raw` (canonical normalized rows)

Each row is either a **place** or an **event**.

| Field          | Type        | Description                                                |
| -------------- | ----------- | ---------------------------------------------------------- |
| `entity_id`    | string      | Unique id (numeric string for Foursquare data, UUID otherwise) |
| `entity_type`  | enum        | `place` or `event`                                         |
| `source`       | string      | `foursquare`, `manual`, etc.                               |
| `source_id`    | string      | Unique id from the source                                  |
| `name`         | string      | Display name                                               |
| `lat` / `lon`  | float       | Coordinates                                                |
| `address`      | string      | One-line address for UI                                    |
| `description`  | string      | Main text used for keyword similarity                      |
| `categories`   | list or string | Tags/categories — JSON array preferred; comma-string also accepted |
| `rating`       | float?      | 0–5 (nullable; mostly for places)                          |
| `review_count` | int?        | Popularity proxy (nullable)                                |
| `price_tier`   | int?        | 1–4, like $ to $$$$ (nullable)                             |
| `event_start`  | datetime?   | ISO 8601, UTC — events only                                |
| `event_end`    | datetime?   | ISO 8601, UTC — events only                                |
| `open`         | string?     | `HH:MM` local open time, e.g. `"09:00"` — places only      |
| `close`        | string?     | `HH:MM` local close time, e.g. `"23:00"` — places only     |
| `created_at`   | date/datetime | Row created (`YYYY-MM-DD` or ISO 8601)                   |
| `updated_at`   | date/datetime | Row last updated                                         |

**Important:** Keep `description` intentionally rich (categories + vibe words + short summary). This is what makes keyword similarity meaningful.

### 2) Weather enrichment

For simplicity, weather can be stored **inside** each row after enrichment.

* `weather_temp_f`
* `weather_precip_prob` (0..1)
* `weather_wind_mph`
* `weather_condition`
* `weather_updated_at`

(You can later normalize this into a separate weather table keyed by grid/time buckets.)

### 3) `entities_enriched` (raw + derived numeric features)

This is `entities_raw` plus computed fields:

* `popularity_score` (0..1)
* `weather_score` (0..1)
* `urgency_score` (0..1; events only; can be computed at runtime)
* `is_active_event` (boolean)

---

## Scoring design

Each entity gets 4 component scores, all normalized to **0..1**.

### 1) Correlation score (keyword ⇄ description)

* Tokenize descriptions.
* Tokenize user keywords.
* Build TF-IDF vectors.
* Compute cosine similarity.

Output:

* `correlation_score ∈ [0,1]`

### 2) Popularity score (rating + reviews)

Typical normalization:

* `rating_score = rating / 5`
* `count_score = log(1 + review_count) / log(1 + cap)`
* `popularity_score = 0.7 * rating_score + 0.3 * count_score`

If rating/reviews are missing (common for some event sources), you can default to a neutral value (e.g. `0.5`).

### 3) Weather score (per entity coordinate)

Compute a simple score from:

* temperature closeness to a comfortable range
* low precipitation probability
* low wind

Output:

* `weather_score ∈ [0,1]`

### 4) Urgency score (events + venues)

Urgency measures how time-sensitive it is to act on an entity *right now*. The score is driven by **exponential decay** using configurable time constants.

#### Events (`event_start` / `event_end` present)

Three phases:

| Phase | Condition | Score |
|---|---|---|
| Too early | `now < event_start` and `delta > H_start` | `0.0` |
| Pre-start build-up | `now < event_start` and `delta ≤ H_start` | `exp(-delta / tau_start)` |
| Live wind-down | `event_start ≤ now < event_end` | `exp(-remaining / tau_event_end)` |
| Ended | `now ≥ event_end` | `0.0` |

Where:
* `delta` = seconds until `event_start`
* `remaining` = seconds until `event_end`

#### Venues / places (`open` / `close` hours present)

* If the venue is closed right now → `0.0`
* If open: `urgency = exp(-remaining_until_close / tau_venue_close)`

Rises as closing time approaches; handles overnight hours (e.g. `open=22:00`, `close=02:00`).

#### Config defaults (`config.py`)

| Constant | Default | Meaning |
|---|---|---|
| `URGENCY_H_START_S` | `21600` (6 h) | Lookahead window before event start |
| `URGENCY_TAU_START_S` | `5400` (90 min) | Pre-start decay time constant |
| `URGENCY_TAU_EVENT_END_S` | `3600` (60 min) | Live wind-down decay time constant |
| `URGENCY_TAU_VENUE_CLOSE_S` | `3600` (60 min) | Venue closing-time decay constant |

### Final score

Weights (configured in `config.py`, must sum to 1.0):

* `w_corr = 0.45`
* `w_pop = 0.25`
* `w_weather = 0.15`
* `w_urgency = 0.15`

Step 1 — weighted sum:

```
raw_score = w_corr    * correlation_score
          + w_pop     * popularity_score
          + w_weather * weather_score
          + w_urgency * urgency_score
```

Step 2 — **min-max normalization** across all results in the response:

```
score = (raw_score - min(raw_scores)) / (max(raw_scores) - min(raw_scores))
```

This stretches the final scores so the best result always maps to `1.0` and the worst to `0.0`, giving the frontend a full `[0, 1]` gradient regardless of the keyword query.  
The `breakdown` sub-scores returned per row are the **raw (pre-normalization)** component values.

---

## Workflow (how you’ll build it)

### Step 1: Define Madison boundary

Create a config for:

* `min_lat, min_lon, max_lat, max_lon`

Use it to:

* validate incoming data
* filter entities to Madison

### Step 2: Ingest data into `entities_raw`

Data is loaded from two JSON files in `data/`:

* **`data/places.json`** — 1,708 real Foursquare venues for Madison, WI (schema as above, including `open`/`close`).
* **`data/events.json`** — 15 hand-crafted Madison events with real venue coordinates.

To swap in a different dataset, replace either JSON file. The loader (`fake_data.py`) handles:

* `categories` as either a JSON array or a comma-separated string
* `entity_id` as either a numeric string (Foursquare) or UUID
* `created_at`/`updated_at` as either `YYYY-MM-DD` date strings or full ISO 8601 datetimes

**Places sources (for future replacement):** Foursquare, Google Places, Yelp, OSM

**Event sources (for future replacement):** Eventbrite, Ticketmaster, city calendars, UW events

### Step 3: Weather enrichment

Two options:

* **Simple:** attach the same city-wide weather snapshot to all rows.
* **Better:** attach weather per coordinate (nearest grid point), cached by time bucket.

### Step 4: Compute enriched features

* popularity_score (precompute)
* weather_score (precompute)
* urgency_score (compute at runtime for accuracy, or precompute as snapshot)

### Step 5: Runtime scoring API

* Input: `keywords: string[]`
* Process: compute correlation + combine with other signals
* Output: final table rows with `score`

### Step 6: Frontend map

* fetch scored rows
* plot markers at `(lat, lon)`
* marker size/color based on `score`
* popup shows name/address/description and optionally breakdown

---

## Example API contract

### Request

`POST /score`

```json
{
  "keywords": ["ramen", "coffee", "cozy", "quiet", "study-friendly"]
}
```

### Response

```json
{
  "meta": {
    "city": "Madison, WI",
    "keywords": ["ramen", "coffee", "cozy"],
    "rows_returned": 1565
  },
  "rows": [
    {
      "name": "Yola's Café & Coffee Shop of Madison",
      "type": "place",
      "lat": 43.05551,
      "lon": -89.52325,
      "address": "7463 Mineral Point Rd, Madison, WI 53717",
      "description": "Café, Coffee Shop. cozy, quiet, study-friendly...",
      "score": 1.0,
      "breakdown": {
        "similarity": 0.72,
        "popularity": 0.81,
        "weather": 0.64,
        "urgency": 0.00
      }
    }
  ]
}
```

> **Note:** `score` is min-max normalised across all rows in the response (`1.0` = best match for this query). `breakdown` values are the raw pre-normalisation component scores.

---

## Extending the project later

Once the demo works, you can improve it without changing the core concept:

* Replace fake datasets with real APIs.
* Add a real DB (Postgres/PostGIS) to store entities and query by bounds.
* Add a city grid/tiling strategy for efficient weather + event lookups.
* Add better text embeddings (e.g., sentence transformers) instead of TF-IDF.

---

## License

MIT (or choose your preferred license).
