import io
import logging
import re
import tarfile
import time
from datetime import datetime, timezone

from lxml import etree

from app.extensions import db
from app.repositories.scan_repository import (
    ScanRepository,
    ControlRepository,
    ScanResultControlRepository,
)
from app.repositories.container_repository import ContainerRepository
from app.services.docker_service import DockerService
from app.services.parser.openscap_parser import OpenSCAPAdapter
from app.services.parser.ciscat_parser import CISCATAdapter
from app.utils.errors import NotFoundError, ValidationError, ExternalServiceError


logger = logging.getLogger("secharden.scan_service")


ADAPTERS = {
    "openscap": OpenSCAPAdapter(),
    "ciscat": CISCATAdapter(),
}


# ---------------------------------------------------------------------------
# Scan/report configuration
# ---------------------------------------------------------------------------

# How long we're willing to wait for the report file to appear/finish writing
# after the scan command returns.
REPORT_POLL_ATTEMPTS = 5
REPORT_POLL_DELAY_SECONDS = 2


# Retries for Docker archive copy.
COPY_RETRY_ATTEMPTS = 3
COPY_RETRY_DELAY_SECONDS = 2


# Maximum time allowed for the actual scan command.
SCAN_COMMAND_TIMEOUT_SECONDS = 600


# Directory tree searched inside the target container for SCAP datastreams.
DATASTREAM_SEARCH_ROOT = "/usr/share/xml/scap"


# oscap info output is not identical across all OpenSCAP versions/builds.
# This pattern extracts normal SSG/XCCDF profile IDs.
PROFILE_ID_PATTERN = re.compile(
    r"xccdf_[\w.\-]+_profile_[\w.\-]+"
)


