"""
GC-7 Coverage Metrics Tests

Comprehensive tests for step status validation and coverage bookkeeping.
Tests computation, validation, error categories, and fixtures.
"""

import pytest
import json
from pathlib import Path
from src.core.step import DerivationStep, StepStatus
from src.core.claim import Claim, ClaimLabel
from src.core.evidence import EvidenceObject, EvidenceType, EvidenceStatus, EvidenceSource, PayloadRef
from src.core.report import ScientificReport
from src.core.coverage_metrics import (
    CoverageMetrics, UncheckedStepItem, FailedStepItem,
    compute_coverage_metrics
)
from src.core.gc7_wire_parsers import parse_step_status, parse_status_reason
from src.core.gc7_validators import (
    GC7ValidationError, validate_step_object,
    validate_coverage_metrics_match, validate_and_compute_coverage_metrics
)


class TestStepStatusEnum:
    """Test StepStatus enum has exactly 4 values with lowercase wire format."""
    
    def test_step_status_enum_only_allows_four_values(self):
        """StepStatus enum must have exactly 4 members: unchecked, checked, failed, indeterminate."""
        assert len(StepStatus) == 4
        assert StepStatus.UNCHECKED.value == "unchecked"
        assert StepStatus.CHECKED.value == "checked"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.INDETERMINATE.value == "indeterminate"
    
    def test_parse_step_status_accepts_exact_tokens_only(self):
        """parse_step_status accepts only exact lowercase tokens."""
        assert parse_step_status("unchecked") == StepStatus.UNCHECKED
        assert parse_step_status("checked") == StepStatus.CHECKED
        assert parse_step_status("failed") == StepStatus.FAILED
        assert parse_step_status("indeterminate") == StepStatus.INDETERMINATE
    
    def test_parse_step_status_rejects_case_variants(self):
        """parse_step_status rejects case variants (e.g., CHECKED, Checked)."""
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("CHECKED")
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("Checked")
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("UNCHECKED")
    
    def test_parse_step_status_rejects_whitespace_variants(self):
        """parse_step_status rejects whitespace variants (no trimming)."""
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status(" checked")
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("checked ")
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("\tchecked\n")
    
    def test_parse_step_status_rejects_invalid_tokens(self):
        """parse_step_status rejects invalid tokens (e.g., 'done', 'complete')."""
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("done")
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("complete")
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status("pending")


class TestStatusReasonValidation:
    """Test status_reason validation rules."""
    
    def test_indeterminate_requires_reason_non_empty(self):
        """step_status=indeterminate requires non-empty status_reason."""
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.INDETERMINATE,
                status_reason=None
            )
        
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.INDETERMINATE,
                status_reason=""
            )
        
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.INDETERMINATE,
                status_reason="   "
            )
    
    def test_failed_status_reason_allowed(self):
        """Failed steps MAY include status_reason (optional)."""
        # Should NOT raise - failed steps can have status_reason
        step = DerivationStep(
            step_id="step-001",
            claim_ids=["claim-001"],
            step_status=StepStatus.FAILED,
            status_reason="Verification failed due to missing data"
        )
        assert step.status_reason == "Verification failed due to missing data"
        
        # Also OK without status_reason
        step_no_reason = DerivationStep(
            step_id="step-002",
            claim_ids=["claim-001"],
            step_status=StepStatus.FAILED,
            status_reason=None
        )
        assert step_no_reason.status_reason is None
    
    def test_checked_status_reason_rejected(self):
        """Checked steps cannot have status_reason (fail-closed)."""
        with pytest.raises(ValueError, match="STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.CHECKED,
                status_reason="Should not be present"
            )
    
    def test_unchecked_status_reason_rejected(self):
        """Unchecked steps cannot have status_reason (fail-closed)."""
        with pytest.raises(ValueError, match="STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.UNCHECKED,
                status_reason="Should not be present"
            )
    
    def test_parse_status_reason_rejects_whitespace_only(self):
        """parse_status_reason rejects whitespace-only strings."""
        with pytest.raises(ValueError, match="INDETERMINATE_REASON_EMPTY"):
            parse_status_reason("   ", required=True)
        
        with pytest.raises(ValueError, match="INDETERMINATE_REASON_EMPTY"):
            parse_status_reason("\t\n", required=True)


