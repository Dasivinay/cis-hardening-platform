from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.decorators import roles_required
from app.services.audit_service import AuditService
from app.api._pagination import get_pagination_args, apply_sort, paginated_response
from app.utils.errors import NotFoundError, ValidationError

ns = Namespace("users", description="User management (admin only)")


@ns.route("")
class UserList(Resource):
    @jwt_required()
    @roles_required("admin")
    def get(self):
        page, per_page = get_pagination_args()
        query = User.query
        search = request.args.get("search")
        if search:
            query = query.filter(User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%"))
        query = apply_sort(query, User)
        return paginated_response(query, page, per_page, lambda u: u.to_dict())


@ns.route("/<string:user_id>")
class UserDetail(Resource):
    @jwt_required()
    @roles_required("admin")
    def get(self, user_id):
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User not found.")
        return user.to_dict()

    @jwt_required()
    @roles_required("admin")
    def patch(self, user_id):
        from flask_jwt_extended import get_jwt_identity
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User not found.")

        data = request.get_json() or {}
        repo = UserRepository()

        if "role" in data:
            role = repo.get_role_by_name(data["role"])
            if not role:
                raise ValidationError(f"Unknown role '{data['role']}'.")
            user.role_id = role.id
        if "is_active" in data:
            user.is_active = bool(data["is_active"])
        if "full_name" in data:
            user.full_name = data["full_name"]

        repo.add(user)
        AuditService().log(get_jwt_identity(), "user.update", "user", user.id, details=str(data))
        return user.to_dict()

    @jwt_required()
    @roles_required("admin")
    def delete(self, user_id):
        from flask_jwt_extended import get_jwt_identity
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User not found.")
        repo = UserRepository()
        repo.delete(user)
        AuditService().log(get_jwt_identity(), "user.delete", "user", user_id)
        return {"message": "User deleted."}, 200
