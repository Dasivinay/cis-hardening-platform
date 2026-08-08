import uuid
from datetime import datetime, timezone
from app.extensions import db


class Scan(db.Model):
    __tablename__ = "scans"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    container_id = db.Column(db.String(36), db.ForeignKey("containers.id", ondelete="CASCADE"), nullable=False)
    container = db.relationship("Container", back_populates="scans")

    triggered_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    triggered_by = db.relationship("User")

    engine = db.Column(db.String(32), nullable=False)              # openscap | ciscat
    benchmark_id = db.Column(db.String(255), nullable=False)        # e.g. xccdf_org.ssgproject.content_benchmark_UBUNTU_22_04
    benchmark_version = db.Column(db.String(64), nullable=True)

    status = db.Column(db.String(32), default="queued")             # queued|running|completed|failed
    error_message = db.Column(db.Text, nullable=True)
    datastream_path = db.Column(db.String(512), nullable=True)  # auto-detected SCAP content path used for this run
    oscap_stdout = db.Column(db.Text, nullable=True)  # captured on every run, pass or fail
    oscap_stderr = db.Column(db.Text, nullable=True)

    overall_score = db.Column(db.Float, nullable=True)              # 0-100
    total_controls = db.Column(db.Integer, default=0)
    passed_controls = db.Column(db.Integer, default=0)
    failed_controls = db.Column(db.Integer, default=0)
    error_controls = db.Column(db.Integer, default=0)
    notchecked_controls = db.Column(db.Integer, default=0)
    notapplicable_controls = db.Column(db.Integer, default=0)
    notselected_controls = db.Column(db.Integer, default=0)

    raw_report_path = db.Column(db.String(512), nullable=True)

    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    results = db.relationship("ScanResultControl", back_populates="scan", cascade="all, delete-orphan")

    def to_summary_dict(self):
        return {
            "id": self.id,
            "container_id": self.container_id,
            "container_name": self.container.name if self.container else None,
            "engine": self.engine,
            "benchmark_id": self.benchmark_id,
            "status": self.status,
            "overall_score": self.overall_score,
            "total_controls": self.total_controls,
            "passed_controls": self.passed_controls,
            "failed_controls": self.failed_controls,
            "error_controls": self.error_controls,
            "notchecked_controls": self.notchecked_controls,
            "triggered_by": self.triggered_by.full_name if self.triggered_by else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "error_message": self.error_message,
            "datastream_path": self.datastream_path,
            "oscap_stdout": self.oscap_stdout,
            "oscap_stderr": self.oscap_stderr,
        }


class ScheduledScan(db.Model):
    """Recurring scan definition, executed by a Celery Beat periodic task."""
    __tablename__ = "scheduled_scans"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    container_id = db.Column(db.String(36), db.ForeignKey("containers.id", ondelete="CASCADE"), nullable=False)
    container = db.relationship("Container")

    engine = db.Column(db.String(32), nullable=False)
    benchmark_id = db.Column(db.String(255), nullable=False)
    cron_expression = db.Column(db.String(64), nullable=False)   # e.g. "0 2 * * *"
    is_active = db.Column(db.Boolean, default=True)

    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_run_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "container_id": self.container_id,
            "engine": self.engine,
            "benchmark_id": self.benchmark_id,
            "cron_expression": self.cron_expression,
            "is_active": self.is_active,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }
