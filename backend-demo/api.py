# =============================================================================
# api.py — FastAPI web server for the Madison Interest Map
# =============================================================================
# Exposes a single endpoint:
#
#   POST /score
#   Body:  { "keywords": ["ramen", "cozy", "quiet"] }
#   Returns: scored + ranked list of map entities
#
# The pipeline runs once at startup and the enriched entities are kept in
# memory.  Each request only re-computes:
#   - TF-IDF correlation (fast, <100ms for 50+ entities)
#   - urgency_score (must be real-time to be accurate)
#
# Run with:
#   uvicorn api:app --reload
#   or:  python api.py

from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
from models import EntityEnriched, ScoreRequest, ScoreResponse, ScoreMeta, ScoredRow, ScoreBreakdown
from pipeline import build_enriched_entities
from scoring import correlation_scores, urgency_score, final_score

# =============================================================================
# App setup
# =============================================================================

app = FastAPI(
    title="Madison Interest Map API",
    description=(
        "Keyword-driven scoring of places and events in Madison, WI. "
        "Send a list of interest keywords and receive back a ranked list of map markers."
    ),
    version="1.0.0",
)

# Allow all origins for the demo frontend (in production, restrict this!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Startup — run the batch pipeline once and keep results in memory
# =============================================================================

# This list is populated when the server starts (see @app.on_event below)
_enriched_entities: List[EntityEnriched] = []


@app.on_event("startup")
def startup_event():
    """
    Called once when the FastAPI server starts.
    Runs the offline pipeline to ingest and enrich all entities.
    """
    global _enriched_entities
    print("[api] Running pipeline at startup...")
    _enriched_entities = build_enriched_entities()
    print(f"[api] Ready — {len(_enriched_entities)} entities loaded.")


# =============================================================================
# Health check endpoint
# =============================================================================

@app.get("/health", summary="Health check")
def health():
    """Simple ping/pong to verify the server is running."""
    return {
        "status": "ok",
        "entities_loaded": len(_enriched_entities),
    }


# =============================================================================
# POST /score — the main ranking endpoint
# =============================================================================

@app.post("/score", response_model=ScoreResponse, summary="Rank entities by keywords")
def score(request: ScoreRequest) -> ScoreResponse:
    """
    Given a list of user keywords, return all Madison places and events
    ranked by a combined score (similarity + popularity + weather + urgency).

    **Request body:**
    ```json
    { "keywords": ["ramen", "coffee", "cozy", "study"] }
    ```

    **Response:** list of map-ready rows sorted by `score` descending.
    """
    # Validate input
    if not request.keywords:
        raise HTTPException(status_code=400, detail="keywords list must not be empty")

    # Clean up keywords: lowercase, strip whitespace, remove empty strings
    keywords = [kw.strip().lower() for kw in request.keywords if kw.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="No valid keywords provided")

    if not _enriched_entities:
        raise HTTPException(status_code=503, detail="Entities not loaded yet, try again shortly")

    # -----------------------------------------------------------------
    # Re-compute urgency in real-time (time-sensitive)
    # -----------------------------------------------------------------
    # We update urgency_score now (not from the pipeline snapshot) so
    # events that just started or just ended reflect their true state.
    descriptions = [e.description for e in _enriched_entities]

    # -----------------------------------------------------------------
    # Compute TF-IDF correlation scores for all entities at once
    # -----------------------------------------------------------------
    corr_scores = correlation_scores(keywords, descriptions)

    # -----------------------------------------------------------------
    # Build the scored result rows
    # -----------------------------------------------------------------
    rows: List[ScoredRow] = []

    for entity, corr in zip(_enriched_entities, corr_scores):
        # Re-compute urgency with the current time
        urg = urgency_score(entity.event_start, entity.event_end)

        # Compute combined final score
        f_score = final_score(
            corr=corr,
            pop=entity.popularity_score,
            weather=entity.weather_score,
            urgency=urg,
        )

        # Build the response row
        row = ScoredRow(
            name=entity.name,
            type=entity.entity_type,
            lat=entity.lat,
            lon=entity.lon,
            address=entity.address,
            description=entity.description,
            score=f_score,
            breakdown=ScoreBreakdown(
                similarity=corr,
                popularity=entity.popularity_score,
                weather=entity.weather_score,
                urgency=urg,
            ),
        )
        rows.append(row)

    # Sort by final score descending so the best matches appear first
    rows.sort(key=lambda r: r.score, reverse=True)

    return ScoreResponse(
        meta=ScoreMeta(
            city="Madison, WI",
            keywords=keywords,
            rows_returned=len(rows),
        ),
        rows=rows,
    )


# =============================================================================
# Entry point — run directly with: python api.py
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True,   # auto-restart on file changes during development
    )
