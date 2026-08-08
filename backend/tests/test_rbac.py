def test_viewer_cannot_create_container(client):
    client.post("/api/v1/auth/register", json={
        "email": "viewer@test.com", "password": "Password123!", "full_name": "Viewer",
    })
    login = client.post("/api/v1/auth/login", json={"email": "viewer@test.com", "password": "Password123!"})
    token = login.get_json()["access_token"]

    resp = client.post(
        "/api/v1/containers",
        json={"name": "target-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_admin_can_list_users(client, admin_token):
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "items" in resp.get_json()
