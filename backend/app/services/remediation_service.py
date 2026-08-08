from app.models.remediation import Remediation
from app.models.control import Control
from app.extensions import db
from app.utils.errors import NotFoundError


class RemediationService:
    def get_for_control(self, control_id: str):
        remediation = Remediation.query.filter_by(control_id=control_id).first()
        if not remediation:
            raise NotFoundError("No remediation guidance recorded for this control yet.")
        return remediation

    def upsert(self, control_id: str, summary: str, shell_commands: str, references: str):
        control = Control.query.get(control_id)
        if not control:
            raise NotFoundError("Control not found.")

        remediation = Remediation.query.filter_by(control_id=control_id).first()
        if remediation:
            remediation.summary = summary
            remediation.shell_commands = shell_commands
            remediation.references = references
        else:
            remediation = Remediation(
                control_id=control_id,
                summary=summary,
                shell_commands=shell_commands,
                references=references,
            )
            db.session.add(remediation)

        db.session.commit()
        return remediation
