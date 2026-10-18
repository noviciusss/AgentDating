"""
FastAPI app — all routes per Section 11 of the spec.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from app.config import TEMPLATES_DIR, STATIC_DIR
from app.models import Person, ProgressEvent
from app.jobs import (
    create_run, get_run, subscribe, unsubscribe, load_demo,
    get_run_data, update_run, emit,
)
from app.pipeline import run_pipeline

# ── Setup ──────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Dating", description="AI agents date on your behalf")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Helper ─────────────────────────────────────────────────────────

def _get_names(run_data: dict) -> dict[str, str]:
    """Build id -> name map from run data."""
    names = {}
    for p in run_data.get("people", []):
        if isinstance(p, Person):
            names[p.id] = p.name
        elif isinstance(p, dict):
            names[p["id"]] = p.get("name", p["id"])
    return names


# ── Pages ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "run_id": None})


@app.get("/run/{run_id}/people", response_class=HTMLResponse)
async def people_page(request: Request, run_id: str):
    run_data = get_run_data(run_id)
    if not run_data:
        raise HTTPException(404, "Run not found")

    people = run_data.get("people", [])
    return templates.TemplateResponse("people.html", {
        "request": request,
        "run_id": run_id,
        "people": people,
        "active_nav": "people",
    })


@app.get("/run/{run_id}/person/{person_id}", response_class=HTMLResponse)
async def person_page(request: Request, run_id: str, person_id: str):
    run_data = get_run_data(run_id)
    if not run_data:
        raise HTTPException(404, "Run not found")

    people = run_data.get("people", [])
    person = None
    for p in people:
        pid = p.id if isinstance(p, Person) else p.get("id")
        if pid == person_id:
            person = p if isinstance(p, Person) else Person(**p)
            break

    if not person:
        raise HTTPException(404, "Person not found")

    profiles = run_data.get("profiles", {})
    profile = profiles.get(person_id)

    return templates.TemplateResponse("person.html", {
        "request": request,
        "run_id": run_id,
        "person": person,
        "profile": profile,
        "active_nav": "people",
    })


@app.get("/run/{run_id}/dates", response_class=HTMLResponse)
async def dates_page(request: Request, run_id: str, person: Optional[str] = None):
    run_data = get_run_data(run_id)
    if not run_data:
        raise HTTPException(404, "Run not found")

    dates = run_data.get("dates", [])
    people = run_data.get("people", [])
    names = _get_names(run_data)

    # Filter by person if specified
    if person:
        dates = [d for d in dates if
                 (d.a if hasattr(d, 'a') else d.get('a')) == person or
                 (d.b if hasattr(d, 'b') else d.get('b')) == person]

    return templates.TemplateResponse("dates.html", {
        "request": request,
        "run_id": run_id,
        "dates": dates,
        "people": people,
        "names": names,
        "filter_person": person,
        "active_nav": "dates",
    })


@app.get("/run/{run_id}/date/{pair_id}", response_class=HTMLResponse)
async def date_page(request: Request, run_id: str, pair_id: str):
    run_data = get_run_data(run_id)
    if not run_data:
        raise HTTPException(404, "Run not found")

    # Find the date
    dates = run_data.get("dates", [])
    date = None
    for d in dates:
        d_a = d.a if hasattr(d, 'a') else d.get('a')
        d_b = d.b if hasattr(d, 'b') else d.get('b')
        if f"{d_a}__{d_b}" == pair_id:
            date = d
            break

    if not date:
        raise HTTPException(404, "Date not found")

    names = _get_names(run_data)
    a_id = date.a if hasattr(date, 'a') else date.get('a')
    b_id = date.b if hasattr(date, 'b') else date.get('b')

    return templates.TemplateResponse("date.html", {
        "request": request,
        "run_id": run_id,
        "date": date,
        "a_name": names.get(a_id, a_id),
        "b_name": names.get(b_id, b_id),
        "active_nav": "dates",
    })


@app.get("/run/{run_id}/rankings", response_class=HTMLResponse)
async def rankings_page(request: Request, run_id: str):
    run_data = get_run_data(run_id)
    if not run_data:
        raise HTTPException(404, "Run not found")

    rankings = run_data.get("rankings", [])
    names = _get_names(run_data)

    return templates.TemplateResponse("rankings.html", {
        "request": request,
        "run_id": run_id,
        "rankings": rankings,
        "names": names,
        "active_nav": "rankings",
    })


from collections import defaultdict
import time
from app.config import (
    TEMPLATES_DIR, STATIC_DIR,
    MAX_PEOPLE_PER_RUN, MAX_RUNS_PER_HOUR, MAX_RUNS_PER_IP_PER_HOUR,
)

_global_run_timestamps: list[float] = []
_ip_run_timestamps: dict[str, list[float]] = defaultdict(list)
_pipeline_lock = asyncio.Lock()


async def _run_pipeline_queued(run_id: str, people_input: list[dict]):
    if _pipeline_lock.locked():
        update_run(run_id, status="queued", current_stage="queued")
        await emit(run_id, ProgressEvent(
            stage="queued", done=0, total=1,
            message="Queued behind another active run. Starting shortly…"
        ))
    async with _pipeline_lock:
        await run_pipeline(run_id, people_input)


# ── API Routes ─────────────────────────────────────────────────────

@app.post("/api/runs")
async def create_new_run(request: Request, background_tasks: BackgroundTasks):
    """Start a new pipeline run with Section 18.5 protections."""
    now = time.time()
    one_hour_ago = now - 3600

    # Clean old timestamps
    global _global_run_timestamps
    _global_run_timestamps = [t for t in _global_run_timestamps if t > one_hour_ago]

    client_ip = request.client.host if request.client else "unknown"
    _ip_run_timestamps[client_ip] = [t for t in _ip_run_timestamps[client_ip] if t > one_hour_ago]

    # Global and IP rate limits
    if len(_global_run_timestamps) >= MAX_RUNS_PER_HOUR:
        raise HTTPException(429, f"Hourly limit reached ({MAX_RUNS_PER_HOUR}/hr). Try again later.")

    if len(_ip_run_timestamps[client_ip]) >= MAX_RUNS_PER_IP_PER_HOUR:
        raise HTTPException(429, f"Rate limit reached for your IP ({MAX_RUNS_PER_IP_PER_HOUR}/hr).")

    body = await request.json()
    people_input = body.get("people", [])

    if len(people_input) < 3:
        raise HTTPException(400, "Need at least 3 people")

    if len(people_input) > MAX_PEOPLE_PER_RUN:
        raise HTTPException(400, f"Maximum {MAX_PEOPLE_PER_RUN} people per run on the live site to conserve quotas. The pre-computed demo features 25+ people.")

    # Record run timestamps
    _global_run_timestamps.append(now)
    _ip_run_timestamps[client_ip].append(now)

    # Create Person objects for the run
    people = []
    for entry in people_input:
        people.append(Person(
            id="pending",
            name=entry.get("name", ""),
            linkedin_url=entry.get("linkedin_url", ""),
            instagram_url=entry.get("instagram_url", ""),
        ))

    run_id = create_run(people)
    background_tasks.add_task(_run_pipeline_queued, run_id, people_input)

    return JSONResponse({"run_id": run_id})


@app.get("/api/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get current run state (for polling fallback)."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run.model_dump()


@app.get("/api/runs/{run_id}/events")
async def run_events(request: Request, run_id: str):
    """SSE stream of progress events."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    queue = subscribe(run_id)

    async def event_generator():
        try:
            # Send any existing progress events first
            for event in run.progress:
                yield {"event": "message", "data": json.dumps(event.model_dump())}

            # Stream new events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {"event": "message", "data": json.dumps(data)}
                    if data.get("stage") == "done":
                        break
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            unsubscribe(run_id, queue)

    return EventSourceResponse(event_generator())


@app.post("/api/demo/load")
async def load_demo_endpoint():
    """Load pre-computed demo data."""
    run_id = load_demo()
    if not run_id:
        raise HTTPException(404, "Demo data not found. Run scripts/run_batch.py first.")
    return JSONResponse({"run_id": run_id})
