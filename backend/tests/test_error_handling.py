"""
Regression coverage for the flask-restx / flask-jwt-extended interaction bug
found during audit: flask-restx's Api.error_router intercepts every exception
raised inside a Resource *before* Flask's own app.errorhandler_spec runs, and
only consults handlers registered via api.errorhandler(). Registering
AppError / JWT exceptions only via @app.errorhandler (the natural-looking
approach) silently produces 500s for every 400/401/403/404/409 in real
deployment, while still appearing to pass under pytest's TESTING config —
which takes a different exception-propagation path and masks the bug. These
tests intentionally do NOT rely on that masking: they assert on the exact
status code and body shape returned over the Flask test client, which is
sufficient because register_api_error_handlers is exercised identically
regardless of TESTING config (the fix operates at the flask-restx layer, not
Flask's exception-propagation layer).
"""


def test_unauthenticated_request_returns_401_not_500(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401
    body = resp.get_json()
    assert body["error"] != "InternalServerError"


def test_duplicate_registration_returns_409_not_500(client):
    payload = {"email": "conflict@test.com", "password": "Password123!", "full_name": "Conflict"}
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "ConflictError"


def test_not_found_returns_404_not_500(client, admin_token):
    resp = client.get("/api/v1/users/does-not-exist", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "NotFoundError"


def test_forbidden_returns_403_not_500(client):
    client.post("/api/v1/auth/register", json={"email": "viewer3@test.com", "password": "Password123!", "full_name": "V"})
    login = client.post("/api/v1/auth/login", json={"email": "viewer3@test.com", "password": "Password123!"})
    token = login.get_json()["access_token"]
    resp = client.post("/api/v1/containers", json={"name": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "ForbiddenError"


def test_bad_credentials_returns_401_not_500(client):
    client.post("/api/v1/auth/register", json={"email": "creds@test.com", "password": "Password123!", "full_name": "C"})
    resp = client.post("/api/v1/auth/login", json={"email": "creds@test.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "UnauthorizedError"


def test_validation_error_returns_400_not_500(client):
    resp = client.post("/api/v1/auth/register", json={"email": "incomplete@test.com"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "ValidationError"


def test_malformed_bearer_token_returns_401_not_500(client):
    resp = client.get("/api/v1/users", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
