from flask_jwt_extended import create_access_token, create_refresh_token
from datetime import datetime, timezone

from app.repositories.user_repository import UserRepository
from app.utils.errors import ConflictError, UnauthorizedError, NotFoundError


class AuthService:
    def __init__(self):
        self.users = UserRepository()

    def register(self, email: str, password: str, full_name: str, role_name: str = "viewer"):
        if self.users.get_by_email(email):
            raise ConflictError(f"A user with email '{email}' already exists.")

        role = self.users.get_role_by_name(role_name)
        if not role:
            raise NotFoundError(f"Role '{role_name}' does not exist.")

        from app.models.user import User
        user = User(email=email, full_name=full_name, role_id=role.id)
        user.set_password(password)
        self.users.add(user)
        return user

    def authenticate(self, email: str, password: str):
        user = self.users.get_by_email(email)
        if not user or not user.check_password(password):
            raise UnauthorizedError("Invalid email or password.")
        if not user.is_active:
            raise UnauthorizedError("This account has been deactivated.")

        user.last_login_at = datetime.now(timezone.utc)
        self.users.add(user)

        claims = {"role": user.role.name, "full_name": user.full_name}
        access_token = create_access_token(identity=user.id, additional_claims=claims)
        refresh_token = create_refresh_token(identity=user.id, additional_claims=claims)
        return user, access_token, refresh_token