class TestCoverageComputation:
    """Test coverage metrics computation from step statuses."""
    
    def test_coverage_computed_from_step_statuses(self):
        """Coverage metrics computed from step_status only (single source of truth)."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
            DerivationStep(step_id="step-002", claim_ids=["c2"], step_status=StepStatus.UNCHECKED),
            DerivationStep(step_id="step-003", claim_ids=["c3"], step_status=StepStatus.INDETERMINATE, status_reason="Needs data"),
            DerivationStep(step_id="step-004", claim_ids=["c4"], step_status=StepStatus.FAILED),
        ]
        
        metrics = compute_coverage_metrics(steps)
        
        assert metrics.checked_steps == ["step-001"]
        assert len(metrics.unchecked_steps) == 2
        assert metrics.unchecked_steps[0].step_id == "step-002"
        assert metrics.unchecked_steps[0].kind == "unchecked"
        assert metrics.unchecked_steps[1].step_id == "step-003"
        assert metrics.unchecked_steps[1].kind == "indeterminate"
        assert metrics.unchecked_steps[1].reason == "Needs data"
        assert len(metrics.failed_steps) == 1
        assert metrics.failed_steps[0].step_id == "step-004"
        
        assert metrics.checked_count == 1
        assert metrics.unchecked_count == 2
        assert metrics.failed_count == 1
        assert metrics.total_steps == 4
    
    def test_indeterminate_counts_as_unchecked_for_progress_ratio(self):
        """indeterminate counts as unchecked for verification_progress_ratio."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
            DerivationStep(step_id="step-002", claim_ids=["c2"], step_status=StepStatus.UNCHECKED),
            DerivationStep(step_id="step-003", claim_ids=["c3"], step_status=StepStatus.INDETERMINATE, status_reason="Needs data"),
        ]
        
        metrics = compute_coverage_metrics(steps)
        
        # verification_progress_ratio = checked / (checked + unchecked)
        # = 1 / (1 + 2) = 0.333...
        assert metrics.verification_progress_ratio == pytest.approx(1/3)
        assert metrics.unchecked_count == 2  # unchecked + indeterminate
    
    def test_verified_work_pct_uses_total_steps_denominator(self):
        """verified_work_pct = checked / total_steps (different from progress ratio)."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
            DerivationStep(step_id="step-002", claim_ids=["c2"], step_status=StepStatus.UNCHECKED),
            DerivationStep(step_id="step-003", claim_ids=["c3"], step_status=StepStatus.FAILED),
        ]
        
        metrics = compute_coverage_metrics(steps)
        
        # verified_work_pct = checked / total_steps = 1 / 3
        assert metrics.verified_work_pct == pytest.approx(1/3)
        
        # verification_progress_ratio = checked / (checked + unchecked) = 1 / (1 + 1) = 0.5
        assert metrics.verification_progress_ratio == pytest.approx(0.5)
    
    def test_zero_step_coverage_is_zero_with_note(self):
        """Zero-step edge case: all counts 0, ratios 0.0, coverage_note REQUIRED."""
        steps = []
        
        metrics = compute_coverage_metrics(steps)
        
        assert metrics.checked_count == 0
        assert metrics.unchecked_count == 0
        assert metrics.failed_count == 0
        assert metrics.total_steps == 0
        assert metrics.verification_progress_ratio == 0.0
        assert metrics.verified_work_pct == 0.0
        assert metrics.coverage_note is not None
        assert "No derivation steps present" in metrics.coverage_note
    
    def test_coverage_buckets_sorted_deterministically(self):
        """Coverage buckets are sorted lexicographically for determinism."""
        steps = [
            DerivationStep(step_id="step-003", claim_ids=["c3"], step_status=StepStatus.CHECKED),
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
            DerivationStep(step_id="step-002", claim_ids=["c2"], step_status=StepStatus.CHECKED),
        ]
        
        metrics = compute_coverage_metrics(steps)
        
        # checked_steps should be sorted
        assert metrics.checked_steps == ["step-001", "step-002", "step-003"]
    
    def test_all_failed_steps_gives_zero_progress_ratio(self):
        """All failed steps: verification_progress_ratio = 0.0 (denom = 0)."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.FAILED),
            DerivationStep(step_id="step-002", claim_ids=["c2"], step_status=StepStatus.FAILED),
        ]
        
        metrics = compute_coverage_metrics(steps)
        
        assert metrics.checked_count == 0
        assert metrics.unchecked_count == 0
        assert metrics.failed_count == 2
        assert metrics.verification_progress_ratio == 0.0  # denom = 0 + 0 = 0
        assert metrics.verified_work_pct == 0.0  # 0 / 2


