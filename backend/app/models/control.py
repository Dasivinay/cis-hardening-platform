import uuid
from app.extensions import db


class Control(db.Model):
    """
    Master catalog of CIS controls, keyed by rule id, shared across scans/benchmarks.
    Populated/upserted by the parser as new controls are encountered.
    """
    __tablename__ = "controls"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = db.Column(db.String(255), unique=True, nullable=False, index=True)  # XCCDF rule id
    title = db.Column(db.String(512), nullable=False)
    description = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(16), nullable=False, default="medium")  # low|medium|high|critical
    category = db.Column(db.String(128), nullable=True)  # e.g. SSH, Firewall, Auditd

    remediation = db.relationship("Remediation", back_populates="control", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
        }


class ScanResultControl(db.Model):
    """Per-scan result for a single control — the many-to-many join with per-scan status."""
    __tablename__ = "scan_result_controls"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    scan_id = db.Column(db.String(36), db.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    scan = db.relationship("Scan", back_populates="results")

    control_id = db.Column(db.String(36), db.ForeignKey("controls.id"), nullable=False, index=True)
    control = db.relationship("Control")

    status = db.Column(db.String(16), nullable=False)  # pass|fail|error|notchecked|notapplicable
    result_detail = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "control": self.control.to_dict() if self.control else None,
            "status": self.status,
            "result_detail": self.result_detail,
        }
