"""
OpenSCAP adapter — fully functional, no license required.

Runs `oscap xccdf eval` inside the target container against the
scap-security-guide Ubuntu profile, then parses the resulting ARF/XCCDF XML.
"""
import logging

from lxml import etree

from app.services.parser.base import ScanEngineAdapter, ParsedReport, ParsedControlResult

logger = logging.getLogger("secharden.openscap_parser")


def _local_name(el) -> str:
    """Tag name without namespace URI, e.g. '{...xccdf/1.2}Rule' -> 'Rule'."""
    tag = el.tag
    if isinstance(tag, str) and "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _find_local(el, local_name: str):
    """First direct child matching local_name, regardless of namespace."""
    for child in el:
        if _local_name(child) == local_name:
            return child
    return None


def _text_content(el) -> str:
    """
    Flattened text of an element, including mixed XHTML markup.
    Real SSG <description>/<title> content is frequently mixed content —
    e.g. <description>Some text <xhtml:code>value</xhtml:code> more text
    </description> — so el.text alone (used by the old parser) silently
    truncates to whatever precedes the first child tag, or returns None
    entirely when the element's only content is a child tag.
    """
    if el is None:
        return ""
    return "".join(el.itertext()).strip()

# Real oscap output is not guaranteed to match a single namespace/URI or a
# single wrapper shape:
#   - plain `--results` output: <Benchmark xmlns="…xccdf/1.2"> at the root
#   - `--results-arf` output: the same Benchmark/TestResult buried several
#     levels down inside <arf:asset-report-collection>/<arf:report>/
#     <arf:content>/...
#   - XCCDF 1.1 content (older SSG builds) uses .../xccdf/1.1 instead of 1.2
# Rather than hardcode one xccdf: prefix bound to one URI and one exact
# ancestor path (which silently returns zero matches — no exception — the
# moment any of the above varies), every lookup below matches on local-name()
# so it finds the right elements regardless of namespace URI or how deeply
# they're nested under an ARF wrapper.
SEVERITY_MAP = {"low": "low", "medium": "medium", "high": "high", "unknown": "medium"}

# Best-effort category inference from rule id keywords — used to group
# remediation guidance (SSH, Firewall, Auditd, etc.) without needing a
# separate taxonomy file.
CATEGORY_KEYWORDS = {
    "ssh": "SSH",
    "firewall": "Firewall",
    "ufw": "Firewall",
    "iptables": "Firewall",
    "password": "Password Policy",
    "pam": "Authentication Policy",
    "audit": "Auditd",
    "cron": "Cron",
    "sysctl": "Kernel Parameters",
    "grub": "Bootloader",
    "bootloader": "Bootloader",
    "service": "System Services",
    "usb": "USB Devices",
    "ipv6": "IPv6",
    "network": "Network Security",
    "permission": "File Permissions",
    "filepermissions": "File Permissions",
    "logging": "Logging",
    "rsyslog": "Logging",
    "journald": "Logging",
}


def _infer_category(rule_id: str) -> str:
    lowered = rule_id.lower()
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in lowered:
            return category
    return "General Hardening"


class OpenSCAPAdapter(ScanEngineAdapter):
    engine_name = "openscap"

    # Fallback only — used if ScanService's auto-detection (which inspects
    # the actual target container at scan time; see
    # ScanService._resolve_datastream_path) can't be run for some reason.
    # The real, normal path is always resolved dynamically so the platform
    # keeps working if the target image's OS/content version changes without
    # this constant being updated in lockstep.
    DATASTREAM_PATH = "/usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml"
    RESULT_PATH = "/tmp/openscap-results.xml"

    def build_scan_command(self, benchmark_id: str, datastream_path: str | None = None) -> list[str]:
        return [
            "oscap", "xccdf", "eval",
            "--profile", benchmark_id,
            "--results", self.RESULT_PATH,
            datastream_path or self.DATASTREAM_PATH,
        ]

    def result_file_path(self, benchmark_id: str) -> str:
        return self.RESULT_PATH

    def parse(self, raw_report_bytes: bytes, benchmark_id: str) -> ParsedReport:
        # recover=True: real oscap output has occasionally shipped with minor
        # well-formedness quirks (stray control chars from embedded command
        # output in <message> elements); fail loudly only if the document is
        # too broken to recover anything from at all.
        parser = etree.XMLParser(recover=True, huge_tree=True)
        root = etree.fromstring(raw_report_bytes, parser=parser)
        if root is None:
            raise ValueError("OpenSCAP results XML could not be parsed (empty or unrecoverable document)")

        benchmark_version_el = _find_local(root, "version")
        benchmark_version = _text_content(benchmark_version_el) or "unknown"

        # Build rule metadata lookup: id -> (title, description, severity).
        # local-name() matches regardless of ARF wrapping or which XCCDF
        # namespace URI (1.1 vs 1.2) the content declares.
        rule_meta = {}
        for rule_el in root.iter():
            if _local_name(rule_el) != "Rule":
                continue
            rid = rule_el.get("id")
            if not rid:
                continue
            title_el = _find_local(rule_el, "title")
            desc_el = _find_local(rule_el, "description")
            severity = rule_el.get("severity", "medium")
            rule_meta[rid] = {
                "title": _text_content(title_el) or rid,
                "description": _text_content(desc_el),
                "severity": SEVERITY_MAP.get(severity, "medium"),
            }

        status_map = {
            "pass": "pass",
            "fixed": "pass",
            "fail": "fail",
            "error": "error",
            "unknown": "error",       # observed in real oscap output; check ran but couldn't determine a result
            "notchecked": "notchecked",
            "informational": "notchecked",
            # Kept distinct from "notapplicable": notapplicable means oscap
            # evaluated platform-applicability and genuinely excluded the
            # rule (e.g. a bootloader check inside a container). notselected
            # means the rule was never evaluated at all because the chosen
            # profile didn't include it. A report that is ALL notselected is
            # a profile/content-scoping bug, not "nothing applies" — see
            # ParsedReport.is_vacuous below.
            "notselected": "notselected",
            "notapplicable": "notapplicable",
        }

        controls: list[ParsedControlResult] = []
        seen_idrefs: set[str] = set()
        for result_el in root.iter():
            if _local_name(result_el) != "rule-result":
                continue
            rule_id = result_el.get("idref")
            if not rule_id:
                continue
            status_el = _find_local(result_el, "result")
            status_raw = (_text_content(status_el) or "notchecked").strip().lower()
            status = status_map.get(status_raw, "notchecked")

            meta = rule_meta.get(rule_id, {"title": rule_id, "description": "", "severity": "medium"})

            controls.append(ParsedControlResult(
                rule_id=rule_id,
                title=meta["title"],
                description=meta["description"],
                severity=meta["severity"],
                category=_infer_category(rule_id or ""),
                status=status,
            ))
            seen_idrefs.add(rule_id)

        if not controls:
            logger.warning(
                "openscap.parse_empty_result benchmark_id=%s rules_found=%d "
                "(no <rule-result> elements matched anywhere in the document — "
                "check that oscap actually ran the profile, not just listed it)",
                benchmark_id, len(rule_meta),
            )

        return ParsedReport(
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
            controls=controls,
        )