class TestCoverageMetricsMismatch:
    """Test computed-only enforcement: wire-provided coverage must match recomputation."""
    
    def test_coverage_metrics_mismatch_fails(self):
        """Wire-provided coverage metrics trigger FAIL on any mismatch."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
        ]
        
        # Wire provides wrong checked_count
        wire_coverage = {
            "checked_steps": ["step-001"],
            "unchecked_steps": [],
            "failed_steps": [],
            "checked_count": 999,  # MISMATCH
            "unchecked_count": 0,
            "failed_count": 0,
            "total_steps": 1,
            "verification_progress_ratio": 1.0,
            "verified_work_pct": 1.0,
        }
        
        is_valid, errors = validate_coverage_metrics_match(steps, wire_coverage)
        
        assert not is_valid
        assert any("COVERAGE_COUNT_MISMATCH" in err for err in errors)
    
    def test_coverage_rejects_nan_inf(self):
        """Wire-provided coverage metrics reject NaN/Infinity."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
        ]
        
        import math
        wire_coverage = {
            "checked_steps": ["step-001"],
            "unchecked_steps": [],
            "failed_steps": [],
            "checked_count": 1,
            "unchecked_count": 0,
            "failed_count": 0,
            "total_steps": 1,
            "verification_progress_ratio": math.nan,  # NaN
            "verified_work_pct": 1.0,
        }
        
        is_valid, errors = validate_coverage_metrics_match(steps, wire_coverage)
        
        assert not is_valid
        assert any("COVERAGE_INVALID_NUMBER" in err for err in errors)
    
    def test_partition_consistency_enforced(self):
        """Partition consistency: all steps accounted for, no overlaps, no duplicates."""
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
            DerivationStep(step_id="step-002", claim_ids=["c2"], step_status=StepStatus.UNCHECKED),
        ]
        
        # Wire omits step-002 (partition incomplete)
        wire_coverage = {
            "checked_steps": ["step-001"],
            "unchecked_steps": [],  # Missing step-002
            "failed_steps": [],
            "checked_count": 1,
            "unchecked_count": 0,
            "failed_count": 0,
            "total_steps": 2,
            "verification_progress_ratio": 1.0,
            "verified_work_pct": 0.5,
        }
        
        is_valid, errors = validate_coverage_metrics_match(steps, wire_coverage)
        
        assert not is_valid
        assert any("COVERAGE_PARTITION_MISMATCH" in err for err in errors)


