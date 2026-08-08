import uuid
from datetime import datetime, timezone
from app.extensions import db


class Container(db.Model):
    """
    Represents a Docker-managed Ubuntu scan target owned by this platform.
    The platform only ever executes commands against containers tracked here —
    never against the Docker host itself.
    """
    __tablename__ = "containers"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), unique=True, nullable=False)
    docker_container_id = db.Column(db.String(64), unique=True, nullable=True)
    image = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), default="created")  # created|running|stopped|removed|error
    ubuntu_version = db.Column(db.String(32), default="22.04")

    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_by = db.relationship("User")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    scans = db.relationship("Scan", back_populates="container", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "docker_container_id": self.docker_container_id,
            "image": self.image,
            "status": self.status,
            "ubuntu_version": self.ubuntu_version,
            "created_by": self.created_by.full_name if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
