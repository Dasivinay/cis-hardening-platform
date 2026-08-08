from app.models.container import Container
from app.repositories.base_repository import BaseRepository


class ContainerRepository(BaseRepository):
    model = Container

    def get_by_docker_id(self, docker_container_id: str):
        return Container.query.filter_by(docker_container_id=docker_container_id).first()

    def get_by_name(self, name: str):
        return Container.query.filter_by(name=name).first()
