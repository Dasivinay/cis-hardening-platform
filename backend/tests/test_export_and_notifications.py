from datetime import datetime, timezone


def _make_completed_scan(app, client, admin_token):
    """Helper: build a container + a completed scan with a couple of results directly
    against the DB (bypassing Docker/Celery, which aren't available in unit tests)."""
    from app.extensions import db
    from app.models.container import Container
    from app.models.scan import Scan
    from app.models.control import Control, ScanResultControl
    from app.models.user import User

    with app.app_context():
        admin = User.query.filter_by(email="admin@test.com").first()
        container = Container(name="export-target", image="ubuntu:22.04", status="running", created_by_id=admin.id)
        db.session.add(container)
        db.session.flush()

        scan = Scan(
            container_id=container.id, triggered_by_id=admin.id, engine="openscap",
            benchmark_id="cis_level1_server", status="completed",
            overall_score=75.0, total_controls=4, passed_controls=3, failed_controls=1,
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(scan)
        db.session.flush()

        control = Control(rule_id="rule_ssh_disable_root", title="Disable SSH root login", severity="high", category="SSH")
        db.session.add(control)
        db.session.flush()

        db.session.add(ScanResultControl(scan_id=scan.id, control_id=control.id, status="fail"))
        db.session.commit()
        return scan.id


def test_pdf_export(app, client, admin_token):
    scan_id = _make_completed_scan(app, client, admin_token)
    resp = client.get(f"/api/v1/reports/scan/{scan_id}/pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert resp.data[:4] == b"%PDF"  # real PDF magic bytes, not a stub


def test_html_export(app, client, admin_token):
    scan_id = _make_completed_scan(app, client, admin_token)
    resp = client.get(f"/api/v1/reports/scan/{scan_id}/html", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert b"Disable SSH root login" in resp.data
    assert b"75.0%" in resp.data


def test_export_rejects_incomplete_scan(client, admin_token):
    from app.extensions import db
    resp = client.post(
        "/api/v1/containers", json={"name": "incomplete-target"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # container creation may 502 without real docker; that's fine, we just need a scan row
    from app.models.user import User
    from app.models.container import Container
    from app.models.scan import Scan
    admin = User.query.filter_by(email="admin@test.com").first()
    container = Container(name="incomplete-c", image="ubuntu:22.04", status="running", created_by_id=admin.id)
    db.session.add(container)
    db.session.flush()
    scan = Scan(container_id=container.id, triggered_by_id=admin.id, engine="openscap", benchmark_id="x", status="running")
    db.session.add(scan)
    db.session.commit()

    resp = client.get(f"/api/v1/reports/scan/{scan.id}/pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 400


def test_notifications_flow(client, admin_token):
    from app.services.notification_service import NotificationService
    from app.models.user import User

    admin = User.query.filter_by(email="admin@test.com").first()
    notif = NotificationService().notify(admin.id, "Test notification", "hello", "info")

    resp = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert any(n["id"] == notif.id for n in items)

    resp = client.post(f"/api/v1/notifications/{notif.id}/read", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.get_json()["is_read"] is True


def test_scheduling_flow(client, admin_token):
    from app.models.user import User
    from app.models.container import Container
    from app.extensions import db

    admin = User.query.filter_by(email="admin@test.com").first()
    container = Container(name="sched-target", image="ubuntu:22.04", status="running", created_by_id=admin.id)
    db.session.add(container)
    db.session.commit()

    resp = client.post(
        "/api/v1/scheduled-scans",
        json={"container_id": container.id, "engine": "openscap", "benchmark_id": "cis_level1_server", "cron_expression": "0 2 * * *"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    sched_id = resp.get_json()["id"]

    resp = client.post(
        "/api/v1/scheduled-scans",
        json={"container_id": container.id, "engine": "openscap", "benchmark_id": "x", "cron_expression": "not-a-cron"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400

    resp = client.delete(f"/api/v1/scheduled-scans/{sched_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
