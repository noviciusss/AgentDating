import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analyze import analyze_person
from app.models import RawLinkedIn, RawInstagram
from app.scrape.cache import get_cached, normalize_url

async def main():
    print("Testing analyze_person with qwen/qwen3.8-27b on cached data...")
    li_url = normalize_url("https://www.linkedin.com/in/garyvaynerchuk/")
    ig_url = normalize_url("https://www.instagram.com/garyvee/")

    li_data = get_cached(li_url)
    ig_data = get_cached(ig_url)

    li = RawLinkedIn(**li_data) if li_data else None
    ig = RawInstagram(**ig_data) if ig_data else None

    print(f"LinkedIn cached: {li is not None}, Instagram cached: {ig is not None}")
    profile = await analyze_person("gary-vaynerchuk", li, ig)
    if profile:
        print("\nAnalysis Succeeded!")
        print(f"Summary: {profile.summary}")
        print(f"Needs count: {len(profile.needs)}")
        print(f"Hobbies count: {len(profile.hobbies)}")
        print(f"Agent Persona: {profile.agent_persona}")
    else:
        print("\nAnalysis returned None!")

if __name__ == "__main__":
    asyncio.run(main())
