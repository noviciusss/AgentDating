#!/usr/bin/env python3
"""
Controlled Pipeline Runner satisfying all Rules 0-8:
- Resumable: writes to data/demo_new/ immediately, skips completed items.
- Token budget calculation using real Groq rate limits.
- Stage-based control:
  --stage budget: prints token budget & Groq limits
  --stage analyze: scrapes (from cache) + analyzes all 25 people, reports failed/partial & 3 most generic profiles (Rule 6)
  --stage pilot-dates: runs first 3 dates, prints transcripts & score spread (Rule 7)
  --stage full-dates: runs remaining dates and computes rankings
  --stage swap: validates demo_new and swaps into data/demo/ (Rule 1, 8)
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Setup root path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import requests
from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app.config import (
    LLM_API_KEY, LLM_BASE_URL, ANALYSIS_MODEL, DATE_MODEL,
    TOP_K_SHORTLIST, TOP_N_RANKING, MAX_PAIRS
)
from app.models import Person, Profile, DateResult, PersonRanking
from app.scrape.cache import get_cached, normalize_url, validate_linkedin_url, validate_instagram_url
from app.scrape.linkedin import scrape_linkedin
from app.scrape.instagram import scrape_instagram
from app.analyze import analyze_person
from app.shortlist import compute_shortlist
from app.dating import run_date, make_compact_profile
from app.ranking import compute_rankings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("controlled_pipeline")

DEMO_NEW_DIR = ROOT_DIR / "data" / "demo_new"
DEMO_DIR = ROOT_DIR / "data" / "demo"
CSV_PATH = ROOT_DIR / "data" / "people_agent.csv"


def ensure_dirs():
    DEMO_NEW_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_NEW_DIR / "profiles").mkdir(exist_ok=True)
    (DEMO_NEW_DIR / "dates").mkdir(exist_ok=True)


def check_groq_limits() -> dict:
    """Read real limits from Groq headers."""
    api_key = os.getenv("LLM_API_KEY", "").strip("\"'")
    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

    limits = {}
    for model in models:
        try:
            r = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "accept-encoding": "identity"
                },
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
                timeout=10
            )
            rl = {k: v for k, v in r.headers.items() if "ratelimit" in k.lower()}
            limits[model] = {
                "status": r.status_code,
                "remaining_requests": rl.get("x-ratelimit-remaining-requests", "N/A"),
                "limit_requests": rl.get("x-ratelimit-limit-requests", "N/A"),
                "remaining_tokens": rl.get("x-ratelimit-remaining-tokens", "N/A"),
                "limit_tokens": rl.get("x-ratelimit-limit-tokens", "N/A"),
                "reset_requests": rl.get("x-ratelimit-reset-requests", "N/A"),
                "reset_tokens": rl.get("x-ratelimit-reset-tokens", "N/A"),
            }
        except Exception as e:
            limits[model] = {"error": str(e)}
    return limits


def print_token_budget(limits: dict, num_people: int = 25, estimated_pairs: int = 35):
    print("\n" + "="*70)
    print(" RULE 3: TOKEN BUDGET & REAL GROQ LIMITS")
    print("="*70)
    for model, data in limits.items():
        if "error" in data:
            print(f"- {model}: Error ({data['error']})")
        else:
            print(f"- {model} (HTTP {data['status']}):")
            print(f"    Remaining Requests: {data['remaining_requests']} / {data['limit_requests']} (reset: {data['reset_requests']})")
            print(f"    Remaining Tokens:   {data['remaining_tokens']} / {data['limit_tokens']} (reset: {data['reset_tokens']})")

    analysis_tokens_per_person = 1300  # ~800 prompt + ~500 completion
    total_analysis_tokens = num_people * analysis_tokens_per_person

    # Compact profile date turns: ~460 tokens/turn * 6 turns = 2760
    # Scoring: 2 * ~530 = 1060
    # Total per date = ~3820 tokens
    date_tokens_per_pair = 3820
    total_date_tokens = estimated_pairs * date_tokens_per_pair

    total_tokens = total_analysis_tokens + total_date_tokens

    print("\n--- Estimated Pipeline Spending ---")
    print(f"1. Profile Analysis ({num_people} people):")
    print(f"   ~{analysis_tokens_per_person:,} tokens/person -> {total_analysis_tokens:,} tokens total (Target: qwen/qwen3.8-27b)")
    print(f"2. Dating Engine (~{estimated_pairs} candidate pairs):")
    print(f"   Compact profiles (no evidence strings) used.")
    print(f"   ~{date_tokens_per_pair:,} tokens/date -> {total_date_tokens:,} tokens total (Target: openai/gpt-oss-20b)")
    print(f"TOTAL ESTIMATED SPEND: ~{total_tokens:,} tokens across {num_people + (estimated_pairs * 8)} calls.")
    print("="*70 + "\n")


def load_people_input() -> list[dict]:
    people = []
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            people.append({
                "name": row.get("name", "").strip(),
                "linkedin_url": row.get("linkedin_url", "").strip(),
                "instagram_url": row.get("instagram_url", "").strip(),
            })
    return people


def make_slug(name: str, linkedin_url: str, instagram_url: str) -> str:
    if name:
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return slug or "person"
    url = linkedin_url or instagram_url
    parts = url.rstrip('/').split('/')
    return parts[-1].lower() if parts else "person"


def calculate_genericity_score(profile: Profile) -> float:
    """Calculate how generic a profile sounds.
    Higher score = more generic / clichéd.
    Lower score = more specific, grounded, unique evidence.
    """
    generic_words = [
        "passionate", "hardworking", "motivated", "enthusiastic", "leader",
        "visionary", "growth", "networking", "content creator", "journey",
        "community", "mindset", "success", "entrepreneur", "travel", "reading",
        "fitness", "lifestyle", "career coach", "digital"
    ]
    text_corpus = " ".join([
        profile.summary,
        profile.agent_persona,
        " ".join(n.item for n in profile.needs),
        " ".join(h.item for h in profile.hobbies),
        " ".join(i.item for i in profile.interests),
        " ".join(v.item for v in profile.values),
    ]).lower()

    # Evidence ratio: check length and specificity of evidence strings
    all_evidence = [
        n.evidence for n in profile.needs + profile.hobbies + profile.interests + profile.values
    ]
    avg_ev_len = sum(len(e) for e in all_evidence) / max(1, len(all_evidence))

    # Generic word occurrences
    generic_count = sum(text_corpus.count(w) for w in generic_words)

    # Inferred vs direct quotes
    inferred_count = sum(1 for e in all_evidence if "inferred" in e.lower())

    # Genericity score formula: more generic words + short evidence + heavy inference
    score = (generic_count * 2.5) + (inferred_count * 2.0) - (avg_ev_len / 15.0)
    return round(score, 2)


async def stage_analyze():
    ensure_dirs()
    people_raw = load_people_input()
    print(f"\n--- STAGE 1: SCRAPE & ANALYZE ({len(people_raw)} PEOPLE) ---")

    people: list[Person] = []
    seen = set()
    for row in people_raw:
        li_url = row["linkedin_url"]
        ig_url = row["instagram_url"]
        key = f"{li_url}|{ig_url}"
        if key in seen:
            continue
        seen.add(key)
        slug = make_slug(row["name"], li_url, ig_url)
        warnings = []
        if li_url and not validate_linkedin_url(li_url):
            warnings.append("Invalid LinkedIn URL")
            li_url = ""
        if ig_url and not validate_instagram_url(ig_url):
            warnings.append("Invalid Instagram URL")
            ig_url = ""

        p = Person(
            id=slug,
            name=row["name"],
            linkedin_url=li_url,
            instagram_url=ig_url,
            warnings=warnings
        )
        people.append(p)

    # Step 1: Scrape (from cache or live)
    for p in people:
        li = await scrape_linkedin(p.linkedin_url) if p.linkedin_url else None
        ig = await scrape_instagram(p.instagram_url) if p.instagram_url else None

        if not li:
            p.warnings.append("LinkedIn data missing or scrape failed")
        if not ig:
            p.warnings.append("Instagram data missing or scrape failed")
        elif ig.is_private:
            p.warnings.append("Instagram is private")

        if not li and not ig:
            p.status = "failed"
        elif not li or not ig or (ig and ig.is_private):
            p.status = "partial"
        else:
            p.status = "ready"

        # Update name if empty
        if not p.name or p.name == p.id:
            if li and li.name:
                p.name = li.name
            elif ig and ig.full_name:
                p.name = ig.full_name

    # Step 2: Analyze (resumable)
    profiles: dict[str, Profile] = {}
    profiles_dir = DEMO_NEW_DIR / "profiles"

    for i, p in enumerate(people):
        if p.status == "failed":
            continue

        target_file = profiles_dir / f"{p.id}.json"
        if target_file.exists():
            try:
                data = json.loads(target_file.read_text(encoding="utf-8"))
                profiles[p.id] = Profile(**data)
                print(f"[{i+1}/{len(people)}] Profile for {p.name} ({p.id}) loaded from disk (model: {data.get('model_used', 'unknown')})")
                continue
            except Exception as e:
                logger.warning(f"Failed to load cached profile for {p.id}: {e}")

        # Need to run analysis
        li = await scrape_linkedin(p.linkedin_url) if p.linkedin_url else None
        ig = await scrape_instagram(p.instagram_url) if p.instagram_url else None

        print(f"[{i+1}/{len(people)}] Analyzing {p.name} ({p.id})...")
        profile = await analyze_person(p.id, li, ig)
        if profile:
            profiles[p.id] = profile
            target_file.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            print(f"  -> Analyzed successfully via {profile.model_used} and saved to {target_file.name}")
        else:
            p.status = "failed"
            p.warnings.append("LLM Analysis failed")
            print(f"  -> Analysis FAILED for {p.name}")

    # Persist people.json in demo_new
    people_dicts = [p.model_dump() for p in people]
    (DEMO_NEW_DIR / "people.json").write_text(json.dumps(people_dicts, indent=2), encoding="utf-8")

    # RULE 6 REPORT
    print("\n" + "="*70)
    print(" RULE 6 REPORT: FAILED / PARTIAL PROFILES & 3 MOST GENERIC PROFILES")
    print("="*70)

    failed_people = [p for p in people if p.status == "failed"]
    partial_people = [p for p in people if p.status == "partial"]

    print(f"\n1. Failed People ({len(failed_people)}):")
    if not failed_people:
        print("   None! All 25 profiles had accessible data.")
    for p in failed_people:
        print(f"   - {p.name} ({p.id}): Warnings: {', '.join(p.warnings)}")

    print(f"\n2. Partial People ({len(partial_people)}):")
    if not partial_people:
        print("   None! All 25 profiles had full two-source data.")
    for p in partial_people:
        print(f"   - {p.name} ({p.id}): Warnings: {', '.join(p.warnings)}")

    # Calculate genericity
    scored_profiles = []
    for pid, prof in profiles.items():
        g_score = calculate_genericity_score(prof)
        scored_profiles.append((g_score, pid, prof))

    scored_profiles.sort(key=lambda x: x[0], reverse=True)

    print(f"\n3. Top 3 Most Generic-Sounding Profiles (Rule 6):")
    for rank, (score, pid, prof) in enumerate(scored_profiles[:3], 1):
        person_obj = next((p for p in people if p.id == pid), None)
        pname = person_obj.name if person_obj else pid
        print(f"\n   #{rank}: {pname} (ID: {pid}, Genericity Score: {score})")
        print(f"        Summary: {prof.summary[:140]}...")
        print(f"        Persona: {prof.agent_persona}")
        print(f"        Key items: {', '.join(h.item for h in prof.hobbies[:2])} | {', '.join(v.item for v in prof.values[:2])}")
    print("="*70 + "\n")


async def stage_pilot_dates():
    ensure_dirs()
    profiles_dir = DEMO_NEW_DIR / "profiles"
    dates_dir = DEMO_NEW_DIR / "dates"

    profiles = {}
    for pf in profiles_dir.glob("*.json"):
        data = json.loads(pf.read_text(encoding="utf-8"))
        profiles[data["id"]] = Profile(**data)

    people_data = json.loads((DEMO_NEW_DIR / "people.json").read_text(encoding="utf-8"))
    names = {p["id"]: p["name"] for p in people_data}

    print(f"Loaded {len(profiles)} profiles for shortlisting.")
    pairs, similarities = compute_shortlist(profiles)
    print(f"Total candidate pairs shortlisted: {len(pairs)}")

    # Take first 3 pairs for Rule 7
    pilot_pairs = pairs[:3]
    print("\n" + "="*70)
    print(" RULE 7 PILOT DATES: RUNNING FIRST 3 DATES")
    print("="*70)

    pilot_results = []
    for idx, (a_id, b_id) in enumerate(pilot_pairs, 1):
        target_file = dates_dir / f"{a_id}__{b_id}.json"
        if target_file.exists():
            print(f"Date {idx}/3 ({names[a_id]} & {names[b_id]}) already exists on disk. Loading...")
            d = json.loads(target_file.read_text(encoding="utf-8"))
            pilot_results.append(DateResult(**d))
            continue

        print(f"\nRunning Date {idx}/3: {names[a_id]} ({a_id}) <-> {names[b_id]} ({b_id})...")
        res = await run_date(
            a_id=a_id,
            b_id=b_id,
            a_name=names[a_id],
            b_name=names[b_id],
            a_profile=profiles[a_id],
            b_profile=profiles[b_id],
        )
        target_file.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        pilot_results.append(res)
        print(f"  -> Date complete! Final Score: {res.final_score} (Model: {res.model_used})")

    # RULE 7 PRESENTATION
    print("\n" + "="*70)
    print(" RULE 7 REPORT: TRANSCRIPTS & SCORE SPREAD (FIRST 3 DATES)")
    print("="*70)

    scores = []
    for idx, res in enumerate(pilot_results, 1):
        a_name = names.get(res.a, res.a)
        b_name = names.get(res.b, res.b)
        scores.append(res.final_score)
        print(f"\n--- DATE #{idx}: {a_name} & {b_name} ---")
        print(f"Final Score: {res.final_score}/100 | Model: {res.model_used}")
        print(f"{a_name} Verdict: Score={res.a_verdict.score}, 2nd Date={res.a_verdict.would_second_date}")
        print(f"   Chemistry: {res.a_verdict.chemistry}")
        print(f"   Concerns:  {res.a_verdict.concerns}")
        print(f"{b_name} Verdict: Score={res.b_verdict.score}, 2nd Date={res.b_verdict.would_second_date}")
        print(f"   Chemistry: {res.b_verdict.chemistry}")
        print(f"   Concerns:  {res.b_verdict.concerns}")
        print("\nTranscript:")
        for t in res.transcript:
            spk = a_name if t.speaker == "a" else b_name
            print(f"   [{spk}]: {t.text}")

    print("\n--- Pilot Score Spread Analysis ---")
    print(f"Scores: {scores}")
    print(f"Mean Score: {sum(scores)/len(scores):.1f}")
    print(f"Score Range: Min={min(scores)}, Max={max(scores)}")
    all_above_75 = all(s > 75 for s in scores)
    print(f"Are all scores > 75? {'YES - WARNING (Calibration needed)' if all_above_75 else 'NO - Good spread!'}")
    print("="*70 + "\n")


async def stage_full_dates():
    ensure_dirs()
    profiles_dir = DEMO_NEW_DIR / "profiles"
    dates_dir = DEMO_NEW_DIR / "dates"

    profiles = {}
    for pf in profiles_dir.glob("*.json"):
        data = json.loads(pf.read_text(encoding="utf-8"))
        profiles[data["id"]] = Profile(**data)

    people_data = json.loads((DEMO_NEW_DIR / "people.json").read_text(encoding="utf-8"))
    names = {p["id"]: p["name"] for p in people_data}

    pairs, similarities = compute_shortlist(profiles)
    print(f"Loaded {len(profiles)} profiles, {len(pairs)} candidate pairs.")

    all_date_results = []
    completed_count = 0
    skipped_count = 0

    for idx, (a_id, b_id) in enumerate(pairs, 1):
        target_file = dates_dir / f"{a_id}__{b_id}.json"
        if target_file.exists():
            try:
                d = json.loads(target_file.read_text(encoding="utf-8"))
                all_date_results.append(DateResult(**d))
                skipped_count += 1
                continue
            except Exception:
                pass

        print(f"[{idx}/{len(pairs)}] Running date: {names.get(a_id, a_id)} <-> {names.get(b_id, b_id)}...")
        res = await run_date(
            a_id=a_id,
            b_id=b_id,
            a_name=names.get(a_id, a_id),
            b_name=names.get(b_id, b_id),
            a_profile=profiles[a_id],
            b_profile=profiles[b_id],
        )
        target_file.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        all_date_results.append(res)
        completed_count += 1

    print(f"\nAll dates finished! Newly executed: {completed_count}, Reused from cache: {skipped_count}, Total: {len(all_date_results)}")

    # Compute rankings
    people_objects = [Person(**p) for p in people_data]
    rankings = compute_rankings(people_objects, all_date_results)
    rankings_dicts = [r.model_dump() for r in rankings]
    (DEMO_NEW_DIR / "rankings.json").write_text(json.dumps(rankings_dicts, indent=2), encoding="utf-8")
    print(f"Computed rankings for {len(rankings)} people and saved to {DEMO_NEW_DIR / 'rankings.json'}")


def stage_swap_and_report():
    print("\n" + "="*70)
    print(" RULE 1 & RULE 8: VALIDATION, SWAP & FINAL REPORT")
    print("="*70)

    # 1. Validation checks
    people_file = DEMO_NEW_DIR / "people.json"
    rankings_file = DEMO_NEW_DIR / "rankings.json"
    profiles_dir = DEMO_NEW_DIR / "profiles"
    dates_dir = DEMO_NEW_DIR / "dates"

    if not people_file.exists() or not rankings_file.exists():
        print("ERROR: people.json or rankings.json missing in demo_new!")
        sys.exit(1)

    people = json.loads(people_file.read_text(encoding="utf-8"))
    rankings = json.loads(rankings_file.read_text(encoding="utf-8"))
    profile_files = list(profiles_dir.glob("*.json"))
    date_files = list(dates_dir.glob("*.json"))

    print("--- Checks on demo_new ---")
    print(f"✓ People: {len(people)} entries")
    print(f"✓ Profiles: {len(profile_files)} profile JSONs")
    print(f"✓ Dates: {len(date_files)} date JSONs")
    print(f"✓ Rankings: {len(rankings)} ranked people")

    if len(profile_files) < 20 or len(date_files) < 10:
        print("ERROR: Counts too low for production swap!")
        sys.exit(1)

    # 2. Swap into data/demo/
    print("\nSwapping data/demo_new into active data/demo...")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "profiles").mkdir(exist_ok=True)
    (DEMO_DIR / "dates").mkdir(exist_ok=True)

    # Copy files over
    shutil.copy2(people_file, DEMO_DIR / "people.json")
    shutil.copy2(rankings_file, DEMO_DIR / "rankings.json")

    for pf in profile_files:
        shutil.copy2(pf, DEMO_DIR / "profiles" / pf.name)
    for df in date_files:
        shutil.copy2(df, DEMO_DIR / "dates" / df.name)

    print("✓ Successfully swapped into data/demo/!")

    # 3. Final Report (Rule 8)
    models_used_profiles = set()
    for pf in profile_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        if data.get("model_used"):
            models_used_profiles.add(data["model_used"])

    models_used_dates = set()
    scores = []
    failures = 0
    for df in date_files:
        data = json.loads(df.read_text(encoding="utf-8"))
        if data.get("model_used"):
            models_used_dates.add(data["model_used"])
        if data.get("date_failed"):
            failures += 1
        elif "final_score" in data:
            scores.append(data["final_score"])

    print("\n" + "="*70)
    print(" RULE 8 FINAL REPORT")
    print("="*70)
    print(f"Total People:         {len(people)}")
    print(f"Profiles Generated:   {len(profile_files)}")
    print(f"Pairs Dated:          {len(date_files)}")
    print(f"Date Failures:        {failures}")
    print(f"Models for Profiles:  {', '.join(models_used_profiles) or 'None'}")
    print(f"Models for Dates:     {', '.join(models_used_dates) or 'None'}")
    if scores:
        print(f"Score Distribution:   Min={min(scores)}, Max={max(scores)}, Mean={sum(scores)/len(scores):.1f}")
        bucket_low = sum(1 for s in scores if s < 45)
        bucket_mid = sum(1 for s in scores if 45 <= s <= 75)
        bucket_high = sum(1 for s in scores if s > 75)
        print(f"   Below 45: {bucket_low} | 45-75: {bucket_mid} | Above 75: {bucket_high}")
    print("="*70 + "\n")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["budget", "analyze", "pilot-dates", "full-dates", "swap"], required=True)
    args = parser.parse_args()

    if args.stage == "budget":
        limits = check_groq_limits()
        print_token_budget(limits)
    elif args.stage == "analyze":
        limits = check_groq_limits()
        print_token_budget(limits)
        await stage_analyze()
    elif args.stage == "pilot-dates":
        await stage_pilot_dates()
    elif args.stage == "full-dates":
        await stage_full_dates()
    elif args.stage == "swap":
        stage_swap_and_report()


if __name__ == "__main__":
    asyncio.run(main())
