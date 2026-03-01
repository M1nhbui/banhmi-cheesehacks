#!/usr/bin/env python3
"""
prepare_entities.py

Reads data/entities_described.json and produces entities.json in the
project root with the following transformations:

  - Add `open`  column  ← value copied from event_start
  - Add `close` column  ← value copied from event_end
  - Set event_start and event_end to null
  - If open  is null → default "09:00"
  - If close is null → default "17:00"
  - Drop rows where lat, lon, or description is null/empty

Output: entities.json  (project root)
"""

import json
from pathlib import Path

BASE_DIR   = Path(__file__).parent
INPUT_PATH = BASE_DIR / "data" / "entities_described.json"
OUT_PATH   = BASE_DIR / "entities.json"

DEFAULT_OPEN  = "09:00"
DEFAULT_CLOSE = "17:00"


def main():
    if not INPUT_PATH.exists():
        raise SystemExit(f"Input not found: {INPUT_PATH}")

    with open(INPUT_PATH, encoding="utf-8") as f:
        entities: list[dict] = json.load(f)

    print(f"Loaded {len(entities)} entities from {INPUT_PATH}")

    results = []
    dropped = 0

    for entity in entities:
        # Drop rows missing lat, lon, or description
        if (
            entity.get("lat") is None
            or entity.get("lon") is None
            or not (entity.get("description") or "").strip()
        ):
            dropped += 1
            continue

        row = dict(entity)

        # Copy event_start / event_end → open / close
        row["open"]  = row.get("event_start")
        row["close"] = row.get("event_end")

        # Null out the original fields
        row["event_start"] = None
        row["event_end"]   = None

        # Default nulls
        if not row["open"]:
            row["open"] = DEFAULT_OPEN
        if not row["close"]:
            row["close"] = DEFAULT_CLOSE

        results.append(row)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Dropped {dropped} rows (null lat/lon/description)")
    print(f"Output:  {len(results)} entities → {OUT_PATH}")


if __name__ == "__main__":
    main()
