from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.scheduling_service import SchedulingService
from app.services.audit_service import AuditService
from app.utils.decorators import roles_required
from app.utils.errors import ValidationError
from app.api._pagination import get_pagination_args, paginated_response

ns = Namespace("scheduled-scans", description="Recurring scan schedules")


@ns.route("")
class ScheduleList(Resource):
    @jwt_required()
    def get(self):
        page, per_page = get_pagination_args()
        query = SchedulingService().list_all()
        return paginated_response(query, page, per_page, lambda s: s.to_dict())

    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self):
        data = request.get_json() or {}
        for field in ("container_id", "engine", "benchmark_id", "cron_expression"):
            if not data.get(field):
                raise ValidationError(f"'{field}' is required.")

        user_id = get_jwt_identity()
        sched = SchedulingService().create(
            container_id=data["container_id"],
            engine=data["engine"],
            benchmark_id=data["benchmark_id"],
            cron_expression=data["cron_expression"],
            created_by_id=user_id,
        )
        AuditService().log(user_id, "schedule.create", "scheduled_scan", sched.id)
        return sched.to_dict(), 201


@ns.route("/<string:schedule_id>/toggle")
class ScheduleToggle(Resource):
    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self, schedule_id):
        data = request.get_json() or {}
        user_id = get_jwt_identity()
        sched = SchedulingService().set_active(schedule_id, bool(data.get("is_active", True)))
        AuditService().log(user_id, "schedule.toggle", "scheduled_scan", schedule_id)
        return sched.to_dict()


@ns.route("/<string:schedule_id>")
class ScheduleDetail(Resource):
    @jwt_required()
    @roles_required("admin", "analyst")
    def delete(self, schedule_id):
        user_id = get_jwt_identity()
        SchedulingService().delete(schedule_id)
        AuditService().log(user_id, "schedule.delete", "scheduled_scan", schedule_id)
        return {"message": "Schedule deleted."}
