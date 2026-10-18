# Agent Dating — Build Spec (for Antigravity)

You are building a working web app in ~2 hours. Read this whole file first, then build in the order given in section 12. Do not ask clarifying questions; where something is ambiguous, pick the simplest option and note it in `NOTES.md`.

---

## 1. What we are building

Each person is represented by an AI agent. The agent dates on that person's behalf. Agents date each other. Every person gets a ranking of who fits them best.

**Only two data sources exist for every person:** their public LinkedIn profile and their public Instagram profile. Nothing else. No other scraping, no self-reported forms.

Flow:

```
LinkedIn URL + Instagram URL
        -> scrape (Apify, cached)
        -> Analyze (LLM) -> structured profile + evidence
        -> Shortlist pairs (embeddings)
        -> Date (two LLM agents, multi-turn, private scoring)
        -> Rank (mutual score, asymmetry penalty)
        -> Profile pages + Date transcripts + Rankings pages
```

## 2. Hard requirements (this is how it is graded)

1. The site must **actually work**. Graders will paste their own public links and use every feature.
2. At least **25 real people**, each = one LinkedIn URL + one public Instagram URL.
3. A **profile page per person** showing the analysis: needs, hobbies, interests, other qualities, with evidence.
4. **Agents genuinely date**: real multi-turn conversations between two separate LLM agents, viewable as transcripts.
5. A **rankings page**: for every person, a ranked list of best matches, each linking to its date transcript.
6. A **pre-run demo** (already computed, loadable with one click, no typing, no live scraping).
7. Visible **progress** during long runs. Never a frozen page.
8. Public GitHub repo. No secrets, and no raw scraped data committed.

Not too flashy, not too boring: clean, readable, a little personality. No animations beyond simple progress bars.

## 3. Stack (do not change)

- **Backend:** Python 3.11+, FastAPI, uvicorn. Storage = JSON files on disk under `data/` (plus an in-memory job registry). No database server.
- **Frontend:** server-rendered HTML via Jinja2 templates + Tailwind via CDN + a little vanilla JS. **No React, no build step.**
- **Scraping:** Apify via the `apify-client` Python package.
  - Instagram: `apify/instagram-profile-scraper` (public profiles only).
  - LinkedIn: a no-cookie public profile scraper actor from the Apify store (e.g. `harvestapi/linkedin-profile-scraper`). **Verify the actor's current name and input schema in the Apify store/docs before coding**; actor names and inputs change. Wrap each actor behind an adapter that normalizes output into the internal schema in section 5, so swapping actors is a one-file change.
  - Never use a personal logged-in LinkedIn session or cookies.