class ScanService:
    def __init__(self):
        self.scans = ScanRepository()
        self.controls = ControlRepository()
        self.results = ScanResultControlRepository()
        self.containers = ContainerRepository()
        self.docker = DockerService()

    # ------------------------------------------------------------------ #
    # General helpers
    # ------------------------------------------------------------------ #

    def _get_adapter(self, engine: str):
        adapter = ADAPTERS.get(engine)

        if not adapter:
            raise ValidationError(
                f"Unknown scan engine '{engine}'. "
                f"Supported: {list(ADAPTERS.keys())}"
            )

        return adapter

    def create_scan_record(
        self,
        container_id: str,
        engine: str,
        benchmark_id: str,
        triggered_by_id: str,
    ):
        container = self.containers.get_by_id(container_id)

        if not container:
            raise NotFoundError("Target container not found.")

        self._get_adapter(engine)

        from app.models.scan import Scan

        scan = Scan(
            container_id=container_id,
            triggered_by_id=triggered_by_id,
            engine=engine,
            benchmark_id=benchmark_id,
            status="queued",
        )

        return self.scans.add(scan)

    # ------------------------------------------------------------------ #
    # Main scan execution
    # ------------------------------------------------------------------ #

    def execute_scan(self, scan_id: str):
        """
        Execute a security scan against the target container.

        Pipeline:

        1. Mark scan as running.
        2. Ensure the target container is based on the current image.
        3. For OpenSCAP:
           - Verify oscap exists.
           - Ensure CPE_NAME exists in /etc/os-release.
           - Detect the installed SCAP datastream.
           - Validate requested profile.
        4. Execute the scan.
        5. Validate scan exit code.
        6. Wait for report.
        7. Copy report from container.
        8. Validate XML.
        9. Parse report.
        10. Reject empty/vacuous results.
        11. Persist results atomically.
        12. Mark scan completed.
        13. On any failure, rollback and mark scan failed.
        """

        scan = self.scans.get_by_id(scan_id)

        if not scan:
            raise NotFoundError("Scan not found.")

        adapter = self._get_adapter(scan.engine)

        logger.info(
            "scan.start scan_id=%s container_id=%s engine=%s",
            scan.id,
            scan.container_id,
            scan.engine,
        )

        self.scans.update(
            scan,
            status="running",
            started_at=datetime.now(timezone.utc),
            error_message=None,
        )

        try:
            # ----------------------------------------------------------
            # Pre-flight: make sure target container uses current image
            # ----------------------------------------------------------

            recreated = self.docker.ensure_current_image(scan.container_id)

            if recreated:
                logger.warning(
                    "scan.target_recreated scan_id=%s container_id=%s "
                    "(target was running a stale image; replaced before scanning)",
                    scan.id,
                    scan.container_id,
                )

            # ----------------------------------------------------------
            # OpenSCAP pre-flight checks
            # ----------------------------------------------------------

            datastream_path = None

            if scan.engine == "openscap":

                # Check that oscap exists.
                self._ensure_oscap_available(scan.container_id)

                # IMPORTANT:
                # Ensure /etc/os-release contains CPE_NAME.
                self._ensure_platform_cpe_configured(
                    scan.container_id
                )

                # Detect SCAP datastream.
                datastream_path = self._resolve_datastream_path(
                    scan.container_id
                )

                # Validate requested profile.
                self._validate_profile(
                    scan.container_id,
                    datastream_path,
                    scan.benchmark_id,
                )

            # ----------------------------------------------------------
            # Execute scan
            # ----------------------------------------------------------

            command = adapter.build_scan_command(
                scan.benchmark_id,
                datastream_path,
            )

            logger.info(
                "scan.command scan_id=%s argv=%s",
                scan.id,
                command,
            )

            exit_code, (stdout, stderr) = self.docker.exec_in_target(
                scan.container_id,
                command,
                timeout=SCAN_COMMAND_TIMEOUT_SECONDS,
                demux=True,
            )

            # Always save scan output.
            self.scans.update(
                scan,
                datastream_path=datastream_path,
                oscap_stdout=stdout,
                oscap_stderr=stderr,
            )

            logger.info(
                "scan.command_complete scan_id=%s exit_code=%s",
                scan.id,
                exit_code,
            )

            # OpenSCAP:
            # 0 = successful evaluation
            # 2 = evaluation completed but one or more rules failed
            # Anything else = execution/evaluation failure
            if exit_code not in (0, 2):
                raise ExternalServiceError(
                    f"oscap exited with code {exit_code} "
                    f"(expected 0 or 2).\n"
                    f"--- stderr ---\n"
                    f"{(stderr or '(empty)')[-2000:]}\n"
                    f"--- stdout ---\n"
                    f"{(stdout or '(empty)')[-1000:]}"
                )

            # ----------------------------------------------------------
            # Wait for report
            # ----------------------------------------------------------

            report_path = adapter.result_file_path(
                scan.benchmark_id
            )

            self._wait_for_report(
                scan.container_id,
                report_path,
            )

            # ----------------------------------------------------------
            # Copy report from container
            # ----------------------------------------------------------

            raw_bytes = self._extract_file_from_container(
                scan.container_id,
                report_path,
            )

            # ----------------------------------------------------------
            # Validate XML
            # ----------------------------------------------------------

            self._validate_xml(raw_bytes)

            # ----------------------------------------------------------
            # Parse report
            # ----------------------------------------------------------

            parsed = adapter.parse(
                raw_bytes,
                scan.benchmark_id,
            )

            logger.info(
                "scan.parsed scan_id=%s total=%s passed=%s "
                "failed=%s severity=%s",
                scan.id,
                parsed.total,
                parsed.passed,
                parsed.failed,
                parsed.failed_by_severity,
            )

            # ----------------------------------------------------------
            # Reject empty result
            # ----------------------------------------------------------

            if parsed.total == 0:
                raise ExternalServiceError(
                    f"oscap exited successfully and wrote a report, "
                    f"but it contained zero <rule-result> elements "
                    f"for profile '{scan.benchmark_id}'. "
                    f"This report is unusable — refusing to mark "
                    f"the scan completed."
                )

            # ----------------------------------------------------------
            # Reject vacuous result
            # ----------------------------------------------------------

            if parsed.is_vacuous:
                raise ExternalServiceError(
                    f"Profile '{scan.benchmark_id}' selected zero rules "
                    f"to evaluate against datastream "
                    f"'{datastream_path}' — every one of "
                    f"{parsed.total} rules came back 'notselected'. "
                    f"The profile id exists in the datastream "
                    f"(pre-flight check passed) but doesn't scope "
                    f"to any rules for this content. Choose a different "
                    f"profile id, or verify the datastream actually "
                    f"matches the target's platform."
                )

            # ----------------------------------------------------------
            # Persist results
            # ----------------------------------------------------------

            self._persist_results(
                scan,
                parsed,
            )

            # ----------------------------------------------------------
            # Mark completed
            # ----------------------------------------------------------

            self.scans.update(
                scan,
                status="completed",
                completed_at=datetime.now(timezone.utc),
                benchmark_version=parsed.benchmark_version,
                overall_score=parsed.score,
                total_controls=parsed.total,
                passed_controls=parsed.passed,
                failed_controls=parsed.failed,
                error_controls=parsed.errored,
                notchecked_controls=parsed.not_checked,
                notapplicable_controls=parsed.not_applicable,
                notselected_controls=parsed.not_selected,
            )

            logger.info(
                "scan.completed scan_id=%s score=%s",
                scan.id,
                parsed.score,
            )

        except Exception as exc:
            # Never leave partial DB changes.
            db.session.rollback()

            logger.error(
                "scan.failed scan_id=%s error=%s",
                scan.id,
                exc,
                exc_info=True,
            )

            # Re-fetch after rollback.
            scan = self.scans.get_by_id(scan_id)

            self.scans.update(
                scan,
                status="failed",
                error_message=str(exc),
                completed_at=datetime.now(timezone.utc),
            )

            raise

        return scan

    # ------------------------------------------------------------------ #
    # Pre-flight checks
    # ------------------------------------------------------------------ #

    def _ensure_oscap_available(self, container_id: str):
        """
        Verify that the oscap executable exists inside the target container.
        """

        exit_code, output = self.docker.exec_in_target(
            container_id,
            [
                "sh",
                "-c",
                "command -v oscap",
            ],
            timeout=15,
        )

        if exit_code != 0 or not output.strip():
            raise ExternalServiceError(
                "The 'oscap' executable was not found inside the target "
                "container. The target image must be built from "
                "targets/ubuntu-scan-target/Dockerfile "
                "(run: docker compose build scan-target-image-builder), "
                "which installs openscap-scanner and openscap-utils."
            )

        logger.info(
            "scan.oscap_found container_id=%s path=%s",
            container_id,
            output.strip(),
        )

    # ------------------------------------------------------------------ #
    # OS detection
    # ------------------------------------------------------------------ #

    def _detect_os_release(
        self,
        container_id: str,
    ) -> tuple[str | None, str | None]:
        """
        Read ID and VERSION_ID from /etc/os-release.
        """

        exit_code, output = self.docker.exec_in_target(
            container_id,
            [
                "sh",
                "-c",
                "cat /etc/os-release 2>/dev/null",
            ],
            timeout=15,
        )

        if exit_code != 0:
            return None, None

        os_id = None
        version_id = None

        for line in output.splitlines():

            if line.startswith("ID="):
                os_id = (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                    .lower()
                )

            elif line.startswith("VERSION_ID="):
                version_id = (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                )

        return os_id, version_id

    # ------------------------------------------------------------------ #
    # CPE configuration
    # ------------------------------------------------------------------ #

    def _ensure_platform_cpe_configured(
        self,
        container_id: str,
    ):
        """
        Ensure the target container exposes CPE_NAME in /etc/os-release.

        OpenSCAP uses the platform CPE to determine whether
        platform-specific rules are applicable.

        If CPE_NAME is missing, rules can incorrectly become
        notapplicable/notselected even though the scan itself succeeds.

        Currently automatic CPE configuration is supported for Ubuntu.
        """

        # --------------------------------------------------------------
        # First check whether CPE_NAME already exists.
        # --------------------------------------------------------------

        exit_code, output = self.docker.exec_in_target(
            container_id,
            [
                "sh",
                "-c",
                "grep '^CPE_NAME=' /etc/os-release 2>/dev/null || true",
            ],
            timeout=15,
        )

        if exit_code != 0:
            raise ExternalServiceError(
                "Could not inspect /etc/os-release inside the "
                "target container."
            )

        if output and output.strip():
            logger.info(
                "scan.cpe_configured container_id=%s value=%s",
                container_id,
                output.strip(),
            )
            return

        # --------------------------------------------------------------
        # CPE_NAME does not exist.
        # Read /etc/os-release.
        # --------------------------------------------------------------

        exit_code, output = self.docker.exec_in_target(
            container_id,
            [
                "sh",
                "-c",
                "cat /etc/os-release 2>/dev/null",
            ],
            timeout=15,
        )

        if exit_code != 0 or not output.strip():
            raise ExternalServiceError(
                "Could not read /etc/os-release from the target "
                "container; cannot configure the platform CPE."
            )

        # --------------------------------------------------------------
        # Parse OS information.
        # --------------------------------------------------------------

        os_id = None
        version_id = None

        for line in output.splitlines():

            if line.startswith("ID="):
                os_id = (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                    .lower()
                )

            elif line.startswith("VERSION_ID="):
                version_id = (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                )

        # --------------------------------------------------------------
        # Currently support Ubuntu.
        # --------------------------------------------------------------

        if os_id != "ubuntu" or not version_id:
            raise ExternalServiceError(
                "Unsupported target platform for automatic CPE "
                f"configuration: ID={os_id!r}, "
                f"VERSION_ID={version_id!r}"
            )

        # --------------------------------------------------------------
        # Build Ubuntu CPE.
        #
        # Example:
        # Ubuntu 24.04
        #
        # cpe:/o:canonical:ubuntu_linux:24.04
        # --------------------------------------------------------------

        cpe_name = (
            f"cpe:/o:canonical:ubuntu_linux:{version_id}"
        )

        logger.info(
            "scan.cpe_configuring container_id=%s "
            "os_id=%s version_id=%s cpe=%s",
            container_id,
            os_id,
            version_id,
            cpe_name,
        )

        # --------------------------------------------------------------
        # Write CPE_NAME into /etc/os-release.
        #
        # If CPE_NAME already exists, replace it.
        # Otherwise append it.
        # --------------------------------------------------------------

        command = [
            "sh",
            "-c",
            (
                "if grep -q '^CPE_NAME=' /etc/os-release; then "
                "sed -i 's|^CPE_NAME=.*|CPE_NAME=\""
                + cpe_name
                + "\"|' /etc/os-release; "
                "else "
                "printf '\\nCPE_NAME=\""
                + cpe_name
                + "\"\\n' >> /etc/os-release; "
                "fi"
            ),
        ]

        exit_code, result = self.docker.exec_in_target(
            container_id,
            command,
            timeout=15,
        )

        if exit_code != 0:
            raise ExternalServiceError(
                f"Failed to configure CPE_NAME='{cpe_name}' "
                f"in target /etc/os-release: "
                f"{result or '(no output)'}"
            )

        # --------------------------------------------------------------
        # Verify that CPE_NAME was actually written.
        # --------------------------------------------------------------

        exit_code, verification = self.docker.exec_in_target(
            container_id,
            [
                "sh",
                "-c",
                "grep '^CPE_NAME=' /etc/os-release 2>/dev/null",
            ],
            timeout=15,
        )

        if exit_code != 0 or not verification.strip():
            raise ExternalServiceError(
                "CPE_NAME configuration could not be verified "
                f"in the target container. Expected '{cpe_name}'."
            )

        # Verify the actual value, not just that some CPE_NAME exists.
        expected_line = f'CPE_NAME="{cpe_name}"'

        if expected_line not in verification.strip():
            raise ExternalServiceError(
                f"CPE_NAME verification failed. "
                f"Expected '{expected_line}', "
                f"but received '{verification.strip()}'."
            )

        logger.info(
            "scan.cpe_configured container_id=%s value=%s",
            container_id,
            verification.strip(),
        )

    # ------------------------------------------------------------------ #
    # SCAP datastream detection
    # ------------------------------------------------------------------ #

    def _resolve_datastream_path(
        self,
        container_id: str,
    ) -> str:
        """
        Auto-detect installed SCAP datastream.
        """

        find_cmd = [
            "sh",
            "-c",
            (
                f"find {DATASTREAM_SEARCH_ROOT} "
                f"-maxdepth 4 "
                f"-type f "
                f"-name '*-ds.xml' "
                f"2>/dev/null"
            ),
        ]

        exit_code, output = self.docker.exec_in_target(
            container_id,
            find_cmd,
            timeout=15,
        )

        candidates = [
            line.strip()
            for line in output.splitlines()
            if line.strip()
        ]

        if not candidates:
            raise ExternalServiceError(
                f"No SCAP datastream (*-ds.xml) found under "
                f"{DATASTREAM_SEARCH_ROOT} inside the target container. "
                "The target image must ship SCAP content — rebuild it "
                "from targets/ubuntu-scan-target/Dockerfile."
            )

        if len(candidates) == 1:
            logger.info(
                "scan.datastream_detected container_id=%s path=%s",
                container_id,
                candidates[0],
            )

            return candidates[0]

        # Multiple candidates.
        os_id, os_version = self._detect_os_release(
            container_id
        )

        version_token = (
            os_version or ""
        ).replace(".", "")

        for candidate in sorted(candidates):

            lowered = candidate.lower()

            if (
                os_id
                and os_id in lowered
                and version_token
                and version_token in lowered
            ):
                logger.info(
                    "scan.datastream_detected "
                    "container_id=%s path=%s "
                    "(matched os-release %s %s)",
                    container_id,
                    candidate,
                    os_id,
                    os_version,
                )

                return candidate

        candidates.sort()

        chosen = candidates[-1]

        logger.warning(
            "scan.datastream_ambiguous "
            "container_id=%s candidates=%s chosen=%s "
            "(no exact /etc/os-release match; "
            "picked the lexicographically last candidate)",
            container_id,
            candidates,
            chosen,
        )

        return chosen

    # ------------------------------------------------------------------ #
    # Profile validation
    # ------------------------------------------------------------------ #

    def _validate_profile(
        self,
        container_id: str,
        datastream_path: str,
        benchmark_id: str,
    ):
        """
        Confirm requested profile exists in the resolved datastream.
        """

        available = self._list_available_profiles(
            container_id,
            datastream_path,
        )

        # oscap info failed completely.
        # Treat this as best effort and allow real scan to proceed.
        if available is None:
            return

        if benchmark_id not in available:
            raise ExternalServiceError(
                f"Profile '{benchmark_id}' was not found in datastream "
                f"'{datastream_path}'. "
                f"Available profiles: "
                f"{', '.join(available) if available else '(none listed)'}."
            )

        logger.info(
            "scan.profile_validated "
            "container_id=%s benchmark_id=%s datastream=%s",
            container_id,
            benchmark_id,
            datastream_path,
        )

    def _list_available_profiles(
        self,
        container_id: str,
        datastream_path: str,
    ) -> list[str] | None:
        """
        Run oscap info and extract available profile IDs.
        """

        commands = (
            [
                "oscap",
                "info",
                "--profiles",
                datastream_path,
            ],
            [
                "oscap",
                "info",
                datastream_path,
            ],
        )

        ran_successfully = False

        for command in commands:

            exit_code, output = self.docker.exec_in_target(
                container_id,
                command,
                timeout=30,
            )

            if exit_code != 0:
                logger.warning(
                    "scan.profile_list_failed "
                    "container_id=%s command=%s "
                    "exit_code=%s output=%s",
                    container_id,
                    command,
                    exit_code,
                    (output or "")[-500:],
                )

                continue

            ran_successfully = True

            profiles = self._parse_profile_ids(
                output
            )

            if profiles:
                return profiles

        return (
            None
            if not ran_successfully
            else []
        )

    @staticmethod
    def _parse_profile_ids(output: str) -> list[str]:
        """
        Extract profile IDs from oscap info output.
        """

        if not output:
            return []

        matches = PROFILE_ID_PATTERN.findall(
            output
        )

        if matches:

            seen: set[str] = set()
            ordered: list[str] = []

            for match in matches:

                if match not in seen:
                    seen.add(match)
                    ordered.append(match)

            return ordered

        # Fallback for custom/non-SSG content.
        ids = []

        for line in output.splitlines():

            line = line.strip()

            if not line:
                continue

            for sep in ("\t", ":"):

                if sep in line:
                    line = line.split(
                        sep,
                        1,
                    )[0].strip()

                    break

            if line:
                ids.append(line)

        return ids

    # ------------------------------------------------------------------ #
    # Report retrieval
    # ------------------------------------------------------------------ #

    def _wait_for_report(
        self,
        container_id: str,
        path: str,
    ):
        last_error = None

        for attempt in range(
            1,
            REPORT_POLL_ATTEMPTS + 1,
        ):

            try:

                exists, size = self.docker.file_exists_in_target(
                    container_id,
                    path,
                )

                if exists and size > 0:

                    logger.info(
                        "scan.report_found "
                        "path=%s size=%s attempt=%s",
                        path,
                        size,
                        attempt,
                    )

                    return

                last_error = (
                    f"report file '{path}' "
                    f"{'is empty' if exists else 'does not exist'}"
                )

            except Exception as exc:
                last_error = str(exc)

            if attempt < REPORT_POLL_ATTEMPTS:
                time.sleep(
                    REPORT_POLL_DELAY_SECONDS
                )

        raise ExternalServiceError(
            "Report file was never produced after the "
            f"scan command completed: {last_error}"
        )

    # ------------------------------------------------------------------ #
    # Extract report from Docker
    # ------------------------------------------------------------------ #

    def _extract_file_from_container(
        self,
        container_record_id: str,
        path: str,
    ) -> bytes:
        """
        Copy a file from target container using Docker archive API.
        """

        record = self.containers.get_by_id(
            container_record_id
        )

        if not record:
            raise NotFoundError(
                "Target container record not found."
            )

        last_error = None

        for attempt in range(
            1,
            COPY_RETRY_ATTEMPTS + 1,
        ):

            try:

                handle = self.docker.client.containers.get(
                    record.docker_container_id
                )

                stream, stat = handle.get_archive(
                    path
                )

                buf = io.BytesIO()
                total_bytes = 0

                for chunk in stream:

                    buf.write(chunk)
                    total_bytes += len(chunk)

                if total_bytes == 0:
                    raise ExternalServiceError(
                        f"Docker returned an empty archive "
                        f"stream for '{path}'."
                    )

                buf.seek(0)

                try:

                    with tarfile.open(
                        fileobj=buf
                    ) as tf:

                        members = tf.getmembers()

                        if not members:
                            raise ExternalServiceError(
                                f"Archive for '{path}' "
                                "contained no files."
                            )

                        extracted = tf.extractfile(
                            members[0]
                        )

                        if extracted is None:
                            raise ExternalServiceError(
                                f"Could not extract '{path}' "
                                "from archive "
                                "(not a regular file?)."
                            )

                        data = extracted.read()

                except tarfile.TarError as tar_exc:

                    raise ExternalServiceError(
                        f"Corrupt or incomplete tar archive "
                        f"copying '{path}' from container "
                        f"(attempt {attempt}/"
                        f"{COPY_RETRY_ATTEMPTS}): "
                        f"{tar_exc}"
                    )

                if len(data) == 0:
                    raise ExternalServiceError(
                        f"Extracted file '{path}' is empty."
                    )

                logger.info(
                    "scan.report_copied "
                    "path=%s bytes=%s attempt=%s",
                    path,
                    len(data),
                    attempt,
                )

                return data

            except ExternalServiceError as exc:

                last_error = exc

                logger.warning(
                    "scan.copy_retry "
                    "path=%s attempt=%s error=%s",
                    path,
                    attempt,
                    exc,
                )

                if attempt < COPY_RETRY_ATTEMPTS:
                    time.sleep(
                        COPY_RETRY_DELAY_SECONDS
                    )

        raise ExternalServiceError(
            f"Failed to copy '{path}' out of the target "
            f"container after {COPY_RETRY_ATTEMPTS} attempts: "
            f"{last_error}"
        )

    # ------------------------------------------------------------------ #
    # XML validation
    # ------------------------------------------------------------------ #

    def _validate_xml(
        self,
        raw_bytes: bytes,
    ):
        """
        Verify report is valid XML before parsing.
        """

        if not raw_bytes or len(raw_bytes) == 0:
            raise ExternalServiceError(
                "Report file is empty — refusing to parse."
            )

        try:

            etree.fromstring(
                raw_bytes
            )

        except etree.XMLSyntaxError as exc:

            raise ExternalServiceError(
                "Report file is not well-formed XML — "
                f"refusing to parse partial data: {exc}"
            )

    # ------------------------------------------------------------------ #
    # Database persistence
    # ------------------------------------------------------------------ #

    def _persist_results(
        self,
        scan,
        parsed,
    ):
        """
        Persist all parsed controls in one transaction.
        """

        from app.models.control import (
            Control,
            ScanResultControl,
        )

        try:

            for pc in parsed.controls:

                control = self.controls.get_by_rule_id(
                    pc.rule_id
                )

                if not control:

                    control = Control(
                        rule_id=pc.rule_id,
                        title=pc.title,
                        description=pc.description,
                        severity=pc.severity,
                        category=pc.category,
                    )

                    db.session.add(control)

                    # Get control.id without committing.
                    db.session.flush()

                else:

                    control.title = pc.title
                    control.description = pc.description
                    control.severity = pc.severity
                    control.category = pc.category

                db.session.add(
                    ScanResultControl(
                        scan_id=scan.id,
                        control_id=control.id,
                        status=pc.status,
                    )
                )

            db.session.commit()

        except Exception:

            db.session.rollback()

            raise