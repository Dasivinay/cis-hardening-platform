"""
Regression coverage for the scan pipeline hardening: pre-flight checks
(oscap availability, datastream auto-detection, profile validation),
retries/validation on Docker file extraction, XML validation before
parsing, atomic persistence with rollback on failure, and DB-level
cascade deletes.
"""
from unittest.mock import patch, MagicMock
import pytest

from app.services.scan_service import ScanService
from app.utils.errors import ExternalServiceError


def _seed_scan(app):
    from app.extensions import db
    from app.models.user import User
    from app.models.container import Container
    from app.models.scan import Scan

    admin = User.query.filter_by(email="admin@test.com").first()
    container = Container(name="hardening-target", image="ubuntu:24.04", status="running", created_by_id=admin.id)
    db.session.add(container)
    db.session.flush()
    scan = Scan(container_id=container.id, triggered_by_id=admin.id, engine="openscap", benchmark_id="xccdf_org.ssgproject.content_profile_cis_level1_server", status="queued")
    db.session.add(scan)
    db.session.commit()
    return scan.id


def _mock_exec_router(responses: dict):
    """
    Builds a side_effect function for exec_in_target that returns a canned
    response based on which command was actually invoked, matching the
    real multi-step pre-flight pipeline (oscap check -> datastream find ->
    profile list -> actual scan) instead of assuming a single call.
    `responses` maps a substring to match against `" ".join(command)` to
    the (exit_code, output_or_tuple) to return.
    """
    def _router(container_id, command, timeout=None, demux=False):
        joined = " ".join(command)
        for key, value in responses.items():
            if key in joined:
                return value
        raise AssertionError(f"Unexpected exec_in_target call not covered by test mock: {joined}")
    return _router


def _happy_path_preflight_responses(datastream_path="/usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml",
                                     profile="xccdf_org.ssgproject.content_profile_cis_level1_server"):
    return {
        "command -v oscap": (0, "/usr/bin/oscap"),
        "find /usr/share/xml/scap": (0, datastream_path),
        "cat /etc/os-release": (0, "ID=ubuntu\nVERSION_ID=\"24.04\""),
        "oscap info --profiles": (0, f"{profile}\tCIS Level 1 Server"),
    }


def test_scan_marked_failed_when_report_never_appears(app, client, admin_token):
    scan_id = _seed_scan(app)
    service = ScanService()

    responses = _happy_path_preflight_responses()
    responses["oscap xccdf eval"] = (0, ("ok", ""))

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)), \
         patch.object(service.docker, "file_exists_in_target", return_value=(False, 0)), \
         patch("app.services.scan_service.REPORT_POLL_ATTEMPTS", 1), \
         patch("app.services.scan_service.REPORT_POLL_DELAY_SECONDS", 0):
        with pytest.raises(ExternalServiceError):
            service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"
    assert "report" in scan.error_message.lower()


def test_scan_marked_failed_on_corrupt_tar_archive(app, client, admin_token):
    scan_id = _seed_scan(app)
    service = ScanService()

    class FakeContainer:
        def get_archive(self, path):
            return (iter([b"not a valid tar stream at all"]), {})

    responses = _happy_path_preflight_responses()
    responses["oscap xccdf eval"] = (0, ("ok", ""))

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)), \
         patch.object(service.docker, "file_exists_in_target", return_value=(True, 1234)):
        service.docker._client = MagicMock()
        service.docker._client.containers.get.return_value = FakeContainer()
        with patch("app.services.scan_service.COPY_RETRY_ATTEMPTS", 1), \
             patch("app.services.scan_service.COPY_RETRY_DELAY_SECONDS", 0):
            with pytest.raises(ExternalServiceError):
                service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"
    assert scan.error_message is not None


def test_scan_marked_failed_on_malformed_xml(app, client, admin_token):
    scan_id = _seed_scan(app)
    service = ScanService()

    responses = _happy_path_preflight_responses()
    responses["oscap xccdf eval"] = (0, ("ok", ""))

    with patch.object(service, "_extract_file_from_container", return_value=b"<not><valid<xml"):
        with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)), \
             patch.object(service.docker, "file_exists_in_target", return_value=(True, 100)):
            with pytest.raises(ExternalServiceError, match="not well-formed XML"):
                service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"
    assert "not well-formed xml" in scan.error_message.lower()


