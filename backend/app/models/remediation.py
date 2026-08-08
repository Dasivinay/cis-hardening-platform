import uuid
from app.extensions import db


class Remediation(db.Model):
    """
    Advisory remediation guidance mapped 1:1 to a Control.
    Commands are DISPLAYED to the user only. The platform never auto-executes
    remediation against the host; execution against a target container requires
    an explicit, separately-audited confirmation action (see AuditLog).
    """
    __tablename__ = "remediations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    control_id = db.Column(db.String(36), db.ForeignKey("controls.id", ondelete="CASCADE"), unique=True, nullable=False)
    control = db.relationship("Control", back_populates="remediation")

    summary = db.Column(db.Text, nullable=False)
    shell_commands = db.Column(db.Text, nullable=True)     # newline-separated, display-only
    references = db.Column(db.Text, nullable=True)          # newline-separated URLs / CIS section refs

    def to_dict(self):
        return {
            "id": self.id,
            "control_id": self.control_id,
            "summary": self.summary,
            "shell_commands": self.shell_commands.splitlines() if self.shell_commands else [],
            "references": self.references.splitlines() if self.references else [],
        }
