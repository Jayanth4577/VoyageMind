"""Phase 8 hardening tests: rate limiting + graceful AI unavailability."""
from app.core import rate_limit as rl
from app.core.config import settings


def auth_headers(client, email="rl@example.com"):
    res = client.post(
        "/auth/register", json={"email": email, "password": "supersecret1"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_rate_limit_blocks_after_budget(client, monkeypatch):
    rl.reset_rate_limiter()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 5)
    monkeypatch.setattr(settings, "auth_rate_limit_per_minute", 1000)

    codes = [client.get("/health").status_code for _ in range(7)]
    # /health is exempt? No — it's rate-limited too; first 5 pass, rest 429
    assert codes[:5] == [200] * 5
    assert codes[5] == 429 and codes[6] == 429

    blocked = client.get("/health")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert "Too many requests" in blocked.json()["detail"]
    rl.reset_rate_limiter()


def test_auth_endpoints_have_stricter_budget(client, monkeypatch):
    rl.reset_rate_limiter()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1000)
    monkeypatch.setattr(settings, "auth_rate_limit_per_minute", 3)

    codes = [
        client.post(
            "/auth/register",
            json={"email": f"rl{i}@example.com", "password": "supersecret1"},
        ).status_code
        for i in range(5)
    ]
    # First 3 requests reach the handler (201 created / 409 duplicate are fine),
    # the rest are rejected before hitting the route.
    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429 and codes[4] == 429
    rl.reset_rate_limiter()


def test_generate_returns_503_without_llm_key(client):
    """No LLM key configured in tests -> generate must degrade to 503, not 500."""
    headers = auth_headers(client, "nokey@example.com")
    trip = client.post(
        "/trips",
        json={"destination_name": "Goa", "start_date": "2026-10-01", "end_date": "2026-10-03"},
        headers=headers,
    ).json()

    res = client.post(f"/trips/{trip['id']}/generate", headers=headers)
    assert res.status_code == 503
    assert "AI planning is unavailable" in res.json()["detail"]


def test_copilot_degrades_gracefully_without_llm_key(client):
    headers = auth_headers(client, "nokey2@example.com")
    trip = client.post(
        "/trips",
        json={"destination_name": "Goa", "start_date": "2026-10-01", "end_date": "2026-10-03"},
        headers=headers,
    ).json()

    res = client.post(f"/trips/{trip['id']}/copilot", json={"message": "hi"}, headers=headers)
    # Copilot never 500s — it stores a friendly assistant error message
    assert res.status_code == 200
    body = res.json()
    assert body["suggestions"] is None
    assert "error" in body["message"]["data"]


def test_health_public_and_unauthenticated_trips_blocked(client):
    assert client.get("/health").status_code == 200
    assert client.get("/trips").status_code == 401
