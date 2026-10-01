def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"


def test_request_id_header_present(client):
    res = client.get("/health")
    assert res.headers.get("X-Request-ID")


def test_cors_origins_flexible_parsing():
    from app.core.config import Settings

    s1 = Settings(cors_origins="https://my-frontend.vercel.app")
    assert s1.cors_origins == ["https://my-frontend.vercel.app"]

    s2 = Settings(cors_origins="https://a.com, https://b.com")
    assert s2.cors_origins == ["https://a.com", "https://b.com"]

    s3 = Settings(cors_origins='["https://a.com", "https://b.com"]')
    assert s3.cors_origins == ["https://a.com", "https://b.com"]

    s4 = Settings(cors_origins="")
    assert s4.cors_origins == ["http://localhost:3000"]


def test_health_services_diagnostic(client):
    """The deployment diagnostic must expose config + reachability, never keys."""
    import re

    res = client.get("/health/services")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert isinstance(body["database"]["ok"], bool)
    assert "configured" in body["llm"]
    assert "reachable" in body["mcp_gateway"]

    # no secrets leak through the diagnostic
    assert "AIza" not in res.text
    assert not re.search(r"AQ\.[A-Za-z0-9_-]{20,}", res.text)
    assert "postgresql" not in res.text