- **LLM (free tier, provider-agnostic):** use the `openai` Python SDK (`AsyncOpenAI`) against any OpenAI-compatible endpoint. **No paid APIs.** Provider, base URL, key and model are all env vars, so switching providers is an env change, not a code change.
  - Primary (dates + analysis): **Groq** free plan, `base_url=https://api.groq.com/openai/v1`, model `openai/gpt-oss-120b` for analysis and `openai/gpt-oss-20b` for date turns (verify exact model IDs in the Groq console; fall back to `qwen3.8-27b` if one is unavailable). Free limits are about 30 requests/min and 1,000 requests/day, plus token limits shown in the Groq console.
  - Fallback: **Google AI Studio (Gemini)** OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/`, a Flash model (check the current ID in AI Studio). Free-tier prompts may be used by Google for product improvement, so use it only for people who consented.
  - Optional second fallback: OpenRouter `:free` models (only ~50 requests/day on free, so emergency use only).
  - `llm.py` must: enforce a global rate limiter (`LLM_RPM`, default 25 requests/minute), retry on 429/5xx with exponential backoff and honor `Retry-After`, and automatically fail over to the fallback provider when the primary returns repeated 429s. Request JSON mode (`response_format={"type":"json_object"}`) where supported and still parse tolerantly, since smaller models wrap JSON in prose or code fences.
  - Smaller models drift and agree too much: keep prompts short, keep the persona instructions, and cap output with `max_tokens`.
- **Embeddings:** use `sentence-transformers` (`all-MiniLM-L6-v2`) locally so there is no extra API key. If install size is a problem on the host, fall back to a TF-IDF cosine similarity with scikit-learn. Embeddings are used only to shortlist pairs.
- **Concurrency:** `asyncio` with a semaphore (default 4) around LLM calls. Use `AsyncOpenAI`.
- **Deploy:** Render (web service). Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## 4. Repo structure

```
agent-dating/
  README.md                  # what it is, architecture, how to run, tech section
  NOTES.md                   # assumptions you made
  requirements.txt
  .env.example
  .gitignore                 # includes .env, data/cache/, data/raw/
  render.yaml                # optional
  app/
    main.py                  # FastAPI app, routes
    config.py                # env vars, constants
    models.py                # Pydantic models
    scrape/
      __init__.py
      apify_client.py        # run actor, retry once, timeout
      instagram.py           # adapter -> RawInstagram
      linkedin.py            # adapter -> RawLinkedIn
      cache.py               # disk cache keyed by sha1(url)
    analyze.py               # raw -> Profile via LLM
    shortlist.py             # embeddings, top-K pairs
    dating.py                # date engine (turns + scoring)
    ranking.py               # scoring formula, per-person lists
    jobs.py                  # job registry + SSE event bus
    llm.py                   # AsyncOpenAI wrapper (provider-agnostic, rate limiter, failover), JSON parsing, retries
    prompts.py               # all prompts live here
  templates/
    base.html
    index.html               # paste links + run + load demo
    person.html              # profile page
    dates.html               # list of dates
    date.html                # one transcript
    rankings.html            # per-person rankings
  static/
    app.js                   # SSE client, small helpers
  data/
    demo/                    # COMMITTED: processed output for the pre-run demo
      people.json
      profiles/{id}.json
      dates/{idA}__{idB}.json
      rankings.json
    runs/                    # gitignored: user runs
    cache/                   # gitignored: raw scrape cache
  scripts/
    run_batch.py             # CLI: input file of links -> full pipeline -> data/demo
    seed_people.example.csv  # columns: name,linkedin_url,instagram_url
```

## 5. Data schemas

### RawLinkedIn (normalized from the actor)
```json
{"url": "", "name": "", "headline": "", "about": "", "location": "",
 "experience": [{"title": "", "company": "", "description": ""}],
 "education": [{"school": "", "degree": ""}],
 "skills": [], "posts": []}
```

### RawInstagram (normalized from the actor)
```json
{"url": "", "username": "", "full_name": "", "bio": "", "is_private": false,
 "followers": 0, "following": 0,
 "posts": [{"caption": "", "hashtags": [], "location": "", "likes": 0, "timestamp": ""}]}
```
Keep at most the latest 20 posts. Captions only; do **not** download or store images.

### Person
```json
{"id": "slug", "name": "", "linkedin_url": "", "instagram_url": "",
 "status": "ok | partial | failed", "warnings": []}
```
`partial` = one source missing or unusable. The pipeline continues with whatever exists and the profile page shows which source was missing.

### Profile (LLM output, stored per person)
```json
{
  "id": "slug",
  "summary": "2-3 sentence read of the person",
  "needs": [{"item": "", "evidence": ""}],
  "hobbies": [{"item": "", "evidence": ""}],
  "interests": [{"item": "", "evidence": ""}],
  "values": [{"item": "", "evidence": ""}],
  "communication_style": {"description": "", "evidence": ""},
  "personality_signals": [{"item": "", "evidence": ""}],
  "looking_for": {"description": "", "confidence": "low|medium|high", "evidence": ""},
  "dealbreakers": [{"item": "", "evidence": ""}],
  "lifestyle": {"description": "", "evidence": ""},
  "agent_persona": "2 lines: how this agent talks and behaves on dates",
  "data_quality": {"linkedin": "none|thin|rich", "instagram": "none|thin|rich"}
}
```
Every claim needs `evidence`: a short quote or a concrete reference to a post/role ("IG post: 'sunrise trek at Triund'", "LinkedIn headline: ..."). If a claim has no evidence, it must not appear. Where data is thin, say so in `data_quality` and keep lists short rather than inventing things.

### DateResult
```json
{"a": "idA", "b": "idB",
 "transcript": [{"speaker": "a|b", "text": ""}],
 "a_verdict": {"score": 0, "chemistry": "", "concerns": "", "would_second_date": false},
 "b_verdict": {"score": 0, "chemistry": "", "concerns": "", "would_second_date": false},
 "final_score": 0.0}
