from app.extensions import celery_app
from app.services.scan_service import ScanService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


@celery_app.task(name="tasks.run_scan_task", bind=True, max_retries=1)
def run_scan_task(self, scan_id: str):
    service = ScanService()
    try:
        scan = service.execute_scan(scan_id)
        AuditService().log(scan.triggered_by_id, "scan.completed", "scan", scan.id, details=f"score={scan.overall_score}")
        score_text = f"{scan.overall_score}%" if scan.overall_score is not None else "N/A (no applicable controls scored)"
        NotificationService().notify(
            scan.triggered_by_id,
            title=f"Scan completed: {scan.container.name if scan.container else scan.container_id}",
            message=f"Score {score_text} — {scan.passed_controls} passed, {scan.failed_controls} failed.",
            level="success" if (scan.overall_score is not None and scan.overall_score >= 80) else "warning",
        )
        return {"scan_id": scan.id, "status": scan.status}
    except Exception as exc:
        AuditService().log(None, "scan.failed", "scan", scan_id, details=str(exc))
        try:
            from app.models.scan import Scan
            failed_scan = Scan.query.get(scan_id)
            if failed_scan:
                NotificationService().notify(
                    failed_scan.triggered_by_id,
                    title=f"Scan failed: {failed_scan.container.name if failed_scan.container else scan_id}",
                    message=str(exc),
                    level="error",
                )
        except Exception:
            pass  # notification failure should never mask the original scan error
        raise


@celery_app.task(name="tasks.run_scheduled_scans")
def run_scheduled_scans():
    """
    Invoked by Celery Beat on a fixed interval; checks ScheduledScan rows whose
    cron_expression matches the current time and enqueues run_scan_task for each.
    Kept intentionally simple (interval-based check rather than a full cron
    parser dependency) to keep the infra footprint small for this project.
    """
    from datetime import datetime, timezone
    from app.models.scan import ScheduledScan, Scan
    from croniter import croniter

    now = datetime.now(timezone.utc)
    due = []
    for sched in ScheduledScan.query.filter_by(is_active=True).all():
        base = sched.last_run_at or sched.created_at
        itr = croniter(sched.cron_expression, base)
        next_run = itr.get_next(datetime)
        if next_run.replace(tzinfo=timezone.utc) <= now:
            due.append(sched)

    import logging
    logger = logging.getLogger("secharden.tasks")

    from app.extensions import db
    triggered = 0
    for sched in due:
        scan = Scan(
            container_id=sched.container_id,
            triggered_by_id=sched.created_by_id,
            engine=sched.engine,
            benchmark_id=sched.benchmark_id,
            status="queued",
        )
        db.session.add(scan)
        db.session.flush()  # assigns scan.id without committing yet

        try:
            # Enqueue BEFORE committing last_run_at / the scan row. If the
            # broker is unreachable, delay() raises here — we roll back so
            # neither an orphaned 'queued' Scan (with no task behind it) nor
            # an advanced last_run_at is left behind, and this schedule is
            # picked up again on the next beat tick instead of silently
            # skipping the missed run until its next cron occurrence.
            run_scan_task.delay(scan.id)
        except Exception as exc:
            db.session.rollback()
            logger.error(
                "scheduled_scan.enqueue_failed schedule_id=%s container_id=%s error=%s",
                sched.id, sched.container_id, exc,
            )
            continue

        sched.last_run_at = now
        db.session.commit()
        triggered += 1

    return {"triggered": triggered}
