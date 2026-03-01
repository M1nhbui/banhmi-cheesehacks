# Madison Interest Map (Keyword-Driven Scoring)

A FastAPI backend that ingests **places** and **events** for **Madison, WI**, enriches each entity with **real-time popularity and crowd signals** from BestTime, computes a **keyword-to-description correlation** (TF-IDF cosine similarity with sigmoid stretch), combines it with **hotness**, **crowd**, and **urgency** signals, then returns a **ranked list of scored map markers** for a frontend interactive map.

> Goal: keep the system simple, explainable, and easy to extend when you plug in additional real-time data sources.

---

## Demo scope

* **City:** Madison, WI only (fixed bounding box: lat 43.02–43.15, lon −89.55–−89.30).
* **User:** single demo user — only inputs are a keyword list and a scoring mode at request time.
* **Entities:** two types:
  * **Place** (1,708 real Foursquare venues): has `open`/`close` hours, BestTime hotness and crowd scores.
  * **Event** (51 hand-crafted Madison events): has `event_start`/`event_end`; urgency builds before the event starts and decays as it winds down.
* **No personalization:** the only user inputs are a keyword list and an optional scoring mode.
* **Data files:** `data/places.json` and `data/events.json` — swap either file to update the dataset without touching code.

---

## What the frontend receives

The backend returns a list of rows sorted by `score` descending. Each row is ready to plot as a map marker:

* `name`
* `lat`, `lon`
* `address`
* `description`
* `score` — **min-max normalised to `[0, 1]`** across all returned results

Optional debug/UI fields:

* `type` (`place` or `event`)
* `breakdown` — raw pre-normalisation component scores: `similarity`, `hotness`, `crowd`, `urgency`

---

## Architecture at a glance

### Offline / batch pipeline

```
crawldata.py  →  BestTime API  →  hotness_v1_ranked_<timestamp>.csv
                                            ↓
                                    merge_hotness.py
                                            ↓
                              data/places.json  (with hotness + crowd fields)
```

1. **`crawldata.py`** — crawls Foursquare venues and calls BestTime for foot-traffic data.
2. **`compute_hotness_v1.py`** — computes `venue_hotness_final` and `current_busyness` per venue and writes `hotness_v1_ranked_<timestamp>.csv`.
3. **`merge_hotness.py`** — reads the newest CSV from `besttime_outputs/`, geo+name-matches venues to `places.json`, and writes `hotness` and `crowd` back into the JSON.
4. **`data/events.json`** — hand-crafted; `hotness` and `crowd` are set manually per event.

### Runtime API

1. User sends **keyword list** + optional **mode**.
2. Backend computes **TF-IDF cosine similarity** (with sigmoid stretch) between keywords and entity descriptions.
3. Backend recomputes **urgency** in real-time.
4. Backend combines similarity + hotness + crowd + urgency via a **mode-specific formula**.
5. Backend **min-max normalises** the scores across all results and returns the ranked table.

---

## Data model (schema)

| Field | Type | Description |
|---|---|---|
| `entity_id` | string | Unique id (numeric string for Foursquare data, UUID otherwise) |
| `entity_type` | enum | `place` or `event` |
| `source` | string | `foursquare`, `manual`, etc. |
| `source_id` | string | Unique id from the source |
| `name` | string | Display name |
| `lat` / `lon` | float | Coordinates |
| `address` | string | One-line address for UI |
| `description` | string | Rich text used for keyword similarity (categories + vibe words) |
| `categories` | list or string | Tags/categories |
| `rating` | float? | 0–5, nullable |
| `review_count` | int? | Popularity proxy, nullable |
| `price_tier` | int? | 1–4 ($ to $$$$), nullable |
| `hotness` | float? | BestTime `venue_hotness_final` in [0, 1] |
| `crowd` | float? | BestTime `current_busyness / 100` in [0, 1] |
| `event_start` | datetime? | ISO 8601 UTC — events only |
| `event_end` | datetime? | ISO 8601 UTC — events only |
| `open` | string? | `HH:MM` local open time — places only |
| `close` | string? | `HH:MM` local close time — places only |

---

## Scoring design

Each entity gets **4 component scores**, all in **[0, 1]**.

---

### 1) Correlation score — TF-IDF cosine + sigmoid stretch

#### Step 1 — TF-IDF cosine similarity

All entity descriptions and the user's keyword string are fed into a single `TfidfVectorizer` (word + bigram, sublinear TF) so IDF weights are computed across the whole corpus.

```
query_vec  = TF-IDF(keywords joined as one string)
desc_vec_i = TF-IDF(entity i description)
raw_sim_i  = cosine_similarity(query_vec, desc_vec_i)   ∈ [0, 1]
```

