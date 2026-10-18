import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scrape.linkedin import scrape_linkedin
from app.scrape.instagram import scrape_instagram

async def main():
    print("Testing live scraping for 1 person...")
    # Test Gary Vaynerchuk or Diksha Arora
    li_url = "https://www.linkedin.com/in/garyvaynerchuk/"
    ig_url = "https://www.instagram.com/garyvee/"

    print(f"\n1. Scraping LinkedIn: {li_url}")
    li_res = await scrape_linkedin(li_url)
    if li_res:
        print(f"LinkedIn Success! Name: {li_res.name}, Headline: {li_res.headline[:50]}")
    else:
        print("LinkedIn returned None")

    print(f"\n2. Scraping Instagram: {ig_url}")
    ig_res = await scrape_instagram(ig_url)
    if ig_res:
        print(f"Instagram Success! Username: {ig_res.username}, Posts count: {len(ig_res.posts)}")
    else:
        print("Instagram returned None")

if __name__ == "__main__":
    asyncio.run(main())
