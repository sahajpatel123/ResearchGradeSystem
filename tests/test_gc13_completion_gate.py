"""
GC-13 Completion Gate Tests: FINAL vs INCOMPLETE Validation.

Tests all validation rules for GC-13:
- status is computed-only (wire mismatch fails)
- missing_artifacts is computed-only (wire mismatch fails)
- FINAL requires all required artifacts
- FINAL requires derivation for derivational tasks
- INCOMPLETE requires non-empty missing_artifacts
- used_rag=true requires citations with GC-12 provenance
- All checks must be explicitly reported (closed registry)
- NOT_APPLICABLE requires reason
"""

import json
from pathlib import Path

import pytest

from src.core.gc13_computation import (
    ReportArtifacts,
    compute_missing_artifacts,
    compute_report_status,
)
from src.core.gc13_validators import (
    GC13ValidationError,
    validate_check_result,
    validate_checks_from_wire,
    validate_completion_gate,
    validate_incomplete_has_missing_artifacts,
    validate_missing_artifacts_mismatch,
    validate_rag_citations,
    validate_status_mismatch,
)
from src.core.report_checks import (
    CheckResult,
    CheckStatus,
    ReportChecks,
    ReportStatus,
    REQUIRED_CHECK_FIELDS,
)


def _load_fixture(name: str) -> dict:
    """Load a GC-13 fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / name
    with open(fixture_path, "r") as f:
        return json.load(f)


def _build_checks_from_fixture(checks_data: dict) -> ReportChecks:
    """Build ReportChecks from fixture data."""
    def build_check(check_data: dict) -> CheckResult:
        return CheckResult(
            status=CheckStatus(check_data["status"]),
            reason=check_data.get("reason"),
            payload_ref=check_data.get("payload_ref"),
        )
    
    return ReportChecks(
        units_check=build_check(checks_data["units_check"]),
        limits_check=build_check(checks_data["limits_check"]),
        numeric_check=build_check(checks_data["numeric_check"]),
        critic_check=build_check(checks_data["critic_check"]),
        known_result_check=build_check(checks_data["known_result_check"]),
    )


def _build_artifacts_from_fixture(data: dict) -> ReportArtifacts:
    """Build ReportArtifacts from fixture data."""
    artifacts_data = data["artifacts"]
    
    checks = None
    if "checks" in artifacts_data and artifacts_data["checks"] is not None:
        # Only build if all required fields present
        checks_data = artifacts_data["checks"]
        if all(field in checks_data for field in REQUIRED_CHECK_FIELDS):
            checks = _build_checks_from_fixture(checks_data)
    
    return ReportArtifacts(
        problem_restatement=artifacts_data.get("problem_restatement"),
        assumption_ledger=artifacts_data.get("assumption_ledger"),
        derivation_steps=artifacts_data.get("derivation_steps"),
        claims=artifacts_data.get("claims"),
        evidence_objects=artifacts_data.get("evidence_objects"),
        coverage_metrics=artifacts_data.get("coverage_metrics"),
        conclusion=artifacts_data.get("conclusion"),
        confidence=artifacts_data.get("confidence"),
        used_rag=artifacts_data.get("used_rag", False),
        citations=artifacts_data.get("citations"),
        checks=checks,
        task_kind=artifacts_data.get("task_kind"),
        non_derivational_reason=artifacts_data.get("non_derivational_reason"),
        run_manifest_ref=artifacts_data.get("run_manifest_ref"),
    )


class TestFinalRequiresAllRequiredArtifacts:
    """Test FINAL requires all required artifacts."""

    def test_final_requires_all_required_artifacts(self):
        """FINAL status requires all required artifacts present."""
        data = _load_fixture("gc13_pass_genuine_final_report.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.FINAL
        assert computed_missing == []

    def test_missing_coverage_makes_incomplete(self):
        """Missing coverage_metrics makes report INCOMPLETE."""
        data = _load_fixture("gc13_fail_final_missing_coverage.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert "coverage_metrics" in computed_missing

    def test_missing_assumption_ledger_makes_incomplete(self):
        """Missing assumption_ledger makes report INCOMPLETE."""
        data = _load_fixture("gc13_fail_final_missing_assumption_ledger.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert "assumption_ledger" in computed_missing


class TestStatusIsComputedNotTrustedFromWire:
    """Test status is computed-only; wire mismatch fails."""

    def test_status_is_computed_not_trusted_from_wire(self):
        """Wire status that doesn't match computed status fails."""
        data = _load_fixture("gc13_fail_status_mismatch.json")
        artifacts = _build_artifacts_from_fixture(data)
        wire_status = data.get("wire_status")
        
        computed_status = compute_report_status(artifacts)
        errors = validate_status_mismatch(wire_status, computed_status)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert wire_status == "FINAL"
        assert len(errors) == 1
        assert errors[0].category == "REPORT_STATUS_MISMATCH"

    def test_matching_wire_status_passes(self):
        """Wire status that matches computed status passes."""
        data = _load_fixture("gc13_pass_genuine_final_report.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        errors = validate_status_mismatch("FINAL", computed_status)
        
        assert computed_status == ReportStatus.FINAL
        assert len(errors) == 0


class TestMissingArtifactsIsComputedNotTrustedFromWire:
    """Test missing_artifacts is computed-only; wire mismatch fails."""

    def test_missing_artifacts_is_computed_not_trusted_from_wire(self):
        """Wire missing_artifacts that doesn't match computed fails."""
        data = _load_fixture("gc13_fail_missing_artifacts_mismatch.json")
        artifacts = _build_artifacts_from_fixture(data)
        wire_missing = data.get("wire_missing_artifacts")
        
        computed_missing = compute_missing_artifacts(artifacts)
        errors = validate_missing_artifacts_mismatch(wire_missing, computed_missing)
        
        assert len(errors) == 1
        assert errors[0].category == "MISSING_ARTIFACTS_MISMATCH"

    def test_matching_wire_missing_artifacts_passes(self):
        """Wire missing_artifacts that matches computed passes."""
        data = _load_fixture("gc13_pass_incomplete_with_missing_artifacts.json")
        artifacts = _build_artifacts_from_fixture(data)
        expected_missing = data.get("expected_missing_artifacts")
        
        computed_missing = compute_missing_artifacts(artifacts)
        errors = validate_missing_artifacts_mismatch(expected_missing, computed_missing)
        
        assert sorted(computed_missing) == sorted(expected_missing)
        assert len(errors) == 0


class TestIncompleteRequiresNonEmptyMissingArtifacts:
    """Test INCOMPLETE requires non-empty missing_artifacts."""

    def test_incomplete_requires_non_empty_missing_artifacts(self):
        """INCOMPLETE status must have non-empty missing_artifacts."""
        data = _load_fixture("gc13_pass_incomplete_with_missing_artifacts.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        errors = validate_incomplete_has_missing_artifacts(computed_status, computed_missing)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert len(computed_missing) > 0
        assert len(errors) == 0

    def test_incomplete_with_empty_missing_fails(self):
        """INCOMPLETE with empty missing_artifacts fails validation."""
        # This is a logic error - if status is INCOMPLETE, missing must be non-empty
        errors = validate_incomplete_has_missing_artifacts(ReportStatus.INCOMPLETE, [])
        
        assert len(errors) == 1
        assert errors[0].category == "INCOMPLETE_MISSING_ARTIFACTS_EMPTY"


class TestRagUsedRequiresCitationsAndProvenance:
    """Test used_rag=true requires citations with GC-12 provenance."""

    def test_rag_used_requires_citations_and_provenance(self):
        """used_rag=true requires citations present."""
        data = _load_fixture("gc13_fail_rag_used_citations_missing.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        errors = validate_rag_citations(artifacts)
        
        assert len(errors) == 1
        assert errors[0].category == "RAG_USED_CITATIONS_MISSING"

    def test_rag_not_used_no_citations_ok(self):
        """used_rag=false with no citations is ok."""
        data = _load_fixture("gc13_pass_used_rag_false_no_citations.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        errors = validate_rag_citations(artifacts)
        
        assert len(errors) == 0


class TestAllChecksMustBeExplicitlyReported:
    """Test all checks must be explicitly reported (closed registry)."""

    def test_all_checks_must_be_explicitly_reported(self):
        """All 5 check fields must be present."""
        data = _load_fixture("gc13_fail_omit_check_field.json")
        wire_checks = data["artifacts"]["checks"]
        
        errors = validate_checks_from_wire(wire_checks)
        
        categories = [e.category for e in errors]
        assert "CHECK_STATUS_MISSING" in categories

    def test_all_checks_present_passes(self):
        """All checks present passes validation."""
        data = _load_fixture("gc13_pass_genuine_final_report.json")
        wire_checks = data["artifacts"]["checks"]
        
        errors = validate_checks_from_wire(wire_checks)
        
        assert len(errors) == 0


class TestNotApplicableRequiresReason:
    """Test NOT_APPLICABLE requires non-empty reason."""

    def test_not_applicable_requires_reason(self):
        """NOT_APPLICABLE status requires reason."""
        with pytest.raises(ValueError, match="CHECK_NOT_APPLICABLE_MISSING_REASON"):
            CheckResult(status=CheckStatus.NOT_APPLICABLE)

    def test_not_applicable_with_reason_passes(self):
        """NOT_APPLICABLE with reason passes."""
        check = CheckResult(
            status=CheckStatus.NOT_APPLICABLE,
            reason="No units in this problem"
        )
        errors = validate_check_result("units_check", check)
        assert len(errors) == 0

    def test_not_applicable_with_empty_reason_fails(self):
        """NOT_APPLICABLE with empty reason fails."""
        with pytest.raises(ValueError, match="CHECK_NOT_APPLICABLE_MISSING_REASON"):
            CheckResult(status=CheckStatus.NOT_APPLICABLE, reason="")

    def test_not_applicable_with_whitespace_reason_fails(self):
        """NOT_APPLICABLE with whitespace-only reason fails."""
        with pytest.raises(ValueError, match="CHECK_NOT_APPLICABLE_MISSING_REASON"):
            CheckResult(status=CheckStatus.NOT_APPLICABLE, reason="   ")


class TestFinalRequiresDerivationForDerivationalTasks:
    """Test FINAL requires derivation for derivational tasks."""

    def test_final_requires_derivation_for_derivational_tasks(self):
        """Derivational task marked FINAL with no steps fails."""
        data = _load_fixture("gc13_fail_final_no_derivation_steps.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert "derivation" in computed_missing

    def test_derivational_task_with_steps_can_be_final(self):
        """Derivational task with steps can be FINAL."""
        data = _load_fixture("gc13_pass_genuine_final_report.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        
        assert computed_status == ReportStatus.FINAL

    def test_no_derivation_yet_is_incomplete(self):
        """'No derivation possible yet' is INCOMPLETE, not FINAL."""
        data = _load_fixture("gc13_pass_incomplete_no_derivation_yet.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert "derivation" in computed_missing


class TestCheckStatusEnum:
    """Test CheckStatus enum values."""

    def test_check_status_pass(self):
        """PASS status is valid."""
        check = CheckResult(status=CheckStatus.PASS)
        assert check.status == CheckStatus.PASS

    def test_check_status_fail(self):
        """FAIL status is valid."""
        check = CheckResult(status=CheckStatus.FAIL)
        assert check.status == CheckStatus.FAIL

    def test_check_status_indeterminate(self):
        """INDETERMINATE status is valid."""
        check = CheckResult(status=CheckStatus.INDETERMINATE)
        assert check.status == CheckStatus.INDETERMINATE

    def test_check_status_not_run(self):
        """NOT_RUN status is valid."""
        check = CheckResult(status=CheckStatus.NOT_RUN)
        assert check.status == CheckStatus.NOT_RUN


class TestReportChecksSchema:
    """Test ReportChecks schema validation."""

    def test_valid_report_checks(self):
        """Valid ReportChecks with all fields."""
        checks = ReportChecks(
            units_check=CheckResult(status=CheckStatus.PASS),
            limits_check=CheckResult(status=CheckStatus.PASS),
            numeric_check=CheckResult(status=CheckStatus.NOT_RUN),
            critic_check=CheckResult(status=CheckStatus.PASS),
            known_result_check=CheckResult(status=CheckStatus.PASS),
        )
        assert checks.units_check.status == CheckStatus.PASS

    def test_get_all_checks(self):
        """get_all_checks returns all checks."""
        checks = ReportChecks(
            units_check=CheckResult(status=CheckStatus.PASS),
            limits_check=CheckResult(status=CheckStatus.FAIL),
            numeric_check=CheckResult(status=CheckStatus.NOT_RUN),
            critic_check=CheckResult(status=CheckStatus.PASS),
            known_result_check=CheckResult(status=CheckStatus.PASS),
        )
        all_checks = checks.get_all_checks()
        assert len(all_checks) == 5
        assert "units_check" in all_checks
        assert "limits_check" in all_checks

    def test_has_any_failure(self):
        """has_any_failure detects FAIL status."""
        checks = ReportChecks(
            units_check=CheckResult(status=CheckStatus.PASS),
            limits_check=CheckResult(status=CheckStatus.FAIL),
            numeric_check=CheckResult(status=CheckStatus.NOT_RUN),
            critic_check=CheckResult(status=CheckStatus.PASS),
            known_result_check=CheckResult(status=CheckStatus.PASS),
        )
        assert checks.has_any_failure() is True


class TestCompletionGateIntegration:
    """Test validate_completion_gate integration."""

    def test_genuine_final_report(self):
        """Genuine FINAL report passes all validations."""
        data = _load_fixture("gc13_pass_genuine_final_report.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("expected_status"),
            wire_missing_artifacts=data.get("expected_missing_artifacts"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        # Filter out warnings
        hard_errors = [e for e in errors if not e.is_warning]
        
        assert computed_status == ReportStatus.FINAL
        assert computed_missing == []
        assert len(hard_errors) == 0

    def test_incomplete_with_missing_artifacts(self):
        """INCOMPLETE report with correct missing_artifacts passes."""
        data = _load_fixture("gc13_pass_incomplete_with_missing_artifacts.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("expected_status"),
            wire_missing_artifacts=data.get("expected_missing_artifacts"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        # Filter out warnings
        hard_errors = [e for e in errors if not e.is_warning]
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert len(computed_missing) > 0
        assert len(hard_errors) == 0

    def test_status_mismatch_fails(self):
        """Status mismatch produces error."""
        data = _load_fixture("gc13_fail_status_mismatch.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "REPORT_STATUS_MISMATCH" in categories


class TestPassFixtures:
    """Test all PASS fixtures validate successfully."""

    def test_fixture_pass_genuine_final_report(self):
        """PASS fixture: genuine FINAL report."""
        data = _load_fixture("gc13_pass_genuine_final_report.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.FINAL
        assert computed_missing == data["expected_missing_artifacts"]

    def test_fixture_pass_incomplete_with_missing_artifacts(self):
        """PASS fixture: INCOMPLETE with missing artifacts."""
        data = _load_fixture("gc13_pass_incomplete_with_missing_artifacts.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert sorted(computed_missing) == sorted(data["expected_missing_artifacts"])

    def test_fixture_pass_incomplete_no_derivation_yet(self):
        """PASS fixture: INCOMPLETE with no derivation yet."""
        data = _load_fixture("gc13_pass_incomplete_no_derivation_yet.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        computed_missing = compute_missing_artifacts(artifacts)
        
        assert computed_status == ReportStatus.INCOMPLETE
        assert "derivation" in computed_missing

    def test_fixture_pass_used_rag_false_no_citations(self):
        """PASS fixture: used_rag=false with no citations."""
        data = _load_fixture("gc13_pass_used_rag_false_no_citations.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status = compute_report_status(artifacts)
        
        assert computed_status == ReportStatus.FINAL


class TestFailFixtures:
    """Test all FAIL fixtures produce expected errors."""

    def test_fixture_fail_final_missing_coverage(self):
        """FAIL fixture: FINAL missing coverage."""
        data = _load_fixture("gc13_fail_final_missing_coverage.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "REPORT_STATUS_MISMATCH" in categories

    def test_fixture_fail_final_missing_evidence(self):
        """FAIL fixture: FINAL missing evidence."""
        data = _load_fixture("gc13_fail_final_missing_evidence.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "REPORT_STATUS_MISMATCH" in categories

    def test_fixture_fail_final_missing_assumption_ledger(self):
        """FAIL fixture: FINAL missing assumption_ledger."""
        data = _load_fixture("gc13_fail_final_missing_assumption_ledger.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "REPORT_STATUS_MISMATCH" in categories

    def test_fixture_fail_incomplete_empty_missing_artifacts(self):
        """FAIL fixture: INCOMPLETE with empty missing_artifacts."""
        data = _load_fixture("gc13_fail_incomplete_empty_missing_artifacts.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_missing_artifacts=data.get("wire_missing_artifacts"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "MISSING_ARTIFACTS_MISMATCH" in categories

    def test_fixture_fail_status_mismatch(self):
        """FAIL fixture: status mismatch."""
        data = _load_fixture("gc13_fail_status_mismatch.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "REPORT_STATUS_MISMATCH" in categories

    def test_fixture_fail_missing_artifacts_mismatch(self):
        """FAIL fixture: missing_artifacts mismatch."""
        data = _load_fixture("gc13_fail_missing_artifacts_mismatch.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_missing_artifacts=data.get("wire_missing_artifacts"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "MISSING_ARTIFACTS_MISMATCH" in categories

    def test_fixture_fail_rag_used_citations_missing(self):
        """FAIL fixture: RAG used but citations missing."""
        data = _load_fixture("gc13_fail_rag_used_citations_missing.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "RAG_USED_CITATIONS_MISSING" in categories

    def test_fixture_fail_omit_check_field(self):
        """FAIL fixture: omit check field."""
        data = _load_fixture("gc13_fail_omit_check_field.json")
        
        errors = validate_checks_from_wire(data["artifacts"]["checks"])
        
        categories = [e.category for e in errors]
        assert "CHECK_STATUS_MISSING" in categories

    def test_fixture_fail_final_no_derivation_steps(self):
        """FAIL fixture: FINAL with no derivation steps."""
        data = _load_fixture("gc13_fail_final_no_derivation_steps.json")
        artifacts = _build_artifacts_from_fixture(data)
        
        computed_status, computed_missing, errors = validate_completion_gate(
            artifacts,
            wire_status=data.get("wire_status"),
            wire_checks=data["artifacts"]["checks"],
        )
        
        categories = [e.category for e in errors]
        assert "REPORT_STATUS_MISMATCH" in categories
        assert "derivation" in computed_missing