#### Step 2 — Remapped sigmoid stretch

Raw cosine values cluster tightly near 0 (typical max ≈ 0.10–0.15). A remapped sigmoid is applied to create clear divergence between relevant and non-relevant results:

$$
f(x) = \frac{\sigma\!\left(k(x - c)\right) - \sigma\!\left(-kc\right)}{\sigma\!\left(k(1-c)\right) - \sigma\!\left(-kc\right)}
\quad \text{where} \quad \sigma(z) = \frac{1}{1+e^{-z}}
$$

This guarantees $f(0) = 0$, $f(1) = 1$, with a steep S-shaped transition at $x = c$.

Config defaults:

| Parameter | Value | Meaning |
|---|---|---|
| `SIMILARITY_SIGMOID_CENTER` | `0.04` | Inflection point — raw cosine ≈ 0.04 maps to stretched score ≈ 0.5 |
| `SIMILARITY_SIGMOID_K` | `80.0` | Steepness — higher = sharper cliff |

Representative mapping at these defaults:

| Raw cosine | Stretched score |
|---|---|
| 0.00 | 0.00 |
| 0.01 | ≈ 0.07 |
| 0.04 | ≈ 0.50 |
| 0.06 | ≈ 0.82 |
| 0.10 | ≈ 0.98 |

Output: `correlation_score ∈ [0, 1]`

---

### 2) Hotness score — BestTime `venue_hotness_final`

Pass-through of the precomputed BestTime hotness signal, already normalised to [0, 1]:

```
hotness_score = venue_hotness_final   (clipped to [0, 1])
```

Returns `0.0` when data is unavailable (venue not crawled or closed).

---

### 3) Crowd score — BestTime `current_busyness`

Pass-through of the precomputed BestTime busyness signal:

```
crowd_score = current_busyness / 100   (clipped to [0, 1])
```

Returns `0.0` when data is unavailable.

---

### 4) Urgency score — exponential decay

Urgency measures how time-sensitive it is to act *right now*. Driven by exponential decay:

$$\text{urgency} = e^{-t / \tau}$$

where $t$ is the relevant remaining time in seconds and $\tau$ is the decay time constant.

> **Demo note:** `SIMULATED_MADISON_HOUR = 14` in `config.py` pins the clock to 2 PM Madison time so urgency scores are meaningful during a demo even if the real time is late at night. Set to `None` for production.

#### Events (`event_start` + `event_end` present)

| Phase | Condition | Score |
|---|---|---|
| Too early | `now < event_start` and `delta > H_start` | `0.0` |
| Pre-start build-up | `now < event_start` and `delta ≤ H_start` | $e^{-\delta / \tau_\text{start}}$ |
| Live wind-down | `event_start ≤ now < event_end` | $e^{-r / \tau_\text{end}}$ |
| Ended | `now ≥ event_end` | `0.0` |

* $\delta$ = seconds until `event_start`
* $r$ = seconds until `event_end`

#### Places (`open` + `close` hours present)

```
urgency = 0.0                                    if venue is closed
urgency = exp(-remaining_until_close / τ_venue)  if open
```

Handles overnight venues (e.g. `open=22:00`, `close=02:00`) by adding one day to `close` when `close ≤ open`.

#### Config defaults

| Constant | Default | Meaning |
|---|---|---|
| `URGENCY_H_START_S` | `21600` (6 h) | Lookahead window before event start |
| `URGENCY_TAU_START_S` | `5400` (90 min) | Pre-start decay time constant |
| `URGENCY_TAU_EVENT_END_S` | `3600` (60 min) | Live wind-down decay time constant |
| `URGENCY_TAU_VENUE_CLOSE_S` | `3600` (60 min) | Closing-time decay constant for places |

---

### 5) Mode-aware final score

Instead of a single fixed weighted sum, the final score depends on the **mode** (`?mode=`) requested by the client.

#### Helper functions

**Triangular membership `tri(x, center, width)`** — peaks at 1.0 at `center`, drops linearly to 0 at `center ± width`:

$$\text{tri}(x,\, c,\, w) = \max\!\left(0,\; 1 - \frac{|x - c|}{w}\right)$$

**Derived scores** (computed once per entity per request, where `hot` = hotness, `crowd` = crowd, `urg` = urgency):

```
mid_hot      = tri(hot,   center=0.50, width=0.25)   # peaks at moderate hotness
calm_hot     = tri(hot,   center=0.30, width=0.25)   # peaks at low-ish hotness
gentle_crowd = tri(crowd, center=0.28, width=0.22)   # peaks at comfortable crowd level
low_crowd    = 1 - crowd
low_urg      = 1 - urg
```

