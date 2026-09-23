"""Basic API tests. Run without GEMINI_API_KEY -> analyzer falls back to a
deterministic heuristic mode, so these tests validate the API contract and
error handling without requiring network access to Gemini."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_serves_frontend():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Notification Translator" in resp.text


def test_analyze_empty_input():
    resp = client.post("/api/analyze", json={"notifications": []})
    assert resp.status_code == 400


def test_analyze_all_blank_lines():
    resp = client.post("/api/analyze", json={"notifications": ["   ", ""]})
    assert resp.status_code == 400


def test_analyze_single_notification():
    resp = client.post(
        "/api/analyze",
        json={"notifications": ["GitHub: You were assigned issue #42."]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    result = body["results"][0]
    assert result["source"]
    assert result["category"] in (
        "ACTION_REQUIRED",
        "IMPORTANT",
        "INFORMATIONAL",
        "LOW_PRIORITY",
        "IGNORE",
    )
    assert result["urgency"] in ("HIGH", "MEDIUM", "LOW")


def test_analyze_multiple_notifications():
    resp = client.post(
        "/api/analyze",
        json={
            "notifications": [
                "GitHub: You were assigned issue #42.",
                "Amazon: Your package will arrive tomorrow.",
                "Instagram: Someone liked your post.",
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["results"]) == 3


def test_analyze_malformed_request():
    resp = client.post("/api/analyze", json={"notifications": "not-a-list"})
    assert resp.status_code == 422


def test_analyze_too_many_notifications():
    many = [f"App{i}: message {i}" for i in range(101)]
    resp = client.post("/api/analyze", json={"notifications": many})
    assert resp.status_code == 400
