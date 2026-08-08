from app.services.parser.openscap_parser import OpenSCAPAdapter

SAMPLE_XCCDF = b"""<?xml version="1.0"?>
<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.2" id="xccdf_org.ssgproject.content_benchmark_UBUNTU_22_04">
  <version>0.1.72</version>
  <Rule id="xccdf_org.ssgproject.content_rule_sshd_disable_root_login" severity="high">
    <title>Disable SSH Root Login</title>
    <description>Root should not log in via SSH.</description>
  </Rule>
  <Rule id="xccdf_org.ssgproject.content_rule_ufw_enabled" severity="high">
    <title>Enable UFW</title>
    <description>Firewall should be enabled.</description>
  </Rule>
  <TestResult>
    <rule-result idref="xccdf_org.ssgproject.content_rule_sshd_disable_root_login">
      <result>pass</result>
    </rule-result>
    <rule-result idref="xccdf_org.ssgproject.content_rule_ufw_enabled">
      <result>fail</result>
    </rule-result>
  </TestResult>
</Benchmark>
"""


def test_openscap_parse_counts_pass_and_fail():
    adapter = OpenSCAPAdapter()
    report = adapter.parse(SAMPLE_XCCDF, benchmark_id="xccdf_org.ssgproject.content_benchmark_UBUNTU_22_04")

    assert report.total == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.score == 50.0

    ssh_control = next(c for c in report.controls if "sshd_disable_root_login" in c.rule_id)
    assert ssh_control.status == "pass"
    assert ssh_control.category == "SSH"

    fw_control = next(c for c in report.controls if "ufw_enabled" in c.rule_id)
    assert fw_control.status == "fail"
    assert fw_control.category == "Firewall"


VACUOUS_XCCDF = b"""<?xml version="1.0" encoding="UTF-8"?>
<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.2" id="xccdf_org.ssgproject.content_benchmark_UBUNTU_24_04">
  <version>0.1.81</version>
  <Rule id="xccdf_org.ssgproject.content_rule_sshd_disable_root_login" severity="high">
    <title>Disable SSH Root Login</title>
    <description>SSH root login should be disabled.</description>
  </Rule>
  <Rule id="xccdf_org.ssgproject.content_rule_ufw_enabled" severity="medium">
    <title>Enable UFW</title>
    <description>Firewall should be enabled.</description>
  </Rule>
  <TestResult>
    <rule-result idref="xccdf_org.ssgproject.content_rule_sshd_disable_root_login">
      <result>notselected</result>
    </rule-result>
    <rule-result idref="xccdf_org.ssgproject.content_rule_ufw_enabled">
      <result>notselected</result>
    </rule-result>
  </TestResult>
</Benchmark>
"""


def test_openscap_all_notselected_is_flagged_vacuous_not_scored_zero():
    """
    Regression test for the 'Score N/A / Passed 0 / Failed 0 / no controls'
    bug: a profile id that exists in the datastream but selects zero rules
    produces a well-formed report where every rule-result is 'notselected'.
    This must be distinguishable from genuine 'notapplicable' results (which
    are expected and normal inside a container), so ScanService can reject
    it as a scan failure instead of silently completing with N/A.
    """
    adapter = OpenSCAPAdapter()
    report = adapter.parse(VACUOUS_XCCDF, benchmark_id="xccdf_org.ssgproject.content_profile_bad_scope")

    assert report.total == 2
    assert report.passed == 0
    assert report.failed == 0
    assert report.not_selected == 2
    assert report.not_applicable == 0  # must NOT be folded into notapplicable
    assert report.score is None
    assert report.is_vacuous is True


def test_openscap_notapplicable_is_not_flagged_vacuous():
    """A report with real pass/fail plus legitimately-excluded rules (e.g.
    a bootloader check inside a container) must NOT trip the vacuous gate —
    that's a normal, valid completed scan."""
    adapter = OpenSCAPAdapter()
    report = adapter.parse(SAMPLE_XCCDF, benchmark_id="xccdf_org.ssgproject.content_benchmark_UBUNTU_22_04")

    assert report.is_vacuous is False