def test_scan_never_marked_completed_without_successful_parse(app, client, admin_token):
    """Directly enforces the core requirement: never mark a scan completed
    unless parsing (and persistence) actually succeeded."""
    scan_id = _seed_scan(app)
    service = ScanService()

    with patch.object(service.docker, "exec_in_target", side_effect=ExternalServiceError("docker unreachable")):
        with pytest.raises(ExternalServiceError):
            service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"
    assert scan.status != "completed"


def test_deleting_scan_cascades_to_scan_result_controls(app, client, admin_token):
    """DB-level cascade — deletes via raw SQL too, not just the ORM."""
    from app.extensions import db
    from app.models.control import Control, ScanResultControl
    from app.models.scan import Scan

    scan_id = _seed_scan(app)
    control = Control(rule_id="cascade_rule_x", title="t", severity="low", category="c")
    db.session.add(control)
    db.session.flush()
    src = ScanResultControl(scan_id=scan_id, control_id=control.id, status="pass")
    db.session.add(src)
    db.session.commit()
    src_id = src.id

    db.session.execute(db.text("DELETE FROM scans WHERE id = :id"), {"id": scan_id})
    db.session.commit()

    assert Scan.query.get(scan_id) is None
    assert ScanResultControl.query.get(src_id) is None


def test_oscap_exit_code_1_is_reported_as_real_error_not_missing_report(app, client, admin_token):
    """
    Direct regression test for the reported bug: oscap exit code 1 means a
    real evaluation error (per the official man page) and must be surfaced
    as such — not silently treated as success, leaving the person staring
    at a misleading 'report file was never produced' message that hides
    the actual cause.
    """
    scan_id = _seed_scan(app)
    service = ScanService()

    oscap_error_text = (
        'No profile matching suffix "xccdf_org.ssgproject.content_profile_cis_level1_server" '
        'was found.'
    )
    responses = _happy_path_preflight_responses()
    # Profile validation passes (profile IS listed) but the real eval still
    # fails — covers the case where content drifted between the list call
    # and the eval call, or the pre-check itself was inconclusive.
    responses["oscap xccdf eval"] = (1, ("", oscap_error_text))

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)):
        with pytest.raises(ExternalServiceError, match="expected 0 or 2"):
            service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"
    assert "profile matching suffix" in scan.error_message
    assert "was never produced" not in scan.error_message
    # Full stdout/stderr must be persisted regardless, per requirement #6.
    assert scan.oscap_stderr == oscap_error_text


def test_oscap_exit_code_2_findings_present_is_not_treated_as_error(app, client, admin_token):
    """Exit code 2 (rules failed/unknown, evaluation itself succeeded) must
    proceed to report extraction, not be treated as a scan failure."""
    scan_id = _seed_scan(app)
    service = ScanService()

    responses = _happy_path_preflight_responses()
    responses["oscap xccdf eval"] = (2, ("some rules failed, that's normal", ""))

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)), \
         patch.object(service, "_wait_for_report") as mock_wait:
        mock_wait.side_effect = Exception("stop here — we only care that exit code 2 got this far")
        with pytest.raises(Exception, match="stop here"):
            service.execute_scan(scan_id)

    mock_wait.assert_called_once()


def test_scan_marked_failed_when_report_is_entirely_notselected(app, client, admin_token):
    """
    Regression test for the original 'Score N/A / Passed 0 / Failed 0 / no
    controls imported' bug report: oscap can exit 0, write a well-formed
    non-empty report, and pass profile pre-flight validation (the profile id
    genuinely exists in the datastream) while still selecting zero rules to
    evaluate. This must surface as a FAILED scan with a diagnostic message,
    not silently complete with a vacuous N/A/0/0 result.
    """
    scan_id = _seed_scan(app)
    service = ScanService()

    vacuous_xml = b"""<?xml version="1.0"?>
    <Benchmark xmlns="http://checklists.nist.gov/xccdf/1.2" id="xccdf_org.ssgproject.content_benchmark_UBUNTU_24_04">
      <version>0.1.81</version>
      <Rule id="rule_a" severity="high"><title>A</title><description>d</description></Rule>
      <TestResult>
        <rule-result idref="rule_a"><result>notselected</result></rule-result>
      </TestResult>
    </Benchmark>"""

    responses = _happy_path_preflight_responses()
    responses["oscap xccdf eval"] = (0, ("ok", ""))

    with patch.object(service, "_extract_file_from_container", return_value=vacuous_xml):
        with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)), \
             patch.object(service.docker, "file_exists_in_target", return_value=(True, 500)):
            with pytest.raises(ExternalServiceError, match="notselected"):
                service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"
    assert scan.status != "completed"
    assert "notselected" in scan.error_message.lower()


