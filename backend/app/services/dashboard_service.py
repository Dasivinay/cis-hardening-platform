from sqlalchemy import func
from app.extensions import db
from app.models.scan import Scan
from app.models.control import ScanResultControl, Control
from app.models.container import Container


class DashboardService:
    def summary(self):
        latest_scans_subq = (
            db.session.query(
                Scan.container_id,
                func.max(Scan.completed_at).label("max_completed"),
            )
            .filter(Scan.status == "completed")
            .group_by(Scan.container_id)
            .subquery()
        )

        latest_scans = (
            db.session.query(Scan)
            .join(
                latest_scans_subq,
                (Scan.container_id == latest_scans_subq.c.container_id)
                & (Scan.completed_at == latest_scans_subq.c.max_completed),
            )
            .all()
        )

        total_targets = Container.query.count()
        total_scans = Scan.query.count()

        scored_scans = [s for s in latest_scans if s.overall_score is not None]
        if scored_scans:
            avg_score = round(sum(s.overall_score for s in scored_scans) / len(scored_scans), 2)
        else:
            avg_score = None
        total_passed = sum(s.passed_controls or 0 for s in latest_scans)
        total_failed = sum(s.failed_controls or 0 for s in latest_scans)

        severity_breakdown = (
            db.session.query(Control.severity, func.count(ScanResultControl.id))
            .join(ScanResultControl, ScanResultControl.control_id == Control.id)
            .filter(ScanResultControl.status == "fail")
            .group_by(Control.severity)
            .all()
        )

        return {
            "total_targets": total_targets,
            "total_scans": total_scans,
            "average_score": avg_score,
            "total_passed_controls": total_passed,
            "total_failed_controls": total_failed,
            "failed_by_severity": {sev: count for sev, count in severity_breakdown},
            "latest_scan_per_target": [s.to_summary_dict() for s in latest_scans],
        }

    def trend_for_container(self, container_id: str):
        scans = (
            Scan.query.filter_by(container_id=container_id, status="completed")
            .order_by(Scan.completed_at.asc())
            .all()
        )
        return [
            {
                "scan_id": s.id,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "score": s.overall_score,
                "passed": s.passed_controls,
                "failed": s.failed_controls,
            }
            for s in scans
        ]