class TestGC7Fixtures:
    """Test GC-7 fixtures (PASS and FAIL)."""
    
    def test_fixture_pass_mixed_status(self):
        """PASS fixture: mixed-status derivation with all 4 step statuses."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_pass_mixed_status.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # Parse steps
        steps = []
        for s in data["steps"]:
            step_status = parse_step_status(s["step_status"])
            status_reason = s.get("status_reason")
            steps.append(DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=step_status,
                status_reason=status_reason,
            ))
        
        # Compute coverage
        metrics = compute_coverage_metrics(steps)
        
        # Verify expected values from fixture metadata
        expected = data["_test_metadata"]["expected_coverage"]
        assert metrics.checked_count == expected["checked_count"]
        assert metrics.unchecked_count == expected["unchecked_count"]
        assert metrics.failed_count == expected["failed_count"]
        assert metrics.total_steps == expected["total_steps"]
        assert metrics.verification_progress_ratio == pytest.approx(expected["verification_progress_ratio"])
        assert metrics.verified_work_pct == pytest.approx(expected["verified_work_pct"])
    
    def test_fixture_pass_zero_steps(self):
        """PASS fixture: zero-step edge case with coverage_note."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_pass_zero_steps.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = []
        metrics = compute_coverage_metrics(steps)
        
        expected = data["_test_metadata"]["expected_coverage"]
        assert metrics.total_steps == 0
        assert metrics.checked_count == 0
        assert metrics.unchecked_count == 0
        assert metrics.failed_count == 0
        assert metrics.verification_progress_ratio == 0.0
        assert metrics.verified_work_pct == 0.0
        assert metrics.coverage_note is not None
    
    def test_fixture_pass_all_checked(self):
        """PASS fixture: all steps checked - progress ratio and verified work % both 1.0."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_pass_all_checked.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = []
        for s in data["steps"]:
            step_status = parse_step_status(s["step_status"])
            steps.append(DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=step_status,
            ))
        
        metrics = compute_coverage_metrics(steps)
        
        assert metrics.verification_progress_ratio == 1.0
        assert metrics.verified_work_pct == 1.0
        assert metrics.checked_count == metrics.total_steps
    
    def test_fixture_fail_invalid_step_status(self):
        """FAIL fixture: invalid step_status token."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_invalid_step_status.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="STEP_STATUS_INVALID"):
            parse_step_status(data["steps"][0]["step_status"])
    
    def test_fixture_fail_indeterminate_missing_reason(self):
        """FAIL fixture: indeterminate without status_reason."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_indeterminate_missing_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                step_status=StepStatus.INDETERMINATE,
                status_reason=step_data.get("status_reason"),
            )
    
    def test_fixture_fail_indeterminate_whitespace_reason(self):
        """FAIL fixture: indeterminate with whitespace-only status_reason."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_indeterminate_whitespace_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                step_status=StepStatus.INDETERMINATE,
                status_reason=step_data.get("status_reason"),
            )
    
    def test_fixture_fail_status_reason_when_not_indeterminate(self):
        """FAIL fixture: status_reason present for checked status (not allowed)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_status_reason_when_not_indeterminate.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                step_status=StepStatus.CHECKED,
                status_reason=step_data.get("status_reason"),
            )
    
    def test_fixture_fail_unchecked_with_reason(self):
        """FAIL fixture: status_reason present for unchecked status (not allowed)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_unchecked_with_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                step_status=StepStatus.UNCHECKED,
                status_reason=step_data.get("status_reason"),
            )
    
    def test_fixture_pass_failed_with_reason(self):
        """PASS fixture: failed step with status_reason (allowed)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_pass_failed_with_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        # Should NOT raise - failed steps can have status_reason
        step = DerivationStep(
            step_id=step_data["step_id"],
            claim_ids=step_data["claim_ids"],
            step_status=StepStatus.FAILED,
            status_reason=step_data.get("status_reason"),
        )
        assert step.status_reason == "Verification failed due to missing data"
    
    def test_fixture_fail_coverage_count_mismatch(self):
        """FAIL fixture: wire-provided count mismatches computed."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_count_mismatch.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = [
            DerivationStep(
                step_id=data["steps"][0]["step_id"],
                claim_ids=data["steps"][0]["claim_ids"],
                step_status=StepStatus.CHECKED,
            )
        ]
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_COUNT_MISMATCH" in err for err in errors)
    
    def test_fixture_fail_coverage_ratio_mismatch(self):
        """FAIL fixture: wire-provided ratio mismatches computed."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_ratio_mismatch.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = [
            DerivationStep(
                step_id=data["steps"][0]["step_id"],
                claim_ids=data["steps"][0]["claim_ids"],
                step_status=StepStatus.CHECKED,
            )
        ]
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_RATIO_MISMATCH" in err for err in errors)
    
    def test_fixture_fail_coverage_wrong_type(self):
        """FAIL fixture: coverage field has wrong type."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_wrong_type.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = [
            DerivationStep(
                step_id=data["steps"][0]["step_id"],
                claim_ids=data["steps"][0]["claim_ids"],
                step_status=StepStatus.CHECKED,
            )
        ]
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_WRONG_TYPE" in err for err in errors)
    
    def test_fixture_fail_coverage_ghost_step_id(self):
        """FAIL fixture: bucket contains ghost step_id not in report.steps."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_ghost_step_id.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = [
            DerivationStep(
                step_id=data["steps"][0]["step_id"],
                claim_ids=data["steps"][0]["claim_ids"],
                step_status=StepStatus.CHECKED,
            )
        ]
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_BUCKET_GHOST_STEP_ID" in err for err in errors)
    
    def test_fixture_fail_coverage_duplicate_step_id(self):
        """FAIL fixture: bucket contains duplicate step_id."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_duplicate_step_id.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = [
            DerivationStep(
                step_id=data["steps"][0]["step_id"],
                claim_ids=data["steps"][0]["claim_ids"],
                step_status=StepStatus.CHECKED,
            )
        ]
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_BUCKET_DUPLICATE_STEP_ID" in err for err in errors)
    
    def test_fixture_fail_coverage_partition_mismatch(self):
        """FAIL fixture: partition incomplete (step missing from buckets)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_partition_mismatch.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=parse_step_status(s["step_status"]),
            )
            for s in data["steps"]
        ]
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_PARTITION_MISMATCH" in err for err in errors)
    
    def test_fixture_fail_coverage_note_missing_zero_steps(self):
        """FAIL fixture: total_steps == 0 but coverage_note missing."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc7_fail_coverage_note_missing_zero_steps.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        steps = []
        
        is_valid, errors = validate_coverage_metrics_match(steps, data["coverage_metrics"])
        
        assert not is_valid
        assert any("COVERAGE_NOTE_MISSING_ZERO_STEPS" in err for err in errors)