def test_missing_oscap_binary_fails_clearly_before_running_anything(app, client, admin_token):
    scan_id = _seed_scan(app)
    service = ScanService()

    with patch.object(service.docker, "exec_in_target", return_value=(1, "sh: command not found")):
        with pytest.raises(ExternalServiceError, match="oscap.*not found"):
            service.execute_scan(scan_id)

    from app.models.scan import Scan
    scan = Scan.query.get(scan_id)
    assert scan.status == "failed"


def test_datastream_autodetect_picks_correct_content_among_multiple_versions(app, client, admin_token):
    """
    Regression test for the exact real bug this pipeline was built to catch:
    with multiple ssg-ubuntuNNNN-ds.xml versions present in the target
    (e.g. leftover from a prior content build), the resolver must not pick
    an arbitrary/oldest one — it should prefer an exact /etc/os-release
    match, which is what actually fixed a real "No profile matching
    suffix... found" failure during development.
    """
    from app.models.scan import Scan

    scan_id = _seed_scan(app)
    container_id = Scan.query.get(scan_id).container_id
    service = ScanService()

    multi_candidates = (
        "/usr/share/xml/scap/ssg/content/ssg-ubuntu1604-ds.xml\n"
        "/usr/share/xml/scap/ssg/content/ssg-ubuntu2204-ds.xml\n"
        "/usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml"
    )
    responses = {
        "find /usr/share/xml/scap": (0, multi_candidates),
        "cat /etc/os-release": (0, 'ID=ubuntu\nVERSION_ID="24.04"'),
    }

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)):
        resolved = service._resolve_datastream_path(container_id)

    assert resolved == "/usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml"


def test_datastream_autodetect_falls_back_to_highest_version_without_os_release_match(app, client, admin_token):
    """When no candidate matches /etc/os-release exactly, must still resolve
    deterministically (highest/last after sort) rather than error out."""
    from app.models.scan import Scan

    scan_id = _seed_scan(app)
    container_id = Scan.query.get(scan_id).container_id
    service = ScanService()

    multi_candidates = (
        "/usr/share/xml/scap/ssg/content/ssg-ubuntu1604-ds.xml\n"
        "/usr/share/xml/scap/ssg/content/ssg-ubuntu2204-ds.xml\n"
        "/usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml"
    )
    responses = {
        "find /usr/share/xml/scap": (0, multi_candidates),
        "cat /etc/os-release": (0, "ID=debian\nVERSION_ID=\"12\""),  # deliberately non-matching
    }

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)):
        resolved = service._resolve_datastream_path(container_id)

    assert resolved == "/usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml"


def test_profile_validation_rejects_unknown_profile_with_actionable_message(app, client, admin_token):
    from app.models.scan import Scan

    scan_id = _seed_scan(app)
    container_id = Scan.query.get(scan_id).container_id
    service = ScanService()

    responses = {
        "oscap info --profiles": (0, "xccdf_org.ssgproject.content_profile_standard\tStandard"),
    }

    with patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)):
        with pytest.raises(ExternalServiceError, match="was not found in datastream"):
            service._validate_profile(
                container_id, "/some/ds.xml", "xccdf_org.ssgproject.content_profile_does_not_exist"
            )


def test_profile_id_extraction_handles_multiple_oscap_output_formats():
    """oscap info output format isn't stable across builds — this asserts
    the extractor works regardless of tab-delimited, colon-delimited, or
    bare-token formatting."""
    tab_delimited = "xccdf_org.ssgproject.content_profile_cis_level1_server\tCIS Level 1 Server"
    colon_delimited = "Id: xccdf_org.ssgproject.content_profile_cis_level1_server"
    bare = "  xccdf_org.ssgproject.content_profile_cis_level1_server  \n    Title: CIS Level 1 Server"

    for output in (tab_delimited, colon_delimited, bare):
        ids = ScanService._parse_profile_ids(output)
        assert "xccdf_org.ssgproject.content_profile_cis_level1_server" in ids


