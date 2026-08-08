"""
Report export service — generates PDF and HTML renditions of a completed scan.

PDF uses reportlab's Platypus layer (flowable document model) rather than raw
canvas drawing, since the report has variable-length tables that need to
paginate automatically.
"""
from io import BytesIO
from datetime import datetime, timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from jinja2 import Environment, BaseLoader

from app.models.scan import Scan
from app.models.control import ScanResultControl
from app.utils.errors import ValidationError

SEVERITY_COLORS = {
    "critical": colors.HexColor("#FF3B6B"),
    "high": colors.HexColor("#F1554C"),
    "medium": colors.HexColor("#F5B942"),
    "low": colors.HexColor("#4FA9E8"),
}
STATUS_COLORS = {
    "pass": colors.HexColor("#3DDC97"),
    "fail": colors.HexColor("#F1554C"),
    "error": colors.HexColor("#FF3B6B"),
    "notchecked": colors.HexColor("#6B7690"),
    "notapplicable": colors.HexColor("#6B7690"),
}


class ExportService:
    def _require_completed_scan(self, scan_id: str) -> Scan:
        scan = Scan.query.get(scan_id)
        if not scan:
            raise ValidationError("Scan not found.")
        if scan.status != "completed":
            raise ValidationError(f"Scan is '{scan.status}' — export is only available for completed scans.")
        return scan

    def generate_pdf(self, scan_id: str) -> bytes:
        scan = self._require_completed_scan(scan_id)
        results = ScanResultControl.query.filter_by(scan_id=scan_id).all()

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], textColor=colors.HexColor("#161C2C"))
        meta_style = ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.HexColor("#555"), fontSize=9)

        story = []
        story.append(Paragraph("CIS Benchmark Scan Report", title_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Target: {scan.container.name if scan.container else scan.container_id}", styles["Heading2"]))
        story.append(Paragraph(f"Benchmark: {scan.benchmark_id} (v{scan.benchmark_version or 'n/a'})", meta_style))
        story.append(Paragraph(f"Engine: {scan.engine}", meta_style))
        story.append(Paragraph(f"Completed: {scan.completed_at.isoformat() if scan.completed_at else 'n/a'}", meta_style))
        story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", meta_style))
        story.append(Spacer(1, 14))

        summary_data = [
            ["Overall Score", "Total", "Passed", "Failed", "Errors", "Not Checked"],
            [
                f"{scan.overall_score}%" if scan.overall_score is not None else "N/A",
                str(scan.total_controls),
                str(scan.passed_controls),
                str(scan.failed_controls),
                str(scan.error_controls),
                str(scan.notchecked_controls),
            ],
        ]
        summary_table = Table(summary_data, hAlign="LEFT")
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#161C2C")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 18))

        story.append(Paragraph("Control Results", styles["Heading2"]))
        story.append(Spacer(1, 8))

        control_rows = [["Rule ID", "Title", "Severity", "Status"]]
        for r in sorted(results, key=lambda x: (x.status != "fail", x.control.rule_id if x.control else "")):
            control_rows.append([
                Paragraph(r.control.rule_id if r.control else "unknown", styles["Normal"]),
                Paragraph(r.control.title if r.control else "", styles["Normal"]),
                r.control.severity if r.control else "",
                r.status,
            ])

        control_table = Table(control_rows, colWidths=[1.7 * inch, 2.9 * inch, 0.9 * inch, 0.9 * inch], repeatRows=1)
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#161C2C")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i, r in enumerate(results, start=1):
            if r.status == "fail":
                table_style.append(("TEXTCOLOR", (3, i), (3, i), STATUS_COLORS["fail"]))
            elif r.status == "pass":
                table_style.append(("TEXTCOLOR", (3, i), (3, i), STATUS_COLORS["pass"]))
        control_table.setStyle(TableStyle(table_style))
        story.append(control_table)

        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    HTML_TEMPLATE = """
    <!doctype html>
    <html><head><meta charset="utf-8"><title>Scan Report — {{ scan.container.name }}</title>
    <style>
      body { font-family: -apple-system, sans-serif; background: #0A0E14; color: #E8ECF4; padding: 32px; }
      h1 { font-size: 22px; } h2 { font-size: 16px; color: #AAB4C8; font-weight: 500; }
      table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
      th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #212A3E; }
      th { color: #6B7690; font-weight: 500; }
      .pass { color: #3DDC97; } .fail { color: #F1554C; } .error { color: #FF3B6B; } .notchecked { color: #6B7690; }
      .summary { display: flex; gap: 16px; margin: 16px 0; }
      .stat { background: #161C2C; border: 1px solid #212A3E; border-radius: 8px; padding: 12px 16px; }
      .stat b { display: block; font-size: 20px; font-family: monospace; }
    </style></head>
    <body>
      <h1>CIS Benchmark Scan Report</h1>
      <h2>{{ scan.container.name }} — {{ scan.benchmark_id }}</h2>
      <p style="color:#6B7690; font-size:12px;">Completed {{ scan.completed_at }} · Engine: {{ scan.engine }}</p>
      <div class="summary">
        <div class="stat">Score<b>{{ (scan.overall_score ~ '%') if scan.overall_score is not none else 'N/A' }}</b></div>
        <div class="stat">Passed<b class="pass">{{ scan.passed_controls }}</b></div>
        <div class="stat">Failed<b class="fail">{{ scan.failed_controls }}</b></div>
        <div class="stat">Errors<b class="error">{{ scan.error_controls }}</b></div>
      </div>
      <table>
        <thead><tr><th>Rule ID</th><th>Title</th><th>Severity</th><th>Status</th></tr></thead>
        <tbody>
        {% for r in results %}
          <tr>
            <td><code>{{ r.control.rule_id if r.control else 'unknown' }}</code></td>
            <td>{{ r.control.title if r.control else '' }}</td>
            <td>{{ r.control.severity if r.control else '' }}</td>
            <td class="{{ r.status }}">{{ r.status }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </body></html>
    """

    def generate_html(self, scan_id: str) -> str:
        scan = self._require_completed_scan(scan_id)
        results = ScanResultControl.query.filter_by(scan_id=scan_id).all()
        template = Environment(loader=BaseLoader()).from_string(self.HTML_TEMPLATE)
        return template.render(scan=scan, results=results)
