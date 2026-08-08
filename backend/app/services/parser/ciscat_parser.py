"""
CIS-CAT PRO Assessor adapter.

CIS-CAT PRO is commercial software licensed by the Center for Internet
Security and is NOT bundled with this platform. This adapter assumes an
already-licensed CIS-CAT PRO Assessor installation has been mounted into the
target container image (e.g. via a volume the operator provides), and it
drives that existing installation via its documented CLI.

If no CIS-CAT installation is present, `build_scan_command` will still return
the standard invocation; execution will fail inside the container with a
clear "assessor-cli.sh not found" error surfaced back through ScanService,
rather than the platform attempting to fetch or reconstruct the tool.
"""
from bs4 import BeautifulSoup

from app.services.parser.base import ScanEngineAdapter, ParsedReport, ParsedControlResult
from app.services.parser.openscap_parser import _infer_category

CIS_CAT_INSTALL_DIR = "/opt/ciscat"  # operator-mounted, licensed installation
CIS_CAT_RESULT_DIR = "/tmp/ciscat-results"

STATUS_MAP = {
    "pass": "pass",
    "fail": "fail",
    "error": "error",
    "not checked": "notchecked",
    "not applicable": "notapplicable",
    "unknown": "notchecked",
}

SEVERITY_MAP = {"1": "low", "2": "low", "3": "medium", "4": "high", "5": "high", "6": "critical", "7": "critical"}


class CISCATAdapter(ScanEngineAdapter):
    engine_name = "ciscat"

    def build_scan_command(self, benchmark_id: str, datastream_path: str | None = None) -> list[str]:
        # datastream_path is unused here — CIS-CAT drives its own already-
        # installed, licensed CLI at a fixed location, not an auto-detected
        # SCAP datastream. Accepted for interface compatibility with
        # ScanService, which now resolves and passes it for every engine.
        # benchmark_id here is the CIS-CAT benchmark .xml filename/profile the
        # operator has placed alongside their licensed CIS-CAT installation.
        return [
            "sh", f"{CIS_CAT_INSTALL_DIR}/Assessor-CLI.sh",
            "-b", f"{CIS_CAT_INSTALL_DIR}/benchmarks/{benchmark_id}",
            "-r", CIS_CAT_RESULT_DIR,
            "-rd", CIS_CAT_RESULT_DIR,
            "-x",  # export XML report alongside HTML
        ]

    def result_file_path(self, benchmark_id: str) -> str:
        # CIS-CAT names output files by run timestamp; ScanService resolves the
        # actual generated filename by listing CIS_CAT_RESULT_DIR after the run.
        return CIS_CAT_RESULT_DIR

    def parse(self, raw_report_bytes: bytes, benchmark_id: str) -> ParsedReport:
        """
        Parses CIS-CAT PRO's XML rule-results export. If your CIS-CAT version's
        schema differs, adjust the selectors below — this method is the single
        integration point the rest of the platform depends on.
        """
        soup = BeautifulSoup(raw_report_bytes, "xml")

        benchmark_el = soup.find("benchmark")
        benchmark_version = benchmark_el.get("version") if benchmark_el else "unknown"

        controls: list[ParsedControlResult] = []
        for rule_result in soup.find_all("rule-result"):
            rule_id = rule_result.get("idref", "unknown-rule")
            result_text = (rule_result.find("result").text if rule_result.find("result") else "unknown").strip().lower()
            status = STATUS_MAP.get(result_text, "notchecked")

            rule_el = rule_result.find("rule") or rule_result
            title = rule_el.get("title", rule_id) if rule_el else rule_id
            severity_raw = rule_el.get("severity", "3") if rule_el else "3"
            severity = SEVERITY_MAP.get(str(severity_raw), "medium")

            desc_el = rule_result.find("description")
            description = desc_el.text.strip() if desc_el else ""

            controls.append(ParsedControlResult(
                rule_id=rule_id,
                title=title,
                description=description,
                severity=severity,
                category=_infer_category(rule_id),
                status=status,
            ))

        return ParsedReport(
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
            controls=controls,
        )