def _seed_container(app, image="cis-platform/ubuntu-scan-target:latest", docker_container_id="old-container-id"):
    from app.extensions import db
    from app.models.user import User
    from app.models.container import Container

    admin = User.query.filter_by(email="admin@test.com").first()
    container = Container(
        name="drift-target", image=image, status="running",
        docker_container_id=docker_container_id, created_by_id=admin.id,
    )
    db.session.add(container)
    db.session.commit()
    return container.id


def test_ensure_current_image_recreates_stale_container(app, client, admin_token):
    """
    Core regression test for the bug that survived multiple rounds of
    otherwise-correct fixes: a target container created from an old image
    build must be transparently recreated before the next scan, not
    silently scanned as-is. Simulates the exact drift scenario — the image
    tag now resolves to a different image ID than the one the tracked
    container was actually created from.
    """
    from app.services.docker_service import DockerService
    from app.models.container import Container

    container_id = _seed_container(app)
    service = DockerService()

    old_container = MagicMock()
    old_container.name = "cis-target-drift-target"
    old_container.attrs = {"Image": "sha256:OLD"}
    old_container.reload.return_value = None
    old_container.remove.return_value = None

    fresh_image = MagicMock()
    fresh_image.id = "sha256:NEW"

    new_container = MagicMock()
    new_container.id = "new-container-id"

    fake_client = MagicMock()
    fake_client.images.get.return_value = fresh_image
    fake_client.containers.get.return_value = old_container
    fake_client.containers.run.return_value = new_container
    fake_client.networks.get.return_value = MagicMock()  # pretend the configured network exists
    service._client = fake_client

    with app.app_context():
        recreated = service.ensure_current_image(container_id)

    assert recreated is True
    old_container.remove.assert_called_once_with(force=True)
    fake_client.containers.run.assert_called_once()
    _, run_kwargs = fake_client.containers.run.call_args
    assert run_kwargs["name"] == "cis-target-drift-target"

    with app.app_context():
        record = Container.query.get(container_id)
        assert record.docker_container_id == "new-container-id"


def test_ensure_current_image_noop_when_already_fresh(app, client, admin_token):
    """When the tracked container's image ID already matches the current
    tag resolution, nothing should be touched — this must not recreate a
    perfectly good target on every single scan."""
    from app.services.docker_service import DockerService
    from app.models.container import Container

    container_id = _seed_container(app)
    service = DockerService()

    current_container = MagicMock()
    current_container.attrs = {"Image": "sha256:SAME"}
    current_container.reload.return_value = None

    current_image = MagicMock()
    current_image.id = "sha256:SAME"

    fake_client = MagicMock()
    fake_client.images.get.return_value = current_image
    fake_client.containers.get.return_value = current_container
    service._client = fake_client

    with app.app_context():
        recreated = service.ensure_current_image(container_id)

    assert recreated is False
    fake_client.containers.run.assert_not_called()

    with app.app_context():
        record = Container.query.get(container_id)
        assert record.docker_container_id == "old-container-id"  # unchanged


def test_scan_recreates_stale_target_transparently_then_completes(app, client, admin_token):
    """End-to-end: when ensure_current_image reports a recreation happened,
    execute_scan must log it and continue on to run a normal, successful
    scan — drift detection should never itself block a healthy scan."""
    scan_id = _seed_scan(app)
    service = ScanService()

    from app.services.parser.base import ParsedReport, ParsedControlResult
    parsed = ParsedReport(
        benchmark_id="xccdf_org.ssgproject.content_profile_cis_level1_server",
        benchmark_version="0.1.81",
        controls=[
            ParsedControlResult("r1", "Rule 1", "", "medium", "General Hardening", "pass"),
            ParsedControlResult("r2", "Rule 2", "", "high", "General Hardening", "fail"),
        ],
    )

    responses = _happy_path_preflight_responses()
    responses["oscap xccdf eval"] = (0, ("ok", ""))

    with patch.object(service.docker, "ensure_current_image", return_value=True), \
         patch.object(service.docker, "exec_in_target", side_effect=_mock_exec_router(responses)), \
         patch.object(service.docker, "file_exists_in_target", return_value=(True, 100)), \
         patch.object(service, "_extract_file_from_container", return_value=b"<x/>"), \
         patch.object(service, "_validate_xml", return_value=None), \
         patch("app.services.parser.openscap_parser.OpenSCAPAdapter.parse", return_value=parsed):
        result = service.execute_scan(scan_id)

    assert result.status == "completed"
    assert result.passed_controls == 1
    assert result.failed_controls == 1
    assert result.overall_score == 50.0
