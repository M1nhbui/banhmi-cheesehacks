# =============================================================================
# demo.py — Standalone demo: no server required
# =============================================================================
# This script shows the full pipeline end-to-end in a single run:
#
#   1. Build enriched entities (pipeline)
#   2. Score them against a set of demo keyword lists
#   3. Print a nicely formatted result table
#
# Usage:
#   python demo.py
#   python demo.py --keywords "ramen cozy quiet study"
#   python demo.py --keywords "outdoor hiking nature"  --top 5
#
# You can also import and call `run_demo()` from a notebook or another script.

from __future__ import annotations

import argparse
import sys
from typing import List

from pipeline import build_enriched_entities
from models import EntityEnriched
from scoring import correlation_scores, urgency_score, final_score


# =============================================================================
# Core scoring function (mirrors what the API does)
# =============================================================================

def score_entities(
    keywords: List[str],
    entities: List[EntityEnriched],
) -> List[dict]:
    """
    Score a list of enriched entities against user keywords.

    Args:
        keywords : list of keyword strings from the user
        entities : enriched entities from pipeline.build_enriched_entities()

    Returns:
        List of result dicts, sorted by 'score' descending.
        Each dict contains: name, type, address, score, breakdown, description.
    """
    # Clean keywords: lowercase and strip whitespace
    clean_kw = [kw.strip().lower() for kw in keywords if kw.strip()]

    # Collect description strings for batch TF-IDF
    descriptions = [e.description for e in entities]

    # Compute correlation scores for all entities in one TF-IDF pass
    corr_scores = correlation_scores(clean_kw, descriptions)

    results = []
    for entity, corr in zip(entities, corr_scores):

        # Re-compute urgency right now (for accuracy)
        urg = urgency_score(entity.event_start, entity.event_end)

        # Combine all four signals into one final score
        f_score = final_score(
            corr=corr,
            pop=entity.popularity_score,
            weather=entity.weather_score,
            urgency=urg,
        )

        results.append({
            "name":        entity.name,
            "type":        entity.entity_type,
            "address":     entity.address,
            "lat":         entity.lat,
            "lon":         entity.lon,
            "description": entity.description,
            "score":       f_score,
            "breakdown": {
                "similarity": corr,
                "popularity": entity.popularity_score,
                "weather":    entity.weather_score,
                "urgency":    urg,
            },
        })

    # Sort by final score highest-first
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# =============================================================================
# Pretty-printer
# =============================================================================

def print_results(results: List[dict], top: int = 10) -> None:
    """
    Print the top-N scored results in a human-readable table.

    Args:
        results : output from score_entities()
        top     : how many results to show
    """
    print()
    print("=" * 70)
    print(f"  TOP {top} RESULTS")
    print("=" * 70)

    for i, row in enumerate(results[:top], start=1):
        bd = row["breakdown"]
        # Format score as a visual bar (10 chars wide)
        bar_len = int(row["score"] * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)

        print(f"\n#{i:02d} {row['name']}  [{row['type'].upper()}]")
        print(f"     {row['address']}")
        print(f"     Score: {row['score']:.4f}  |{bar}|")
        print(f"     Breakdown →  similarity={bd['similarity']:.3f}  "
              f"popularity={bd['popularity']:.3f}  "
              f"weather={bd['weather']:.3f}  "
              f"urgency={bd['urgency']:.3f}")
        # Truncate description for readability
        desc_preview = row["description"][:100].replace("\n", " ")
        print(f"     Desc: {desc_preview}…")

    print()
    print(f"  ({len(results)} total entities scored, showing top {min(top, len(results))})")
    print("=" * 70)
    print()


# =============================================================================
# Preset keyword lists for demo scenarios
# =============================================================================

DEMO_SCENARIOS = {
    "ramen":     ["ramen", "japanese", "noodles", "soup", "cozy", "warm"],
    "outdoor":   ["outdoor", "hiking", "nature", "park", "scenic", "trail"],
    "coffee":    ["coffee", "cafe", "quiet", "study", "cozy", "wifi"],
    "nightlife": ["bar", "live-music", "drinks", "dancing", "night-out"],
    "art":       ["art", "museum", "culture", "gallery", "creative"],
}


# =============================================================================
# run_demo — importable function
# =============================================================================

def run_demo(keywords: List[str] = None, top: int = 10) -> List[dict]:
    """
    Run the full pipeline and return scored results.

    This is the main function you'd call from a notebook or another script.

    Args:
        keywords : list of keyword strings (default: ramen/coffee/cozy scenario)
        top      : number of top results to print

    Returns:
        Full list of scored result dicts (all entities, sorted by score).

    Example:
        >>> from demo import run_demo
        >>> results = run_demo(["ramen", "cozy", "quiet"], top=5)
    """
    if keywords is None:
        keywords = ["ramen", "coffee", "cozy", "quiet", "study-friendly"]

    # ---- Step 1: Build enriched entities (ingest + enrich) ----
    print(f"\n[demo] Building enriched entities...")
    entities = build_enriched_entities()

    # ---- Step 2: Score against keywords ----
    print(f"[demo] Scoring {len(entities)} entities for keywords: {keywords}")
    results = score_entities(keywords, entities)

    # ---- Step 3: Print results ----
    print(f"\n[demo] Keywords: {keywords}")
    print_results(results, top=top)

    return results


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    # ---- Parse command-line arguments ----
    parser = argparse.ArgumentParser(
        description="Madison Interest Map — standalone demo scorer"
    )
    parser.add_argument(
        "--keywords", "-k",
        type=str,
        default=None,
        help=(
            'Space or comma-separated keywords.  '
            'Example: --keywords "ramen cozy quiet"  or  -k "outdoor,hiking,nature"'
        ),
    )
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        choices=list(DEMO_SCENARIOS.keys()),
        default=None,
        help=(
            f"Use a preset keyword scenario.  "
            f"Choices: {list(DEMO_SCENARIOS.keys())}"
        ),
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=10,
        help="Number of top results to display (default: 10)",
    )
    args = parser.parse_args()

    # ---- Resolve keywords ----
    if args.scenario:
        # Use a preset scenario
        kw_list = DEMO_SCENARIOS[args.scenario]
        print(f"[demo] Using preset scenario '{args.scenario}': {kw_list}")
    elif args.keywords:
        # Parse user-provided keywords (space- or comma-separated)
        raw = args.keywords.replace(",", " ")
        kw_list = [kw.strip() for kw in raw.split() if kw.strip()]
    else:
        # Default scenario — a common Madison use case
        kw_list = ["ramen", "coffee", "cozy", "quiet", "study-friendly"]
        print(f"[demo] No keywords given — using default: {kw_list}")
        print(f"[demo] Tip: try  python demo.py --keywords 'outdoor hiking nature'")

    # ---- Run! ----
    run_demo(keywords=kw_list, top=args.top)
