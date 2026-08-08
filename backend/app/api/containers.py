from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.container import Container
from app.services.docker_service import DockerService
from app.services.audit_service import AuditService
from app.utils.decorators import roles_required
from app.utils.errors import ValidationError
from app.api._pagination import get_pagination_args, apply_sort, paginated_response

ns = Namespace("containers", description="Docker-managed Ubuntu scan targets")


@ns.route("")
class ContainerList(Resource):
    @jwt_required()
    def get(self):
        page, per_page = get_pagination_args()
        query = Container.query
        status = request.args.get("status")
        if status:
            query = query.filter(Container.status == status)
        search = request.args.get("search")
        if search:
            query = query.filter(Container.name.ilike(f"%{search}%"))
        query = apply_sort(query, Container)
        return paginated_response(query, page, per_page, lambda c: c.to_dict())

    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self):
        data = request.get_json() or {}
        if not data.get("name"):
            raise ValidationError("'name' is required.")

        user_id = get_jwt_identity()
        service = DockerService()
        container = service.create_target(name=data["name"], created_by_id=user_id, image=data.get("image"))
        AuditService().log(user_id, "container.create", "container", container.id, details=data.get("name"))
        return container.to_dict(), 201


@ns.route("/<string:container_id>")
class ContainerDetail(Resource):
    @jwt_required()
    def get(self, container_id):
        from app.utils.errors import NotFoundError
        container = Container.query.get(container_id)
        if not container:
            raise NotFoundError("Target not found.")
        return container.to_dict()

    @jwt_required()
    @roles_required("admin", "analyst")
    def delete(self, container_id):
        user_id = get_jwt_identity()
        DockerService().delete(container_id)
        AuditService().log(user_id, "container.delete", "container", container_id)
        return {"message": "Target deleted."}, 200


@ns.route("/<string:container_id>/start")
class ContainerStart(Resource):
    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self, container_id):
        user_id = get_jwt_identity()
        container = DockerService().start(container_id)
        AuditService().log(user_id, "container.start", "container", container_id)
        return container.to_dict()


@ns.route("/<string:container_id>/stop")
class ContainerStop(Resource):
    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self, container_id):
        user_id = get_jwt_identity()
        container = DockerService().stop(container_id)
        AuditService().log(user_id, "container.stop", "container", container_id)
        return container.to_dict()


@ns.route("/<string:container_id>/restart")
class ContainerRestart(Resource):
    @jwt_required()
    @roles_required("admin", "analyst")
    def post(self, container_id):
        user_id = get_jwt_identity()
        container = DockerService().restart(container_id)
        AuditService().log(user_id, "container.restart", "container", container_id)
        return container.to_dict()


@ns.route("/<string:container_id>/logs")
class ContainerLogs(Resource):
    @jwt_required()
    def get(self, container_id):
        tail = request.args.get("tail", 200, type=int)
        logs = DockerService().logs(container_id, tail=tail)
        return {"logs": logs}
