# Madison Interest Map (Keyword-Driven Scoring)

An end-to-end demo project that ingests **places** and **events** for **Madison, WI**, enriches each row with **weather**, computes a **keyword-to-description correlation** (cosine similarity), plus **popularity** and **urgency** signals, then returns a **final table** of scored map points for a frontend interactive map.

> Goal: keep the system simple, explainable, and easy to extend later when you plug in real online data sources.

---

## Demo scope

* **City:** Madison, WI only (fixed boundary).
* **User:** single demo user (or a request-time keyword list).
* **Entities:** two types of rows:

  * **Place**: has rating/reviews, static info.
  * **Event**: has start/end times; urgency increases as the event is closer to ending.
* **No personalization:** the only user input is a list of keywords.

---

## What the frontend receives

The backend returns a list of rows. Each row is already scored and is ready to plot as a marker:

* `name`
* `lat`, `lon`
* `address`
* `description`
* `score` (0..1)

Optional debug/UI fields:

* `type` (`place` or `event`)
* `breakdown` (similarity/popularity/weather/urgency)

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

| Field          | Type        | Description                            |
| -------------- | ----------- | -------------------------------------- |
| `entity_id`    | string/uuid | Internal unique id                     |
| `entity_type`  | enum        | `place` or `event`                     |
| `source`       | string      | `yelp`, `osm`, `eventbrite`, etc.      |
| `source_id`    | string      | Unique id from the source              |
| `name`         | string      | Display name                           |
| `lat` / `lon`  | float       | Coordinates                            |
| `address`      | string      | One-line address for UI                |
| `description`  | string      | Main text used for similarity          |
| `categories`   | list/string | Tags/categories (optional but helpful) |
| `rating`       | float?      | 0–5 (nullable; mostly for places)      |
| `review_count` | int?        | Popularity proxy (nullable)            |
| `price_tier`   | int?        | Optional (nullable)                    |
| `event_start`  | datetime?   | Only for events                        |
| `event_end`    | datetime?   | Only for events                        |
| `created_at`   | datetime    | Row created                            |
| `updated_at`   | datetime    | Row updated                            |

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

### 4) Urgency score (events only)

Requirement:

* **Events**: more urgent when close to ending.
* **Places**: urgency = 0.

Simple rule:

* If `now` is not within `[event_start, event_end]` → urgency = 0
* Else:

  * `remaining_hours = (event_end - now)`
  * `urgency = clamp(1 - remaining_hours / horizon_hours)`
  * Example: `horizon_hours = 3`

Output:

* `urgency_score ∈ [0,1]`

### Final score

Recommended simple weights:

* `w_corr = 0.45`
* `w_pop = 0.25`
* `w_weather = 0.15`
* `w_urgency = 0.15`

Formula:

```
final_score = w_corr * correlation_score
            + w_pop  * popularity_score
            + w_weather * weather_score
            + w_urgency * urgency_score
```

All terms are in `[0,1]`, so the final score stays in `[0,1]`.

---

## Workflow (how you’ll build it)

### Step 1: Define Madison boundary

Create a config for:

* `min_lat, min_lon, max_lat, max_lon`

Use it to:

* validate incoming data
* filter entities to Madison

### Step 2: Ingest data into `entities_raw`

For each source:

* map source fields to the schema
* normalize times to ISO datetimes (UTC preferred)
* build a rich `description`

**Places sources (examples):** Google Places, Yelp, Foursquare, OSM

**Event sources (examples):** Eventbrite, Ticketmaster, city calendars, UW events

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
    "rows_returned": 200
  },
  "rows": [
    {
      "name": "Place 0042",
      "type": "place",
      "lat": 43.07,
      "lon": -89.39,
      "address": "123 Demo St, Madison, WI",
      "description": "ramen, japanese. cozy, quiet, downtown...",
      "score": 0.83,
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