```

### Ranking
```json
{"person_id": "", "matches": [{"other_id": "", "score": 0.0, "dated": true,
  "reason": "", "date_ref": "idA__idB"}]}
```

## 6. Scraping rules

- Cache every actor result on disk by `sha1(normalized_url)`. Check the cache before calling Apify. A cache hit must never touch the network.
- Normalize URLs (strip query strings, trailing slashes, lowercase host). Validate that LinkedIn URLs contain `linkedin.com/in/` and Instagram URLs have a username.
- Timeout per actor run (default 120s). On failure, **retry once**, then mark that source missing and continue.
- Instagram `is_private == true` -> mark Instagram missing, add warning "Instagram is private", continue with LinkedIn only. Never crash.
- Missing LinkedIn -> continue with Instagram only. Both missing -> person `failed`, excluded from dating, shown with a clear message.
- Run all scrapes concurrently (semaphore 5).
- Respect only public data. Do not try to bypass login walls.

## 7. Analysis (ANALYSIS_MODEL)

One call per person. Input = normalized LinkedIn + Instagram JSON. Output = Profile JSON (section 5), strict JSON only, parsed with a tolerant parser (strip code fences, retry once on parse failure).

System prompt (put in `prompts.py`):

```
You are a perceptive analyst building a profile of one person from exactly two sources: their public LinkedIn and their public Instagram. You have nothing else.

Rules:
1. Every item in needs, hobbies, interests, values, personality_signals, dealbreakers, lifestyle, communication_style and looking_for MUST include an "evidence" field: a short quote or a specific reference to a post, caption, headline, role, or school from the data. If you cannot point to evidence, leave the item out.
2. Distinguish what is stated from what is inferred. For inferences, say "inferred from ..." in the evidence.
3. Be specific. "Enjoys travel" is useless. "Posts mountain treks and mentions solo trips (IG: 'Triund, 3am start')" is good. Generic horoscope-style statements are a failure.
4. Do not invent a relationship status, orientation, health condition, religion, politics, caste, or anything sensitive that is not explicitly stated. Do not speculate about these. Leave out.
5. If a source is empty or thin, say so in data_quality and keep your lists short. Do not pad.
6. "looking_for" describes what this person would plausibly want in a match (personality, lifestyle, ambition) based only on the evidence. Set confidence honestly; it is usually low or medium.
7. agent_persona: two lines describing how an agent speaking for this person should talk (tone, humor, directness, what they would probe or push back on). It must be consistent with the evidence.
Return ONLY valid JSON matching the provided schema. No prose, no code fences.
```

Profile page (`person.html`) must render: name + both source links, data-quality badges, summary, then each section as cards with the **evidence shown under each item** (small muted text). Show warnings (private IG, missing source) at the top.

## 8. Shortlisting

- Build one text blob per person from their Profile (summary, needs, hobbies, interests, values, looking_for).
- Embed, compute cosine similarity matrix.
- For each person take top-K (default K=3) most similar others. Union of pairs, deduplicated and order-independent (`min(a,b)__max(a,b)`). For 25 people this gives ~40-50 pairs.
- Store the similarity score for every pair, since non-dated pairs use it as fallback in rankings.
- Add a config `MAX_PAIRS` (default 50) as a safety cap.

## 9. Date engine (the part graded hardest)

For each shortlisted pair, run a first date between Agent A and Agent B.

- **Two separate LLM call streams.** Agent A's system prompt contains **only** person A's profile. Agent B's contains **only** person B's profile. Neither agent ever sees the other's profile, only what the other says. This is what makes it a real date rather than a script.
- 3 rounds = 6 turns, alternating A then B. Each turn: 1–3 sentences, conversational. The agent sees the full transcript so far (as alternating user/assistant messages from its own perspective).
- Model: `DATE_MODEL`. Max tokens ~150 per turn, temperature ~0.9.

Agent system prompt template:

```
You are the AI agent representing {name} on a first date with another person's agent. You speak AS {name}, in first person, grounded ONLY in this profile of them:

{profile_json}

Persona: {agent_persona}

