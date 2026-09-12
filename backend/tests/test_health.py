def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"


def test_request_id_header_present(client):
    res = client.get("/health")
    assert res.headers.get("X-Request-ID")
