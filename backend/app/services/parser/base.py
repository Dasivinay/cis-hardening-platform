from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParsedControlResult:
    rule_id: str
    title: str
    description: str
    severity: str        # low|medium|high|critical
    category: str
    status: str           # pass|fail|error|notchecked|notapplicable|notselected


@dataclass
class ParsedReport:
    benchmark_id: str
    benchmark_version: str
    controls: list[ParsedControlResult]

    @property
    def total(self) -> int:
        return len(self.controls)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.controls if c.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.controls if c.status == "fail")

    @property
    def errored(self) -> int:
        return sum(1 for c in self.controls if c.status == "error")

    @property
    def not_checked(self) -> int:
        return sum(1 for c in self.controls if c.status == "notchecked")

    @property
    def not_applicable(self) -> int:
        return sum(1 for c in self.controls if c.status == "notapplicable")

    @property
    def not_selected(self) -> int:
        return sum(1 for c in self.controls if c.status == "notselected")

    @property
    def is_vacuous(self) -> bool:
        """
        True when oscap ran, exited cleanly, and wrote a non-empty report,
        but the profile selected zero rules to actually evaluate — every
        result is 'notselected'. This is the exact failure signature of a
        profile id that doesn't scope to any rules in the given datastream
        (as opposed to a profile that legitimately scopes to rules which are
        then correctly excluded as notapplicable to a container). Silently
        treating this as a normal completed scan is what produces the
        "Score N/A, Passed 0, Failed 0" symptom with no diagnostic trail.
        """
        return self.total > 0 and self.not_selected == self.total

    @property
    def failed_by_severity(self) -> dict[str, int]:
        """Severity breakdown of failed controls only — used for the
        dashboard's severity chart and per-scan diagnostics."""
        counts: dict[str, int] = {}
        for c in self.controls:
            if c.status == "fail":
                counts[c.severity] = counts.get(c.severity, 0) + 1
        return counts

    @property
    def score(self) -> float | None:
        """
        Returns None (not 0.0) when nothing was actually scored. This matters
        in practice: many CIS server-hardening rules (bootloader, GRUB,
        kernel module blacklisting, physical console checks, etc.) are
        legitimately 'notapplicable' inside any Docker container regardless
        of which profile is chosen, since containers don't have systemd as
        PID 1, a real /boot, or kernel-level access. A scan can therefore
        complete successfully with zero pass/fail results — that is "no
        applicable data", not "0% compliant", and the two must not be
        conflated in the UI or in trend charts.
        """
        scored = self.passed + self.failed
        if scored == 0:
            return None
        return round((self.passed / scored) * 100, 2)


class ScanEngineAdapter(ABC):
    """
    Interface every scan engine adapter must implement. This is what makes
    CIS-CAT PRO and OpenSCAP interchangeable (FR-14) — the orchestration
    service (ScanService) only ever talks to this interface.
    """

    engine_name: str

    @abstractmethod
    def build_scan_command(self, benchmark_id: str, datastream_path: str | None = None) -> list[str]:
        """Return the argv list to exec inside the target container to run the scan.
        `datastream_path`, when provided, is the SCAP content file ScanService
        auto-detected inside the target (OpenSCAP only — CIS-CAT ignores it
        and drives its own already-installed CLI instead)."""
        raise NotImplementedError

    @abstractmethod
    def result_file_path(self, benchmark_id: str) -> str:
        """Path inside the target container where the raw report will be written."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw_report_bytes: bytes, benchmark_id: str) -> ParsedReport:
        raise NotImplementedError
