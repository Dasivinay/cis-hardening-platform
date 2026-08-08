from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required

from app.models.audit_log import AuditLog
from app.utils.decorators import roles_required
from app.api._pagination import get_pagination_args, apply_sort, paginated_response

ns = Namespace("audit", description="Audit log (admin only)")


@ns.route("")
class AuditList(Resource):
    @jwt_required()
    @roles_required("admin")
    def get(self):
        page, per_page = get_pagination_args()
        query = AuditLog.query
        action = request.args.get("action")
        if action:
            query = query.filter(AuditLog.action == action)
        query = apply_sort(query, AuditLog)
        return paginated_response(query, page, per_page, lambda a: a.to_dict())