Rules:
- Stay in character. Use details from the profile naturally; do not dump them.
- This is a real first date, not a pitch. Be curious: ask the other person real questions and react to their answers.
- Be honest. If something they say clashes with {name}'s values, needs or dealbreakers, push back politely or show hesitation. Do NOT agree with everything. Chemistry has to be earned.
- Show personality: humor, a little flirting if it fits the persona, a playful disagreement now and then.
- Never invent facts about {name} that contradict or go beyond the profile. If asked about something unknown, deflect naturally ("ha, that's a story for date two").
- 1 to 3 sentences per turn. No stage directions, no asterisks, no meta commentary.
- Turn {turn_no} of 6. {opening_or_closing_hint}
```
`opening_or_closing_hint`: turn 1 = "Open warmly and break the ice." Turn 5–6 = "Start wrapping up the date naturally."

After the 6 turns, each agent gets a **private** scoring call (it sees the transcript and its own profile only):

```
The date is over. Privately evaluate how well this match fits {name}, using {name}'s needs, values, looking_for and dealbreakers, and what actually happened in the conversation. Be calibrated and critical: most dates should land between 35 and 80. Scores above 85 are rare; below 30 means a clear mismatch. Return ONLY JSON:
{"score": 0-100, "chemistry": "2 sentences, specific to what happened", "concerns": "1-2 sentences, specific", "would_second_date": true|false}
```

Concurrency: `asyncio.gather` across pairs with a semaphore (`MAX_CONCURRENCY`, default 4), all calls going through the global `LLM_RPM` limiter. Free-tier budget: with ~40 pairs x (6 turns + 2 scoring calls) = ~320 calls plus ~30 analysis calls, a full 25-person run is ~350 calls (about 12-15 minutes at 25 RPM, under the 1,000/day cap). Do not run the full batch more than twice a day. Retry any failed LLM call once with backoff; if a date still fails, mark that pair `date_failed` and use the embedding fallback.

Emit a progress event on each completed turn and each completed date.

## 10. Ranking

For each dated pair:

```
mean      = (scoreA + scoreB) / 2
asym_pen  = 0.3 * abs(scoreA - scoreB)
bonus     = 5 if both would_second_date else 0
final     = clamp(mean - asym_pen + bonus, 0, 100)
```

Per person: collect every pair involving them. Dated pairs use `final`. Non-dated pairs use `embedding_similarity * 60` (scaled so they sit below most real dates) and are flagged `dated: false` and labeled "not dated (similarity estimate)". Sort descending, keep the top 5 (configurable, `TOP_N`). `reason` = the person's own agent's `chemistry` text plus its `concerns` (this is why the ranking is explainable). Each row links to the date transcript.

## 11. Web app

### Routes
- `GET /` — Home. Form with two repeating fields per person (LinkedIn URL, Instagram URL), an "Add person" button, and a textarea "paste CSV" option (`name,linkedin_url,instagram_url`). Buttons: **Run**, **Load demo**. Show the minimum number of people needed (at least 3 to run; the demo has 25+).
- `POST /api/runs` — body: list of people. Validates URLs, creates a run id, starts the pipeline in a background task, returns `{run_id}`.
- `GET /api/runs/{run_id}/events` — **SSE** stream of progress events: `{stage, done, total, message}` for stages `scrape`, `analyze`, `shortlist`, `date`, `rank`, `done`. The home page shows a stage checklist + progress bar from this stream.
- `GET /api/runs/{run_id}` — current state JSON (for polling fallback and reload).
- `POST /api/demo/load` — loads `data/demo/*` as the active run (no network, no LLM).
- `GET /run/{run_id}/people` — grid of all people with status badges and links to profile pages.
- `GET /run/{run_id}/person/{id}` — profile page (section 7).
- `GET /run/{run_id}/dates` — list of all dates with scores; filter by person.
- `GET /run/{run_id}/date/{a}__{b}` — transcript viewer: chat-bubble layout, A left / B right, then both verdicts (score, chemistry, concerns, second-date yes/no) and the final score with the formula breakdown.
- `GET /run/{run_id}/rankings` — one collapsible card per person with their top 5 matches (name, score, reason, link to the date). A person selector at the top to jump.
- The demo is just a run with id `demo`.

### UX requirements
- Clean, light layout; one accent color. Tailwind CDN. Mobile OK, not fancy.
- Top nav: People · Dates · Rankings (scoped to the current run).
- Every error message must be human-readable (e.g. "Instagram profile is private, using LinkedIn only").
- A person with `failed` status is shown, explained, and excluded; it never breaks the run.
- During a run the page streams progress; if SSE drops, fall back to polling `/api/runs/{id}` every 2s.
- Persist run state to `data/runs/{run_id}/` so a server restart doesn't lose a finished run.

## 12. Build order (follow strictly)

1. Scaffold the repo, `requirements.txt`, `.env.example`, FastAPI hello page. Commit.
2. Scrape layer: Apify client, cache, both adapters. Test on 2 real people via `scripts/run_batch.py`. Print normalized JSON.
3. Analyze: prompt + parser + `person.html`. Test on those 2 people.
4. Date engine for one pair + `date.html` transcript viewer.
5. Shortlist + ranking + `rankings.html`.
6. Jobs + SSE + home page form + `Load demo`.
7. Run the full batch on all 25–30 people via `scripts/run_batch.py`; write to `data/demo/` and commit **processed output only**.
8. Deploy to Render, set env vars, test with fresh links, a private IG, and a missing LinkedIn.
9. Write `README.md`.

If time runs short, cut in this order: asymmetry/bonus polish -> dates list filters -> CSV paste. **Never cut:** profile evidence, real multi-turn dates, rankings, demo load, progress stream.

## 13. Environment variables (`.env.example`)

```
APIFY_TOKEN=
LLM_PROVIDER=groq
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=
ANALYSIS_MODEL=openai/gpt-oss-120b
DATE_MODEL=openai/gpt-oss-20b
FALLBACK_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
FALLBACK_API_KEY=
FALLBACK_MODEL=
LLM_RPM=25
APIFY_INSTAGRAM_ACTOR=apify/instagram-profile-scraper
APIFY_LINKEDIN_ACTOR=harvestapi/linkedin-profile-scraper
MAX_CONCURRENCY=4
SCRAPE_CONCURRENCY=5
TOP_K_SHORTLIST=3
TOP_N_RANKING=5
MAX_PAIRS=50
```

Read all keys from env only. Never hardcode or log secrets.

## 14. Privacy and repo hygiene

- `.gitignore`: `.env`, `data/cache/`, `data/runs/`, `data/raw/`, `__pycache__/`.
- Do **not** commit raw scraped LinkedIn/Instagram JSON. `data/demo/` contains only the processed Profile/Date/Ranking output (and names + profile links the people consented to).
- Do not store or download images.
- Profiles must not contain sensitive inferences (see analysis rule 4).
- README should say: only public data is used, people in the demo gave consent, and scraping LinkedIn via third-party actors may conflict with platform terms.

## 15. Testing checklist (run before calling it done)

- [ ] Fresh run with 3 new people end-to-end, with progress visible
- [ ] Person with private Instagram -> run completes, warning shown, profile built from LinkedIn
- [ ] Person with missing/invalid LinkedIn URL -> clear error, no crash
- [ ] Duplicate URL submitted twice -> deduped
- [ ] Second run with same URLs hits cache (no Apify calls)
- [ ] LLM provider 429/5xx (and failover to fallback) -> retried, run still finishes
- [ ] Demo loads with zero network calls
- [ ] Profile page shows evidence under every item
- [ ] Transcript shows real back-and-forth with pushback, not 6 turns of agreement
- [ ] Score spread across dates is realistic (not all 80+)
- [ ] Rankings: every person has up to 5 matches, each linking to a working transcript
- [ ] Works on the deployed URL, not only localhost

## 16. README.md must contain

1. One-breath pitch (<= 200 chars): *Each person gets an AI agent that reads their LinkedIn and public Instagram, builds a profile, then dates other agents on their behalf. The dates produce a ranked list of best matches for everyone.*
2. Architecture diagram (ASCII or Mermaid) of the pipeline.
3. **Technical section:** Apify actors scrape public Instagram and LinkedIn profiles (no logged-in sessions), cached as JSON; an open-weight LLM (gpt-oss via Groq's free tier, Gemini Flash fallback) extracts structured, evidence-backed profiles; embeddings shortlist pairs; separate LLM agents hold multi-turn dates and score privately; FastAPI + async orchestration; ranked by mutual score with an asymmetry penalty.
4. How to run locally and how to run `scripts/run_batch.py`.
5. Demo link and live site link placeholders.
6. Limitations (scraper availability, public data only, LLM-based scores are subjective).

## 17. Definition of done

A grader can open the live site, click **Load demo**, see 25+ people, open a profile with evidence, open a real date transcript, and see per-person rankings; then paste their own two public links per person, watch progress, and get the same outputs without errors.
