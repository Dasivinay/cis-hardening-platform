from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.utils.errors import ValidationError

ns = Namespace("auth", description="Authentication")

register_model = ns.model("Register", {
    "email": fields.String(required=True),
    "password": fields.String(required=True),
    "full_name": fields.String(required=True),
})

login_model = ns.model("Login", {
    "email": fields.String(required=True),
    "password": fields.String(required=True),
})


@ns.route("/register")
class Register(Resource):
    @ns.expect(register_model)
    def post(self):
        data = request.get_json() or {}
        for field in ("email", "password", "full_name"):
            if not data.get(field):
                raise ValidationError(f"'{field}' is required.")

        service = AuthService()
        # SECURITY: role is intentionally NOT taken from client input here.
        # This endpoint is unauthenticated by design (self-service sign-up),
        # so accepting a client-supplied role previously let anyone register
        # as 'admin' directly. Every self-registered account starts as
        # 'viewer'; elevating a user's role requires an authenticated admin
        # via PATCH /users/<id> (see app/api/users.py), which already
        # enforces @roles_required("admin").
        user = service.register(
            email=data["email"],
            password=data["password"],
            full_name=data["full_name"],
            role_name="viewer",
        )
        AuditService().log(user.id, "auth.register", "user", user.id)
        return user.to_dict(), 201


@ns.route("/login")
class Login(Resource):
    @ns.expect(login_model)
    def post(self):
        data = request.get_json() or {}
        if not data.get("email") or not data.get("password"):
            raise ValidationError("'email' and 'password' are required.")

        service = AuthService()
        user, access_token, refresh_token = service.authenticate(data["email"], data["password"])
        AuditService().log(user.id, "auth.login", "user", user.id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_dict(),
        }, 200


@ns.route("/me")
class Me(Resource):
    @jwt_required()
    def get(self):
        from app.models.user import User
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return user.to_dict(), 200


@ns.route("/refresh")
class Refresh(Resource):
    @jwt_required(refresh=True)
    def post(self):
        from flask_jwt_extended import create_access_token
        identity = get_jwt_identity()
        claims = get_jwt()
        new_token = create_access_token(
            identity=identity,
            additional_claims={"role": claims.get("role"), "full_name": claims.get("full_name")},
        )
        return {"access_token": new_token}, 200
