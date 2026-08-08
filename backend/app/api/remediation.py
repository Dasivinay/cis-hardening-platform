from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.remediation_service import RemediationService
from app.services.audit_service import AuditService
from app.utils.decorators import roles_required
from app.utils.errors import ValidationError

ns = Namespace("remediation", description="Remediation guidance (advisory / display-only)")


@ns.route("/<string:control_id>")
class RemediationDetail(Resource):
    @jwt_required()
    def get(self, control_id):
        return RemediationService().get_for_control(control_id).to_dict()

    @jwt_required()
    @roles_required("admin", "analyst")
    def put(self, control_id):
        data = request.get_json() or {}
        if not data.get("summary"):
            raise ValidationError("'summary' is required.")

        user_id = get_jwt_identity()
        remediation = RemediationService().upsert(
            control_id=control_id,
            summary=data["summary"],
            shell_commands="\n".join(data.get("shell_commands", [])),
            references="\n".join(data.get("references", [])),
        )
        AuditService().log(user_id, "remediation.update", "control", control_id)
        return remediation.to_dict()
