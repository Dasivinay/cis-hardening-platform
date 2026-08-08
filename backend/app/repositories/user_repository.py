from app.models.user import User, Role
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    model = User

    def get_by_email(self, email: str):
        return User.query.filter_by(email=email).first()

    def get_role_by_name(self, name: str):
        return Role.query.filter_by(name=name).first()


class RoleRepository(BaseRepository):
    model = Role