class TestValidationOrder:
    """Test GC-7 validation order and integration."""
    
    def test_validation_order_parse_compute_validate(self):
        """Validation order: 1) Parse steps, 2) Compute coverage, 3) Validate wire coverage."""
        # This test verifies the validation flow works correctly
        steps = [
            DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
        ]
        
        # No wire coverage provided - should compute and return
        computed, errors = validate_and_compute_coverage_metrics(steps, wire_coverage=None)
        
        assert len(errors) == 0
        assert computed.checked_count == 1
        assert computed.total_steps == 1
    
    def test_validation_order_gc3_before_gc7(self):
        """GC-3 validation must run before GC-7 (structural validation before coverage)."""
        # GC-7 depends on structurally valid steps (unique step_ids, valid claim_ids)
        # Running GC-7 first can produce noisy/misleading coverage errors
        
        # Test: GC-3 catches duplicate step_ids before GC-7 runs
        from src.core.report import ScientificReport
        
        # This should fail GC-3 validation (duplicate step_ids)
        with pytest.raises(ValueError, match="Duplicate step_ids"):
            report = ScientificReport(
                claims=[
                    Claim(claim_id="c1", statement="Test", claim_label=ClaimLabel.SPECULATIVE)
                ],
                steps=[
                    DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.CHECKED),
                    DerivationStep(step_id="step-001", claim_ids=["c1"], step_status=StepStatus.UNCHECKED),  # Duplicate
                ],
                evidence=[]
            )
        
        # GC-3 should catch this before GC-7 coverage computation runs
        # This ensures clean error messages (structural errors first, then coverage errors)
    
    def test_finalization_blocked_on_gc7_errors(self):
        """FINAL must be blocked if any GC-7 validation error exists."""
        # This is a policy test - GC-7 errors should prevent finalization
        # Implementation will be in report validation integration
        pass  # Placeholder for finalization integration test
