from flask import Response
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.export_service import ExportService
from app.services.audit_service import AuditService

ns = Namespace("reports", description="Scan report export (PDF/HTML)")


@ns.route("/scan/<string:scan_id>/pdf")
class ScanReportPdf(Resource):
    @jwt_required()
    def get(self, scan_id):
        pdf_bytes = ExportService().generate_pdf(scan_id)
        AuditService().log(get_jwt_identity(), "report.export_pdf", "scan", scan_id)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=scan-{scan_id}.pdf"},
        )


@ns.route("/scan/<string:scan_id>/html")
class ScanReportHtml(Resource):
    @jwt_required()
    def get(self, scan_id):
        html = ExportService().generate_html(scan_id)
        AuditService().log(get_jwt_identity(), "report.export_html", "scan", scan_id)
        return Response(html, mimetype="text/html")
