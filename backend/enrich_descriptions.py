#!/usr/bin/env python3
"""
enrich_descriptions.py

Reads data/entities_raw.json, rewrites each entity's `description` field
into a fluent one-sentence summary using a local Ollama model, and saves
the result to data/entities_described.json.

Requirements:
  - Ollama running locally:  https://ollama.com
  - Model pulled:            ollama pull llama3.2

Usage:
  python backend-demo/enrich_descriptions.py [--model llama3.2] [--resume]

Options:
  --model   Ollama model name (default: llama3.2)
  --resume  Skip entities that already have a non-empty description in the
            output file, so you can restart after an interruption.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
INPUT_PATH  = BASE_DIR / "data" / "entities_raw.json"
OUTPUT_PATH = BASE_DIR / "data" / "entities_described.json"

OLLAMA_URL  = "http://localhost:11434/api/generate"
SAVE_EVERY  = 10   # flush to disk every N entities

SYSTEM_PROMPT = (
    "You are a local guide writer. "
    "Given structured keywords about a place, write exactly 4 fluent sentences "
    "that summarise what the place is, what it offers, its atmosphere, and any notable features. "
    "Do not mention the place name. Do not add facts not in the input. "
    "Reply with the 4 sentences only — no preamble, no bullet points, no headers."
)

USER_TEMPLATE = "Place details: {description}"


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def call_ollama(model: str, description: str, retries: int = 3) -> str:
    """Send a generate request to Ollama and return the response text."""
    payload = json.dumps({
        "model":  model,
        "system": SYSTEM_PROMPT,
        "prompt": USER_TEMPLATE.format(description=description),
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 300,
        },
    }).encode()

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data.get("response", "").strip()
        except urllib.error.URLError as e:
            print(f"    [attempt {attempt}/{retries}] Ollama error: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",  default="llama3.2", help="Ollama model name")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-processed entries in the output file")
    args = parser.parse_args()

    # --- load input ---
    if not INPUT_PATH.exists():
        sys.exit(f"Input not found: {INPUT_PATH}\nRun build_entities_raw.py first.")

    with open(INPUT_PATH, encoding="utf-8") as f:
        entities: list[dict] = json.load(f)
    print(f"Loaded {len(entities)} entities from {INPUT_PATH}")

    # --- resume: load existing output ---
    existing: dict[str, str] = {}   # source_id -> enriched description
    if args.resume and OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            existing_rows: list[dict] = json.load(f)
        existing = {
            r["source_id"]: r["description"]
            for r in existing_rows
            if r.get("description")
        }
        print(f"Resuming: {len(existing)} entries already processed.")

    # --- check Ollama is reachable ---
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=5)
    except Exception:
        sys.exit(
            "Cannot reach Ollama at http://localhost:11434\n"
            "Start it with:  ollama serve\n"
            f"Pull the model: ollama pull {args.model}"
        )

    # --- process ---
    results: list[dict] = []
    skipped = 0

    for i, entity in enumerate(entities, 1):
        sid = entity.get("source_id", "")
        name = entity.get("name", "")
        raw_desc = entity.get("description", "").strip()

        # resume: reuse already-generated description
        if args.resume and sid in existing:
            enriched_entity = dict(entity)
            enriched_entity["description"] = existing[sid]
            results.append(enriched_entity)
            skipped += 1
            continue

        print(f"[{i}/{len(entities)}] {name or sid} ...", end=" ", flush=True)

        if not raw_desc:
            print("(no description, skipping)")
            results.append(dict(entity))
            continue

        enriched = call_ollama(args.model, raw_desc)

        if enriched:
            print(f"OK")
        else:
            print("FAILED (keeping original)")
            enriched = raw_desc

        enriched_entity = dict(entity)
        enriched_entity["description"] = enriched
        results.append(enriched_entity)

        # incremental save
        if i % SAVE_EVERY == 0:
            _save(results, OUTPUT_PATH)
            print(f"  -> saved {len(results)} entries so far")

    # --- final save ---
    _save(results, OUTPUT_PATH)
    print(f"\nDone.")
    print(f"  Processed: {len(results) - skipped}")
    print(f"  Skipped (resumed): {skipped}")
    print(f"  Output: {OUTPUT_PATH}")


def _save(rows: list[dict], path: Path):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
