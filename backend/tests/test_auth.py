import uuid

import pytest


def register(client, email=None, password="supersecret1"):
    email = email or f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/auth/register", json={"email": email, "password": password, "display_name": "Test"}
    )
    return res, email, password


def test_register_login_me(client):
    res, email, password = register(client)
    assert res.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token2 = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_register_duplicate_email_409(client):
    _, email, password = register(client)
    dup = client.post("/auth/register", json={"email": email, "password": password})
    assert dup.status_code == 409


def test_login_wrong_password_401(client):
    _, email, password = register(client)
    bad = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert bad.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


@pytest.mark.parametrize("bad_email", ["not-an-email", ""])
def test_register_invalid_email_422(client, bad_email):
    res = client.post("/auth/register", json={"email": bad_email, "password": "supersecret1"})
    assert res.status_code == 422
