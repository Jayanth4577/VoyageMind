"""Auth feature tests: profile, change-password, forgot/reset flow, validation."""
import uuid


def register(client, password="supersecret1", email=None):
    email = email or f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Tester"},
    )
    return res, email, password


def headers_for(client, email, password):
    res = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_weak_register_password_rejected(client):
    res, _, _ = register(client, password="lettersonly")
    assert res.status_code == 422
    assert "password" in str(res.json()).lower()


def test_me_includes_trip_count_and_created_at(client):
    res, email, password = register(client)
    headers = headers_for(client, email, password)
    client.post(
        "/trips",
        json={"destination_name": "Goa", "start_date": "2026-10-01", "end_date": "2026-10-02"},
        headers=headers,
    )
    me = client.get("/auth/me", headers=headers).json()
    assert me["trip_count"] == 1
    assert me["created_at"]
    assert me["display_name"] == "Tester"


def test_update_display_name(client):
    _, email, password = register(client)
    headers = headers_for(client, email, password)
    res = client.put("/auth/me", json={"display_name": "New Name"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["display_name"] == "New Name"


def test_change_password_flow(client):
    _, email, password = register(client)
    headers = headers_for(client, email, password)

    # wrong current password
    bad = client.post(
        "/auth/change-password",
        json={"current_password": "wrongpass1", "new_password": "newpass123"},
        headers=headers,
    )
    assert bad.status_code == 401

    ok = client.post(
        "/auth/change-password",
        json={"current_password": password, "new_password": "newpass123"},
        headers=headers,
    )
    assert ok.status_code == 200

    # old password no longer works, new one does
    old_login = client.post("/auth/login", json={"email": email, "password": password})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", json={"email": email, "password": "newpass123"})
    assert new_login.status_code == 200


def test_forgot_and_reset_flow(client):
    _, email, password = register(client)
    forgot = client.post("/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    code = forgot.json().get("dev_code")
    assert code, "dev_code must be present when SMTP is not configured"

    reset = client.post(
        "/auth/reset-password",
        json={"email": email, "code": code, "new_password": "brandnew123"},
    )
    assert reset.status_code == 200

    # new password works
    new_login = client.post(
        "/auth/login", json={"email": email, "password": "brandnew123"}
    )
    assert new_login.status_code == 200
    # old password dead
    old_login = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert old_login.status_code == 401

    # codes are single-use
    reuse = client.post(
        "/auth/reset-password",
        json={"email": email, "code": code, "new_password": "another123"},
    )
    assert reuse.status_code == 400


def test_forgot_unknown_email_no_leak(client):
    res = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert res.status_code == 200
    assert "dev_code" not in res.json()


def test_reset_with_wrong_code(client):
    _, email, password = register(client)
    client.post("/auth/forgot-password", json={"email": email})
    bad = client.post(
        "/auth/reset-password",
        json={"email": email, "code": "000000", "new_password": "whatever123"},
    )
    assert bad.status_code == 400
