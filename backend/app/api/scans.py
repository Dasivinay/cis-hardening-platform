from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.scan import Scan
from app.models.control import ScanResultControl
from app.services.scan_service import ScanService
from app.services.audit_service import AuditService
from app.utils.decorators import roles_required
from app.utils.errors import ValidationError, NotFoundError
from app.api._pagination import get_pagination_args, apply_sort, paginated_response

ns = Namespace("scans", description="CIS Benchmark scan execution & history")


@ns.route("")
class ScanList(Resource):
    @jwt_required()
    def get(self):
        page, per_page = get_pagination_args()
        query = Scan.query
        container_id = request.args.get("container_id")
        if container_id:
            query = query.filter(Scan.container_id == container_id)
        status = request.args.get("status")
        if status:
            query = query.filter(Scan.status == status)
        query = apply_sort(query, Scan)
        return paginated_response(query, page, per_page, lambda s: s.to_summary_dict())

    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self):
        data = request.get_json() or {}
        for field in ("container_id", "engine", "benchmark_id"):
            if not data.get(field):
                raise ValidationError(f"'{field}' is required.")

        user_id = get_jwt_identity()
        service = ScanService()
        scan = service.create_scan_record(
            container_id=data["container_id"],
            engine=data["engine"],
            benchmark_id=data["benchmark_id"],
            triggered_by_id=user_id,
        )

        # Dispatch async execution via Celery so the API responds immediately.
        from app.tasks import run_scan_task
        run_scan_task.delay(scan.id)

        AuditService().log(user_id, "scan.trigger", "scan", scan.id, details=data["benchmark_id"])
        return scan.to_summary_dict(), 202


@ns.route("/<string:scan_id>")
class ScanDetail(Resource):
    @jwt_required()
    def get(self, scan_id):
        scan = Scan.query.get(scan_id)
        if not scan:
            raise NotFoundError("Scan not found.")
        return scan.to_summary_dict()


@ns.route("/<string:scan_id>/controls")
class ScanControls(Resource):
    @jwt_required()
    def get(self, scan_id):
        page, per_page = get_pagination_args()
        status = request.args.get("status")  # pass|fail|error|notchecked
        search = request.args.get("search")

        query = ScanResultControl.query.filter_by(scan_id=scan_id)
        if status:
            query = query.filter(ScanResultControl.status == status)
        if search:
            from app.models.control import Control
            query = query.join(Control).filter(Control.title.ilike(f"%{search}%"))

        return paginated_response(query, page, per_page, lambda r: r.to_dict())