> **Hard gate:** if the venue/event is closed (`open_now = 0`), **all modes return `−1.0`** and the entity is excluded from results.

#### Mode formulas

**`relevant` (default)** — keyword match dominates:

```
score = 0.80 * rel
      + 0.02 * hot
      + 0.08 * crowd
      + 0.08 * urg
```

**`hottest`** — BestTime hotness dominates:

```
score = 0.08 * rel
      + 0.76 * hot
      + 0.08 * crowd
      + 0.08 * urg
```

**`hidden_gems`** — relevant but not mainstream; soft penalties when too packed or too hot:

```
score = 0.55 * rel
      + 0.20 * mid_hot
      + 0.18 * gentle_crowd
      + 0.07 * low_urg

if crowd > 0.75:  score *= 0.75
if hot   > 0.85:  score *= 0.85
```

**`chill`** — relevant + relaxed; soft penalties when crowded or high urgency:

```
score = 0.50 * rel
      + 0.05 * low_crowd
      + 0.05 * low_urg
      + 0.40 * calm_hot

if crowd > 0.65:  score *= 0.60
if urg   > 0.80:  score *= 0.70
```

---

### 6) Min-max normalisation across the response

After scoring all entities with the chosen mode, every score is stretched so the best result maps to 1.0 and the worst to 0.0:

$$\text{score}_i = \frac{s_i - s_{\min}}{s_{\max} - s_{\min}}$$

The relative ordering is preserved; only the absolute values change. `breakdown` fields always contain the **raw pre-normalisation** component values.

---

## API contract

### `POST /score`

**Query parameter:** `?mode=relevant` *(default)* | `hottest` | `hidden_gems` | `chill`

**Request body:**

```json
{
  "keywords": ["ramen", "coffee", "cozy", "quiet", "study-friendly"]
}
```

**Response:**

```json
{
  "meta": {
    "city": "Madison, WI",
    "keywords": ["ramen", "coffee", "cozy", "quiet", "study-friendly"],
    "rows_returned": 1759
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
        "similarity": 0.9821,
        "hotness": 0.42,
        "crowd": 0.31,
        "urgency": 0.12
      }
    }
  ]
}
```

> `score` is min-max normalised across all rows (`1.0` = best match for this query + mode).
> `breakdown` values are the raw pre-normalisation component scores.

### `GET /health`

Returns server status and count of loaded entities.

```json
{ "status": "ok", "entities_loaded": 1759 }
```

---

## Data pipeline workflow

```
1. crawldata.py               — fetch Foursquare + BestTime data
2. compute_hotness_v1.py      — auto-detected; outputs hotness_v1_ranked_<ts>.csv
3. merge_hotness.py           — reads newest CSV → geo+name matches → writes
                                hotness & crowd fields into data/places.json
4. uvicorn api:app --reload   — runtime API
```

`merge_hotness.py` matching strategy (in priority order):

1. Name similarity ≥ 0.6 within 200 m (Levenshtein ratio via `difflib`)
2. Nearest neighbour within 80 m (geo fallback)

Last run: **453 / 1,708 places matched** (179 name match + 274 geo fallback).

---

## Config reference (`config.py`)

| Key | Default | Description |
|---|---|---|
| `WEIGHTS` | `{correlation: 0.45, hotness: 0.25, crowd: 0.15, urgency: 0.15}` | Component weights (used as baseline; modes override these) |
| `SIMILARITY_SIGMOID_CENTER` | `0.04` | S-curve inflection point for cosine stretch |
| `SIMILARITY_SIGMOID_K` | `80.0` | S-curve steepness |
| `URGENCY_H_START_S` | `21600` | Lookahead window before event start (6 h) |
| `URGENCY_TAU_START_S` | `5400` | Pre-start decay τ (90 min) |
| `URGENCY_TAU_EVENT_END_S` | `3600` | Live wind-down decay τ (60 min) |
| `URGENCY_TAU_VENUE_CLOSE_S` | `3600` | Venue closing-time decay τ (60 min) |
| `SIMULATED_MADISON_HOUR` | `14` | Pin demo clock to this hour (2 PM); `None` = real clock |
| `REVIEW_COUNT_CAP` | `500` | Cap for log-normalising review counts |

---

## Extending the project later

* Replace hand-crafted events with Eventbrite / Ticketmaster API.
* Add a real DB (Postgres/PostGIS) to store entities and query by bounds.
* Replace TF-IDF with sentence-transformer embeddings for richer semantic matching.
* Add per-user preference weighting.
* Refresh BestTime data on a schedule and stream `crowd` updates in real-time.

---

## License

MIT (or choose your preferred license).
