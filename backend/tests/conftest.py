from unittest.mock import patch

import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import Role


@pytest.fixture(autouse=True)
def _no_real_docker_image_check():
    """
    ScanService.execute_scan calls DockerService.ensure_current_image as its
    very first pre-flight step (see app/services/scan_service.py) to detect
    a target running a stale image before scanning it. That method talks to
    a real Docker daemon, which doesn't exist in the test environment.
    Default it to "already fresh, nothing to do" for every test so existing
    exec_in_target-focused tests aren't forced to also mock Docker image/
    container inspection they aren't testing. The dedicated drift test
    overrides this with its own patch.
    """
    with patch("app.services.docker_service.DockerService.ensure_current_image", return_value=False):
        yield


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        for name in ("admin", "analyst", "viewer"):
            _db.session.add(Role(name=name, description=name))
        _db.session.commit()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_token(app, client):
    client.post("/api/v1/auth/register", json={
        "email": "admin@test.com", "password": "Password123!", "full_name": "Admin",
    })
    # /auth/register always creates a 'viewer' account now (role can no
    # longer be self-assigned — see app/api/auth.py). Promote directly via
    # the DB, the way an existing admin would via PATCH /users/<id> in
    # production, so admin-only endpoints can still be exercised in tests.
    with app.app_context():
        from app.extensions import db as _db
        from app.models.user import User
        user = User.query.filter_by(email="admin@test.com").first()
        admin_role = Role.query.filter_by(name="admin").first()
        user.role_id = admin_role.id
        _db.session.commit()

    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Password123!"})
    return resp.get_json()["access_token"]
