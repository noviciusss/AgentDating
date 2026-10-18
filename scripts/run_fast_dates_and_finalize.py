#!/usr/bin/env python3
"""
Fast Dating & Finalize Runner:
- Up to MAX_PAIRS=12 dates.
- 4 turns per date (2 rounds).
- Uses openai/gpt-oss-20b for turns and scoring.
- Hard timeout at 220s (~3.7 minutes).
- Saves every date immediately.
- Computes rankings for all 25 people with embedding fallback for undated pairs.
- Copies everything to data/demo/.
"""

import asyncio
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from app.models import Person, Profile, DateResult, PersonRanking
from app.shortlist import compute_shortlist
from app.dating import run_date
from app.ranking import compute_rankings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fast_finalize")

DEMO_NEW_DIR = ROOT_DIR / "data" / "demo_new"
DEMO_DIR = ROOT_DIR / "data" / "demo"
MAX_PAIRS = int(os.getenv("MAX_PAIRS", "12"))
HARD_TIMEOUT = 220.0  # seconds

async def main():
    start_time = time.monotonic()
    print("="*70)
    print("FAST DATING & FINALIZE (MAX 4 MINUTES)")
    print("="*70)

    # 1. Load profiles
    profiles_dir = DEMO_NEW_DIR / "profiles"
    dates_dir = DEMO_NEW_DIR / "dates"
    dates_dir.mkdir(parents=True, exist_ok=True)

    profiles = {}
    for pf in profiles_dir.glob("*.json"):
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
            profiles[d["id"]] = Profile(**d)
        except Exception:
            pass

    people_data = json.loads((DEMO_NEW_DIR / "people.json").read_text(encoding="utf-8"))
    people_ids = [p["id"] for p in people_data if p["id"] in profiles]
    names = {p["id"]: p["name"] for p in people_data}

    print(f"Loaded {len(profiles)} profiles for 25 people.")

    # 2. Compute shortlist
    pairs, similarities = compute_shortlist(profiles)
    target_pairs = pairs[:MAX_PAIRS]
    print(f"Shortlisted {len(target_pairs)} candidate pairs for dating (MAX_PAIRS={MAX_PAIRS}).")

    # 3. Run dates concurrently with semaphore
    semaphore = asyncio.Semaphore(3)
    completed_dates: list[DateResult] = []

    # Check already existing dates
    for df in dates_dir.glob("*.json"):
        try:
            d = json.loads(df.read_text(encoding="utf-8"))
            res = DateResult(**d)
            if not res.date_failed:
                completed_dates.append(res)
        except Exception:
            pass

    existing_pair_keys = {(d.a, d.b) for d in completed_dates} | {(d.b, d.a) for d in completed_dates}
    pairs_to_run = [p for p in target_pairs if p not in existing_pair_keys and (p[1], p[0]) not in existing_pair_keys]
    print(f"Already completed on disk: {len(completed_dates)} dates. Remaining to run: {len(pairs_to_run)}")

    async def date_task(a_id: str, b_id: str):
        if time.monotonic() - start_time > HARD_TIMEOUT:
            logger.info(f"Hard stop reached; skipping date {a_id}__{b_id}")
            return
        async with semaphore:
            if time.monotonic() - start_time > HARD_TIMEOUT:
                return
            target_file = dates_dir / f"{a_id}__{b_id}.json"
            print(f"Starting date: {names.get(a_id, a_id)} <-> {names.get(b_id, b_id)}...")
            try:
                res = await asyncio.wait_for(
                    run_date(
                        a_id=a_id,
                        b_id=b_id,
                        a_name=names.get(a_id, a_id),
                        b_name=names.get(b_id, b_id),
                        a_profile=profiles[a_id],
                        b_profile=profiles[b_id],
                    ),
                    timeout=50.0
                )
                target_file.write_text(res.model_dump_json(indent=2), encoding="utf-8")
                completed_dates.append(res)
                print(f"  ✓ Date finished: {names.get(a_id, a_id)} & {names.get(b_id, b_id)} (Score: {res.final_score})")
            except Exception as e:
                logger.warning(f"Date {a_id}__{b_id} failed or timed out: {e}")

    tasks = [date_task(a, b) for a, b in pairs_to_run]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.monotonic() - start_time
    print(f"\nDating finished in {elapsed:.1f}s. Total dates completed: {len(completed_dates)}")

    # 4. Compute rankings
    print("\nComputing match rankings for all 25 people...")
    rankings = compute_rankings(people_ids, completed_dates, similarities)
    rankings_dicts = [r.model_dump() for r in rankings]
    (DEMO_NEW_DIR / "rankings.json").write_text(json.dumps(rankings_dicts, indent=2), encoding="utf-8")
    print(f"✓ Saved {len(rankings)} rankings to data/demo_new/rankings.json")

    # 5. Copy to active data/demo/
    print("\nDeploying demo dataset into data/demo/...")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "profiles").mkdir(exist_ok=True)
    (DEMO_DIR / "dates").mkdir(exist_ok=True)

    shutil.copy2(DEMO_NEW_DIR / "people.json", DEMO_DIR / "people.json")
    shutil.copy2(DEMO_NEW_DIR / "rankings.json", DEMO_DIR / "rankings.json")

    for pf in profiles_dir.glob("*.json"):
        shutil.copy2(pf, DEMO_DIR / "profiles" / pf.name)
    for df in dates_dir.glob("*.json"):
        shutil.copy2(df, DEMO_DIR / "dates" / df.name)

    print("✓ Successfully copied all profiles, dates, and rankings to data/demo/!")


if __name__ == "__main__":
    asyncio.run(main())
