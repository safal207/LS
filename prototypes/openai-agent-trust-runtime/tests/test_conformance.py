from ls_agent_trust.conformance import run_conformance


def test_all_ten_reference_conformance_cases_pass() -> None:
    report = run_conformance()

    assert report.ok is True
    assert report.passed == 10
    assert report.failed == 0
    assert len(report.cases) == 10
