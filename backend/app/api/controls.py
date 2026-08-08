from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required

from app.models.control import Control
from app.utils.errors import NotFoundError
from app.api._pagination import get_pagination_args, apply_sort, paginated_response

ns = Namespace("controls", description="Master CIS control catalog")


@ns.route("")
class ControlList(Resource):
    @jwt_required()
    def get(self):
        page, per_page = get_pagination_args()
        query = Control.query
        category = request.args.get("category")
        severity = request.args.get("severity")
        search = request.args.get("search")
        if category:
            query = query.filter(Control.category == category)
        if severity:
            query = query.filter(Control.severity == severity)
        if search:
            query = query.filter(Control.title.ilike(f"%{search}%"))
        query = apply_sort(query, Control, default_field="rule_id", default_dir="asc")
        return paginated_response(query, page, per_page, lambda c: c.to_dict())


@ns.route("/<string:control_id>")
class ControlDetail(Resource):
    @jwt_required()
    def get(self, control_id):
        control = Control.query.get(control_id)
        if not control:
            raise NotFoundError("Control not found.")
        return control.to_dict()
