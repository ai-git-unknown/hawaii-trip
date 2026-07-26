#!/usr/bin/env python3
"""
Geocode addresses in shopping.json and custom.json using Nominatim (OpenStreetMap).
Saves lat/lng back to the JSON files.

Usage:
    python3 geocode.py              # geocode missing lat/lng in both files
    python3 geocode.py --file data/shopping.json  # single file
    python3 geocode.py --dry-run    # show what would be geocoded without saving
"""

import json
import time
import argparse
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote_plus
from urllib.error import HTTPError, URLError

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "HawaiiTripPlanner/1.0 (github.com/ai-git-unknown/hawaii-trip)"
RATE_LIMIT_DELAY = 1.1  # seconds between requests (Nominatim: 1 req/sec)

VALID_CATEGORIES = {"shop", "food", "activity", "beach", "other"}

def load_json(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def geocode_address(address: str) -> tuple[float, float] | None:
    """Return (lat, lng) or None if not found."""
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
        "addressdetails": 0,
    }
    url = f"{NOMINATIM_URL}?{ '&'.join(f'{k}={quote_plus(str(v))}' for k, v in params.items()) }"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except (HTTPError, URLError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"  ✗ Geocode failed: {e}", file=sys.stderr)
    return None

def validate_category(cat: str | None) -> str:
    if cat and cat in VALID_CATEGORIES:
        return cat
    if cat:
        print(f"  ⚠ Invalid category '{cat}', defaulting to 'other'", file=sys.stderr)
    return "other"

def process_file(path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Returns (geocoded_count, total_missing)"""
    data = load_json(path)
    missing = [item for item in data if "lat" not in item or "lng" not in item]
    if not missing:
        print(f"  ✓ {path.name}: all {len(data)} spots have coordinates")
        return 0, 0

    print(f"  → {path.name}: {len(missing)} of {len(data)} spots need geocoding")
    geocoded = 0

    for i, item in enumerate(missing):
        addr = item.get("address", "").strip()
        if not addr:
            print(f"    [{i+1}/{len(missing)}] {item.get('id', '?')}: no address, skipping")
            continue

        print(f"    [{i+1}/{len(missing)}] {item.get('id', '?')}: {addr[:60]}...", end=" ", flush=True)
        coords = geocode_address(addr)
        if coords:
            lat, lng = coords
            item["lat"] = lat
            item["lng"] = lng
            geocoded += 1
            print(f"✓ ({lat:.6f}, {lng:.6f})")
        else:
            print("✗ not found")
        time.sleep(RATE_LIMIT_DELAY)

    # Validate categories for all items
    for item in data:
        item["category"] = validate_category(item.get("category"))

    if not dry_run and geocoded > 0:
        save_json(path, data)
        print(f"  ✓ Saved {geocoded} updated spots to {path}")
    elif dry_run:
        print(f"  [dry-run] Would save {geocoded} updates to {path}")

    return geocoded, len(missing)

def main():
    parser = argparse.ArgumentParser(description="Geocode addresses in JSON files")
    parser.add_argument("--file", help="Process single file instead of both")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be geocoded without saving")
    args = parser.parse_args()

    base = Path(__file__).parent
    files = [base / args.file] if args.file else [base / "data/shopping.json", base / "data/custom.json"]

    total_geocoded = 0
    total_missing = 0
    for f in files:
        if not f.exists():
            print(f"  ✗ File not found: {f}", file=sys.stderr)
            continue
        g, m = process_file(f, args.dry_run)
        total_geocoded += g
        total_missing += m

    print(f"\nDone: {total_geocoded}/{total_missing} geocoded")
    if args.dry_run:
        print("Run without --dry-run to save changes.")

if __name__ == "__main__":
    main()