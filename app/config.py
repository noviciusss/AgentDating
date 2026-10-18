"""
Configuration — all settings come from environment variables.
Never hardcode or log secrets.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEMO_DIR = DATA_DIR / "demo"
RUNS_DIR = DATA_DIR / "runs"
CACHE_DIR = DATA_DIR / "cache"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
for d in [DATA_DIR, DEMO_DIR, RUNS_DIR, CACHE_DIR,
          DEMO_DIR / "profiles", DEMO_DIR / "dates"]:
    d.mkdir(parents=True, exist_ok=True)

# ── Apify ──────────────────────────────────────────────────────────
APIFY_TOKEN: str = os.getenv("APIFY_TOKEN", "")
APIFY_INSTAGRAM_ACTOR: str = os.getenv("APIFY_INSTAGRAM_ACTOR", "apify/instagram-profile-scraper")
APIFY_LINKEDIN_ACTOR: str = os.getenv("APIFY_LINKEDIN_ACTOR", "harvestapi/linkedin-profile-scraper")
SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT", "120"))
SCRAPE_CONCURRENCY: int = int(os.getenv("SCRAPE_CONCURRENCY", "5"))

# ── LLM (primary) ─────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
ANALYSIS_MODEL: str = os.getenv("ANALYSIS_MODEL", "openai/gpt-oss-120b")
DATE_MODEL: str = os.getenv("DATE_MODEL", "openai/gpt-oss-20b")
LLM_RPM: int = int(os.getenv("LLM_RPM", "25"))

# ── LLM (fallback) ────────────────────────────────────────────────
FALLBACK_BASE_URL: str = os.getenv("FALLBACK_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
FALLBACK_API_KEY: str = os.getenv("FALLBACK_API_KEY", "")
FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "")

# ── Concurrency & limits ──────────────────────────────────────────
MAX_CONCURRENCY: int = int(os.getenv("MAX_CONCURRENCY", "4"))
TOP_K_SHORTLIST: int = int(os.getenv("TOP_K_SHORTLIST", "3"))
TOP_N_RANKING: int = int(os.getenv("TOP_N_RANKING", "5"))
MAX_PAIRS: int = int(os.getenv("MAX_PAIRS", "50"))
MAX_INSTAGRAM_POSTS: int = 20
