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
