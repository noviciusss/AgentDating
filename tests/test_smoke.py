"""
Smoke test suite for all endpoints in Agent Dating.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
import os
import json

def test_full_app():
    client = TestClient(app)

    # 1. Test Home
    r = client.get("/")
    assert r.status_code == 200, f"Home failed: {r.status_code}"
    print("[PASS] GET /")

    # 2. Test Demo Load
    r = client.post("/api/demo/load")
    assert r.status_code == 200, f"Demo load failed: {r.status_code}"
    data = r.json()
    run_id = data.get("run_id")
    assert run_id == "demo", f"Unexpected run_id: {run_id}"
    print(f"[PASS] POST /api/demo/load -> run_id: {run_id}")

    # 3. Test People Page
    r = client.get(f"/run/{run_id}/people")
    assert r.status_code == 200, f"People page failed: {r.status_code}"
    assert "People" in r.text
    print("[PASS] GET /run/demo/people")

    # 4. Test Person Profile Page
    r = client.get(f"/run/{run_id}/person/diksha-arora")
    assert r.status_code == 200, f"Person page failed: {r.status_code}"
    assert "Diksha Arora" in r.text
    print("[PASS] GET /run/demo/person/diksha-arora")

    # 5. Test Dates List Page
    r = client.get(f"/run/{run_id}/dates")
    assert r.status_code == 200, f"Dates page failed: {r.status_code}"
    print("[PASS] GET /run/demo/dates")

    # 6. Test Single Date Transcript Page
    date_files = sorted(os.listdir("data/demo/dates"))
    assert len(date_files) > 0, "No dates found in data/demo/dates"
    with open(os.path.join("data/demo/dates", date_files[0]), encoding="utf-8") as f:
        sample_date = json.load(f)
    pair_id = f"{sample_date['a']}__{sample_date['b']}"
    r = client.get(f"/run/{run_id}/date/{pair_id}")
    assert r.status_code == 200, f"Date page failed: {r.status_code}"
    assert "Score Breakdown" in r.text
    print(f"[PASS] GET /run/demo/date/{pair_id}")

    # 7. Test Rankings Page
    r = client.get(f"/run/{run_id}/rankings")
    assert r.status_code == 200, f"Rankings page failed: {r.status_code}"
    assert "Rankings" in r.text
    print("[PASS] GET /run/demo/rankings")

    # 8. Test Validation on /api/runs (< 3 people)
    r = client.post("/api/runs", json={"people": [{"name": "Solo"}]})
    assert r.status_code == 400, f"Expected 400, got: {r.status_code}"
    print("[PASS] POST /api/runs (validation < 3 people)")

    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    test_full_app()
