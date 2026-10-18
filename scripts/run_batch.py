#!/usr/bin/env python3
"""
CLI: Run the full pipeline from a CSV of people and write output to data/demo/.

Usage:
    python scripts/run_batch.py --input scripts/seed_people.example.csv --output data/demo
    python scripts/run_batch.py --input people.csv
"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DEMO_DIR
from app.models import Person, ProgressEvent
from app.pipeline import run_pipeline
from app.jobs import create_run, get_run, get_run_data, store_run_data, save_run_data


async def main():
    parser = argparse.ArgumentParser(description="Run the Agent Dating pipeline on a batch of people")
    parser.add_argument("--input", "-i", required=True, help="CSV file: name,linkedin_url,instagram_url")
    parser.add_argument("--output", "-o", default=str(DEMO_DIR), help="Output directory (default: data/demo)")
    args = parser.parse_args()

    # Read CSV
    people_input = []
    with open(args.input, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            people_input.append({
                "name": row.get("name", "").strip(),
                "linkedin_url": row.get("linkedin_url", "").strip(),
                "instagram_url": row.get("instagram_url", "").strip(),
            })

    if len(people_input) < 3:
        print(f"Error: Need at least 3 people, got {len(people_input)}")
        sys.exit(1)

    print(f"Loaded {len(people_input)} people from {args.input}")

    # Create and run
    people = [Person(id="pending", name=p.get("name", ""),
                     linkedin_url=p.get("linkedin_url", ""),
                     instagram_url=p.get("instagram_url", ""))
              for p in people_input]
    run_id = create_run(people)

    print(f"Starting pipeline (run_id: {run_id})…")
    await run_pipeline(run_id, people_input)

    # Copy output to target directory
    run_data = get_run_data(run_id)
    if run_data:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "profiles").mkdir(exist_ok=True)
        (output_dir / "dates").mkdir(exist_ok=True)

        # People
        people_list = run_data.get("people", [])
        people_dicts = [p.model_dump() if hasattr(p, 'model_dump') else p for p in people_list]
        (output_dir / "people.json").write_text(json.dumps(people_dicts, indent=2), encoding='utf-8')

        # Profiles
        for pid, profile in run_data.get("profiles", {}).items():
            d = profile.model_dump() if hasattr(profile, 'model_dump') else profile
            (output_dir / "profiles" / f"{pid}.json").write_text(json.dumps(d, indent=2), encoding='utf-8')

        # Dates
        for date in run_data.get("dates", []):
            d = date.model_dump() if hasattr(date, 'model_dump') else date
            a = d.get("a", "")
            b = d.get("b", "")
            (output_dir / "dates" / f"{a}__{b}.json").write_text(json.dumps(d, indent=2), encoding='utf-8')

        # Rankings
        rankings = run_data.get("rankings", [])
        rankings_dicts = [r.model_dump() if hasattr(r, 'model_dump') else r for r in rankings]
        (output_dir / "rankings.json").write_text(json.dumps(rankings_dicts, indent=2), encoding='utf-8')

        print(f"\n[OK] Output written to {output_dir}")
        print(f"   People:   {len(people_dicts)}")
        print(f"   Profiles: {len(run_data.get('profiles', {}))}")
        print(f"   Dates:    {len(run_data.get('dates', []))}")
        print(f"   Rankings: {len(rankings)}")
    else:
        print("[ERROR] No run data available")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
