from flask import request
from app.repositories.audit_repository import AuditLogRepository


class AuditService:
    def __init__(self):
        self.repo = AuditLogRepository()

    def log(self, user_id, action: str, resource_type: str = None, resource_id: str = None, details: str = None):
        from app.models.audit_log import AuditLog
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.remote_addr if request else None,
        )
        return self.repo.add(entry)
