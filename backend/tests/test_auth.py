def test_register_and_login(client):
    resp = client.post("/api/v1/auth/register", json={
        "email": "user@test.com", "password": "Password123!", "full_name": "Test User",
    })
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "user@test.com"

    resp = client.post("/api/v1/auth/login", json={"email": "user@test.com", "password": "Password123!"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "access_token" in body
    assert body["user"]["role"] == "viewer"


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={
        "email": "user2@test.com", "password": "Password123!", "full_name": "Test User 2",
    })
    resp = client.post("/api/v1/auth/login", json={"email": "user2@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_duplicate_registration_conflict(client):
    payload = {"email": "dup@test.com", "password": "Password123!", "full_name": "Dup"}
    r1 = client.post("/api/v1/auth/register", json=payload)
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 409


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
