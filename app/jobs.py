"""
Job registry + SSE event bus.

Tracks pipeline runs in-memory and persists completed runs to disk.
Provides SSE streaming for real-time progress updates.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config import RUNS_DIR, DEMO_DIR
from app.models import RunState, ProgressEvent, Person, Profile, DateResult, PersonRanking

logger = logging.getLogger(__name__)

# ── In-memory job registry ─────────────────────────────────────────

_runs: dict[str, RunState] = {}
_event_queues: dict[str, list[asyncio.Queue]] = {}


def create_run(people: list[Person]) -> str:
    """Create a new run and return its ID."""
    run_id = str(uuid.uuid4())[:8]
    _runs[run_id] = RunState(run_id=run_id, people=people, status="pending")
    _event_queues[run_id] = []
    logger.info(f"Created run {run_id} with {len(people)} people")
    return run_id


def get_run(run_id: str) -> Optional[RunState]:
    """Get a run by ID."""
    return _runs.get(run_id)


def update_run(run_id: str, **kwargs):
    """Update run fields."""
    run = _runs.get(run_id)
    if run:
        for k, v in kwargs.items():
            setattr(run, k, v)


# ── SSE Event Bus ──────────────────────────────────────────────────

def subscribe(run_id: str) -> asyncio.Queue:
    """Subscribe to events for a run. Returns a queue."""
    q: asyncio.Queue = asyncio.Queue()
    if run_id not in _event_queues:
        _event_queues[run_id] = []
    _event_queues[run_id].append(q)
    return q


def unsubscribe(run_id: str, q: asyncio.Queue):
    """Unsubscribe from events."""
    if run_id in _event_queues:
        try:
            _event_queues[run_id].remove(q)
        except ValueError:
            pass


async def emit(run_id: str, event: ProgressEvent):
    """Emit a progress event to all subscribers."""
    run = _runs.get(run_id)
    if run:
        run.progress.append(event)
        run.current_stage = event.stage

    data = event.model_dump()
    for q in _event_queues.get(run_id, []):
        try:
            await q.put(data)
        except Exception:
            pass

    logger.debug(f"Event [{run_id}] {event.stage}: {event.message}")


# ── Persistence ────────────────────────────────────────────────────

def save_run_data(
    run_id: str,
    people: list[Person],
    profiles: dict[str, Profile],
    dates: list[DateResult],
    rankings: list[PersonRanking],
):
    """Persist run data to disk."""
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "profiles").mkdir(exist_ok=True)
    (run_dir / "dates").mkdir(exist_ok=True)

    # People
    people_data = [p.model_dump() for p in people]
    (run_dir / "people.json").write_text(
        json.dumps(people_data, indent=2), encoding='utf-8'
    )

    # Profiles
    for pid, profile in profiles.items():
        (run_dir / "profiles" / f"{pid}.json").write_text(
            json.dumps(profile.model_dump(), indent=2), encoding='utf-8'
        )

    # Dates
    for d in dates:
        filename = f"{d.a}__{d.b}.json"
        (run_dir / "dates" / filename).write_text(
            json.dumps(d.model_dump(), indent=2), encoding='utf-8'
        )

    # Rankings
    rankings_data = [r.model_dump() for r in rankings]
    (run_dir / "rankings.json").write_text(
        json.dumps(rankings_data, indent=2), encoding='utf-8'
    )

    logger.info(f"Saved run data to {run_dir}")


def load_run_data(run_dir: Path) -> Optional[dict]:
    """Load run data from disk. Returns dict with people, profiles, dates, rankings."""
    if not run_dir.exists():
        return None

    data = {}

    # People
    people_file = run_dir / "people.json"
    if people_file.exists():
        data["people"] = [
            Person(**p) for p in json.loads(people_file.read_text(encoding='utf-8'))
        ]

    # Profiles
    profiles = {}
    profiles_dir = run_dir / "profiles"
    if profiles_dir.exists():
        for f in profiles_dir.glob("*.json"):
            profile = Profile(**json.loads(f.read_text(encoding='utf-8')))
            profiles[profile.id] = profile
    data["profiles"] = profiles

    # Dates
    dates = []
    dates_dir = run_dir / "dates"
    if dates_dir.exists():
        for f in dates_dir.glob("*.json"):
            dates.append(DateResult(**json.loads(f.read_text(encoding='utf-8'))))
    data["dates"] = dates

    # Rankings
    rankings_file = run_dir / "rankings.json"
    if rankings_file.exists():
        data["rankings"] = [
            PersonRanking(**r) for r in json.loads(rankings_file.read_text(encoding='utf-8'))
        ]
    else:
        data["rankings"] = []

    return data


def load_demo() -> Optional[str]:
    """Load the demo data as the active run with id 'demo'."""
    demo_data = load_run_data(DEMO_DIR)
    if not demo_data:
        return None

    run_id = "demo"
    people = demo_data.get("people", [])
    _runs[run_id] = RunState(
        run_id=run_id,
        people=people,
        status="completed",
        current_stage="done",
    )

    # Store profiles, dates, rankings in a separate data store
    _run_data[run_id] = demo_data
    return run_id


# ── Run data store (profiles, dates, rankings per run) ─────────────

_run_data: dict[str, dict] = {}


def store_run_data(run_id: str, data: dict):
    """Store run data in memory."""
    _run_data[run_id] = data


def get_run_data(run_id: str) -> Optional[dict]:
    """Get stored run data. Falls back to disk."""
    if run_id in _run_data:
        return _run_data[run_id]

    # Try loading from disk
    if run_id == "demo":
        data = load_run_data(DEMO_DIR)
    else:
        data = load_run_data(RUNS_DIR / run_id)

    if data:
        _run_data[run_id] = data
    return data
