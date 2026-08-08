from flask import Blueprint
from flask_restx import Api

from app.utils.errors import register_api_error_handlers

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

api = Api(
    api_bp,
    version="1.0",
    title="SecHarden API",
    description="Enterprise CIS Benchmarking & Linux Hardening Platform API",
    doc="/docs",
)

register_api_error_handlers(api)

from app.api.auth import ns as auth_ns
from app.api.users import ns as users_ns
from app.api.containers import ns as containers_ns
from app.api.scans import ns as scans_ns
from app.api.controls import ns as controls_ns
from app.api.remediation import ns as remediation_ns
from app.api.dashboard import ns as dashboard_ns
from app.api.audit import ns as audit_ns
from app.api.reports import ns as reports_ns
from app.api.notifications import ns as notifications_ns
from app.api.scheduling import ns as scheduling_ns

api.add_namespace(auth_ns, path="/auth")
api.add_namespace(users_ns, path="/users")
api.add_namespace(containers_ns, path="/containers")
api.add_namespace(scans_ns, path="/scans")
api.add_namespace(controls_ns, path="/controls")
api.add_namespace(remediation_ns, path="/remediation")
api.add_namespace(dashboard_ns, path="/dashboard")
api.add_namespace(audit_ns, path="/audit")
api.add_namespace(reports_ns, path="/reports")
api.add_namespace(notifications_ns, path="/notifications")
api.add_namespace(scheduling_ns, path="/scheduled-scans")
