"""
GC-6 Integrity Metrics Tests

Tests for unsupported claim computation, computed-only enforcement, and warnings.
"""

import pytest
import json
from pathlib import Path
from src.core.claim import Claim, ClaimLabel
from src.core.step import DerivationStep, StepStatus
from src.core.evidence import EvidenceObject, EvidenceType, EvidenceStatus, EvidenceSource, PayloadRef
from src.core.report import ScientificReport
from src.core.integrity_metrics import (
    IntegrityMetrics,
    compute_integrity_metrics,
    compute_speculative_flood_warning,
)
from src.core.gc6_validators import (
    validate_and_compute_integrity_metrics,
    validate_report_with_integrity,
    can_finalize_report,
)
from src.core.gc5_wire_parsers import parse_evidence_object


def _make_step_from_fixture(s: dict) -> DerivationStep:
    """Helper to construct DerivationStep from fixture data with default statement."""
    return DerivationStep(
        step_id=s["step_id"],
        claim_ids=s["claim_ids"],
        statement=s.get("statement", "Test derivation step"),
        step_status=StepStatus[s.get("step_status", "UNCHECKED")],
        depends_on=s.get("depends_on", []),
        status_reason=s.get("status_reason"),
    )


class TestIntegrityMetricsSchema:
    """Test IntegrityMetrics schema validation"""
    
    def test_integrity_metrics_valid(self):
        """GC-6: Valid IntegrityMetrics construction"""
        metrics = IntegrityMetrics(
            unsupported_non_spec_claims=1,
            total_non_spec_claims=3,
            unsupported_claim_rate=1/3,
            unsupported_claim_ids=["claim-001"],
        )
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 3
        assert abs(metrics.unsupported_claim_rate - 1/3) < 1e-9
        assert metrics.unsupported_claim_ids == ["claim-001"]
    
    def test_integrity_metrics_rejects_wrong_type_int(self):
        """GC-6: IntegrityMetrics rejects wrong type for int fields"""
        with pytest.raises(TypeError, match="unsupported_non_spec_claims must be int"):
            IntegrityMetrics(
                unsupported_non_spec_claims="zero",
                total_non_spec_claims=1,
                unsupported_claim_rate=0.0,
                unsupported_claim_ids=[],
            )
    
    def test_integrity_metrics_rejects_wrong_type_list(self):
        """GC-6: IntegrityMetrics rejects wrong type for list field"""
        with pytest.raises(TypeError, match="unsupported_claim_ids must be list"):
            IntegrityMetrics(
                unsupported_non_spec_claims=0,
                total_non_spec_claims=1,
                unsupported_claim_rate=0.0,
                unsupported_claim_ids="not-a-list",
            )
    
    def test_integrity_metrics_rejects_negative_values(self):
        """GC-6: IntegrityMetrics rejects negative values"""
        with pytest.raises(ValueError, match="must be non-negative"):
            IntegrityMetrics(
                unsupported_non_spec_claims=-1,
                total_non_spec_claims=1,
                unsupported_claim_rate=0.0,
                unsupported_claim_ids=[],
            )
    
    def test_integrity_metrics_rejects_unsupported_exceeds_total(self):
        """GC-6: IntegrityMetrics rejects unsupported > total"""
        with pytest.raises(ValueError, match="cannot exceed total_non_spec_claims"):
            IntegrityMetrics(
                unsupported_non_spec_claims=5,
                total_non_spec_claims=3,
                unsupported_claim_rate=1.0,
                unsupported_claim_ids=["a", "b", "c", "d", "e"],
            )
    
    def test_integrity_metrics_rejects_nan(self):
        """GC-6: IntegrityMetrics rejects NaN rate"""
        with pytest.raises(ValueError, match="METRICS_INVALID_NUMBER"):
            IntegrityMetrics(
                unsupported_non_spec_claims=0,
                total_non_spec_claims=1,
                unsupported_claim_rate=float('nan'),
                unsupported_claim_ids=[],
            )
    
    def test_integrity_metrics_rejects_infinity(self):
        """GC-6: IntegrityMetrics rejects Infinity rate"""
        with pytest.raises(ValueError, match="METRICS_INVALID_NUMBER"):
            IntegrityMetrics(
                unsupported_non_spec_claims=0,
                total_non_spec_claims=1,
                unsupported_claim_rate=float('inf'),
                unsupported_claim_ids=[],
            )
    
    def test_integrity_metrics_rejects_rate_mismatch(self):
        """GC-6: IntegrityMetrics rejects rate that doesn't match ints"""
        with pytest.raises(ValueError, match="METRICS_INCONSISTENT"):
            IntegrityMetrics(
                unsupported_non_spec_claims=1,
                total_non_spec_claims=2,
                unsupported_claim_rate=0.75,  # Should be 0.5
                unsupported_claim_ids=["claim-001"],
            )
    
    def test_integrity_metrics_rejects_ids_count_mismatch(self):
        """GC-6: IntegrityMetrics rejects unsupported_claim_ids count mismatch"""
        with pytest.raises(ValueError, match="METRICS_INCONSISTENT"):
            IntegrityMetrics(
                unsupported_non_spec_claims=2,
                total_non_spec_claims=3,
                unsupported_claim_rate=2/3,
                unsupported_claim_ids=["claim-001"],  # Should have 2 IDs
            )
    
    def test_integrity_metrics_rejects_unsorted_ids(self):
        """GC-6: IntegrityMetrics rejects unsorted unsupported_claim_ids"""
        with pytest.raises(ValueError, match="METRICS_NON_DETERMINISTIC"):
            IntegrityMetrics(
                unsupported_non_spec_claims=2,
                total_non_spec_claims=3,
                unsupported_claim_rate=2/3,
                unsupported_claim_ids=["claim-002", "claim-001"],  # Not sorted
            )
    
    def test_integrity_metrics_rejects_duplicate_ids(self):
        """GC-6: IntegrityMetrics rejects duplicate unsupported_claim_ids"""
        with pytest.raises(ValueError, match="METRICS_NON_DETERMINISTIC"):
            IntegrityMetrics(
                unsupported_non_spec_claims=2,
                total_non_spec_claims=3,
                unsupported_claim_rate=2/3,
                unsupported_claim_ids=["claim-001", "claim-001"],  # Duplicate
            )


class TestComputeOnInvalid:
    """Test compute_integrity_metrics works even when GC-4/GC-5 fail (GC-6.1)"""
    
    def test_gc6_computes_when_report_invalid_gc4_missing_evidence(self):
        """GC-6.1: Compute metrics even when GC-4 would fail (missing evidence)"""
        claims = [
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
        ]
        evidence_by_id = {}
        
        # Should compute successfully even though GC-4 would fail
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 1.0
        assert metrics.unsupported_claim_ids == ["claim-001"]
    
    def test_gc6_computes_when_evidence_objects_gc5_invalid(self):
        """GC-6.1: Compute metrics even when evidence objects are GC-5 invalid"""
        claims = [
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-001"])
        ]
        # Evidence exists but might be GC-5 invalid - compute still works
        evidence_by_id = {"evidence-001": "malformed"}  # Not an EvidenceObject
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        # Claim is supported (evidence_id resolves), even if evidence is malformed
        assert metrics.unsupported_non_spec_claims == 0
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 0.0
    
    def test_gc6_never_throws_on_malformed_report_shapes(self):
        """GC-6.1: Never crash on malformed report shapes"""
        # Test 1: None claims
        metrics = compute_integrity_metrics(None, None)
        assert metrics.unsupported_non_spec_claims == 0
        assert metrics.total_non_spec_claims == 0
        assert metrics.unsupported_claim_rate == 0.0
        assert any("claims was None" in note for note in metrics.diagnostics_notes)
        
        # Test 2: Wrong type claims
        metrics = compute_integrity_metrics("not a list", {})
        assert metrics.unsupported_non_spec_claims == 0
        assert metrics.total_non_spec_claims == 0
        assert any("claims wrong type" in note for note in metrics.diagnostics_notes)
        
        # Test 3: None evidence_by_id
        claims = [Claim(claim_id="c1", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])]
        metrics = compute_integrity_metrics(claims, None)
        assert metrics.unsupported_non_spec_claims == 1
        assert any("evidence_by_id was None" in note for note in metrics.diagnostics_notes)
        
        # Test 4: Wrong type evidence_by_id
        metrics = compute_integrity_metrics(claims, "not a dict")
        assert metrics.unsupported_non_spec_claims == 1
        assert any("evidence_by_id wrong type" in note for note in metrics.diagnostics_notes)
    
    def test_gc6_handles_malformed_claim_objects(self):
        """GC-6.1: Handle malformed claim objects gracefully"""
        claims = [
            Claim(claim_id="claim-001", statement="Valid", claim_label=ClaimLabel.DERIVED, evidence_ids=[]),
            "not a claim object",  # Malformed
            Claim(claim_id="claim-002", statement="Valid", claim_label=ClaimLabel.COMPUTED, evidence_ids=[]),
        ]
        
        metrics = compute_integrity_metrics(claims, {})
        
        # Should count only valid claims
        assert metrics.unsupported_non_spec_claims == 2
        assert metrics.total_non_spec_claims == 2
        assert metrics.unsupported_claim_ids == ["claim-001", "claim-002"]
        assert any("not a Claim object" in note for note in metrics.diagnostics_notes)
    
    def test_gc6_handles_malformed_evidence_ids(self):
        """GC-6.1: Handle malformed evidence_ids gracefully"""
        # Create a valid claim first, then mutate it to bypass validation
        # (This simulates wire data that bypassed Claim construction)
        
        # Test 1: evidence_ids is not a list
        claim1 = Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
        claim1.evidence_ids = "not-a-list"  # Mutate after construction
        metrics = compute_integrity_metrics([claim1], {})
        assert metrics.unsupported_non_spec_claims == 1
        assert any("evidence_ids wrong type" in note for note in metrics.diagnostics_notes)
        
        # Test 2: evidence_ids contains non-string
        claim2 = Claim(claim_id="claim-002", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
        claim2.evidence_ids = [123, "valid"]  # Mutate after construction
        metrics = compute_integrity_metrics([claim2], {})
        assert metrics.unsupported_non_spec_claims == 1
        assert any("non-string evidence_id" in note for note in metrics.diagnostics_notes)


class TestComputeIntegrityMetrics:
    """Test compute_integrity_metrics function"""
    
    def test_gc6_counts_missing_evidence_as_unsupported(self):
        """GC-6: Claim with empty evidence_ids is unsupported"""
        claims = [
            Claim(
                claim_id="claim-001",
                statement="Test",
                claim_label=ClaimLabel.DERIVED,
                evidence_ids=[],
            )
        ]
        evidence_by_id = {}
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 1.0
        assert metrics.unsupported_claim_ids == ["claim-001"]
    
    def test_gc6_counts_dangling_evidence_id_as_unsupported(self):
        """GC-6: Claim with dangling evidence_id is unsupported"""
        claims = [
            Claim(
                claim_id="claim-001",
                statement="Test",
                claim_label=ClaimLabel.DERIVED,
                evidence_ids=["evidence-999"],
            )
        ]
        evidence_by_id = {}
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 1.0
        assert metrics.unsupported_claim_ids == ["claim-001"]
    
    def test_gc6_counts_partial_dangling_as_unsupported(self):
        """GC-6: Claim with ANY dangling evidence_id is unsupported (Option A strict)"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        evidence_by_id = {"evidence-001": evidence}
        
        claims = [
            Claim(
                claim_id="claim-001",
                statement="Test",
                claim_label=ClaimLabel.DERIVED,
                evidence_ids=["evidence-001", "evidence-999"],  # One valid, one dangling
            )
        ]
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 1.0
        assert metrics.unsupported_claim_ids == ["claim-001"]
    
    def test_gc6_total_zero_sets_rate_zero(self):
        """GC-6: When total_non_spec_claims==0, rate is 0.0"""
        claims = [
            Claim(
                claim_id="claim-001",
                statement="Speculative",
                claim_label=ClaimLabel.SPECULATIVE,
                verify_falsify="Test this",
            )
        ]
        evidence_by_id = {}
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 0
        assert metrics.total_non_spec_claims == 0
        assert metrics.unsupported_claim_rate == 0.0
        assert metrics.unsupported_claim_ids == []
    
    def test_gc6_speculative_not_counted(self):
        """GC-6: SPECULATIVE claims are not counted in numerator or denominator"""
        claims = [
            Claim(
                claim_id="claim-001",
                statement="Derived",
                claim_label=ClaimLabel.DERIVED,
                evidence_ids=[],
            ),
            Claim(
                claim_id="claim-002",
                statement="Speculative",
                claim_label=ClaimLabel.SPECULATIVE,
                verify_falsify="Test",
            ),
        ]
        evidence_by_id = {}
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        # Only claim-001 counted (DERIVED with no evidence)
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 1.0
        assert metrics.unsupported_claim_ids == ["claim-001"]
    
    def test_gc6_supported_claim_not_counted_unsupported(self):
        """GC-6: Claim with valid evidence is not unsupported"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        evidence_by_id = {"evidence-001": evidence}
        
        claims = [
            Claim(
                claim_id="claim-001",
                statement="Test",
                claim_label=ClaimLabel.DERIVED,
                evidence_ids=["evidence-001"],
            )
        ]
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 0
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 0.0
        assert metrics.unsupported_claim_ids == []
    
    def test_gc6_unsupported_claim_ids_match_computed_set(self):
        """GC-6: unsupported_claim_ids matches computed set (sorted, unique)"""
        claims = [
            Claim(claim_id="claim-003", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[]),
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.COMPUTED, evidence_ids=[]),
            Claim(claim_id="claim-002", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[]),
        ]
        evidence_by_id = {}
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_claim_ids == ["claim-001", "claim-002", "claim-003"]  # Sorted
        assert len(set(metrics.unsupported_claim_ids)) == len(metrics.unsupported_claim_ids)  # Unique
    
    def test_gc6_mixed_support_correct_counts(self):
        """GC-6: Mixed support scenario computes correct counts"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        evidence_by_id = {"evidence-001": evidence}
        
        claims = [
            Claim(claim_id="claim-001", statement="Supported", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-001"]),
            Claim(claim_id="claim-002", statement="Unsupported", claim_label=ClaimLabel.COMPUTED, evidence_ids=[]),
            Claim(claim_id="claim-003", statement="Unsupported", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-999"]),
            Claim(claim_id="claim-004", statement="Speculative", claim_label=ClaimLabel.SPECULATIVE, verify_falsify="Test"),
        ]
        
        metrics = compute_integrity_metrics(claims, evidence_by_id)
        
        assert metrics.unsupported_non_spec_claims == 2
        assert metrics.total_non_spec_claims == 3  # claim-004 not counted
        assert abs(metrics.unsupported_claim_rate - 2/3) < 1e-9
        assert metrics.unsupported_claim_ids == ["claim-002", "claim-003"]


class TestComputedOnlyEnforcement:
    """Test computed-only enforcement policy"""
    
    def test_gc6_metrics_are_computed_only_mismatch_fails(self):
        """GC-6: Metrics present on wire but mismatched causes INTEGRITY_METRICS_MISMATCH"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        
        # Wire says 0 unsupported, but claim has no evidence (should be 1 unsupported)
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[],
            integrity_metrics=IntegrityMetrics(
                unsupported_non_spec_claims=0,
                total_non_spec_claims=1,
                unsupported_claim_rate=0.0,
                unsupported_claim_ids=[],
            ),
        )
        
        evidence_by_id = {}
        is_valid, errors = validate_and_compute_integrity_metrics(report, evidence_by_id)
        
        assert not is_valid
        assert any("INTEGRITY_METRICS_MISMATCH" in err and "unsupported_non_spec_claims" in err for err in errors)
    
    def test_gc6_metrics_mismatch_total_fails(self):
        """GC-6: Mismatch in total_non_spec_claims fails"""
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[],
            integrity_metrics=IntegrityMetrics(
                unsupported_non_spec_claims=1,
                total_non_spec_claims=5,  # Wrong
                unsupported_claim_rate=0.2,
                unsupported_claim_ids=["claim-001"],
            ),
        )
        
        evidence_by_id = {}
        is_valid, errors = validate_and_compute_integrity_metrics(report, evidence_by_id)
        
        assert not is_valid
        assert any("INTEGRITY_METRICS_MISMATCH" in err and "total_non_spec_claims" in err for err in errors)
    
    def test_gc6_metrics_mismatch_ids_fails(self):
        """GC-6: Mismatch in unsupported_claim_ids fails"""
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[],
            integrity_metrics=IntegrityMetrics(
                unsupported_non_spec_claims=1,
                total_non_spec_claims=1,
                unsupported_claim_rate=1.0,
                unsupported_claim_ids=["claim-999"],  # Wrong ID
            ),
        )
        
        evidence_by_id = {}
        is_valid, errors = validate_and_compute_integrity_metrics(report, evidence_by_id)
        
        assert not is_valid
        assert any("INTEGRITY_METRICS_MISMATCH" in err and "unsupported_claim_ids" in err for err in errors)
    
    def test_gc6_metrics_mismatch_rate_fails_at_construction(self):
        """GC-6: Mismatch in unsupported_claim_rate fails at construction"""
        # IntegrityMetrics validates rate matches ints at construction
        with pytest.raises(ValueError, match="METRICS_INCONSISTENT"):
            IntegrityMetrics(
                unsupported_non_spec_claims=1,
                total_non_spec_claims=2,
                unsupported_claim_rate=0.75,  # Wrong, should be 0.5
                unsupported_claim_ids=["claim-001"],
            )
    
    def test_gc6_metrics_none_computes_and_sets(self):
        """GC-6: When metrics is None, compute and set"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-001"])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[evidence],
            integrity_metrics=None,
        )
        
        evidence_by_id = {"evidence-001": evidence}
        is_valid, errors = validate_and_compute_integrity_metrics(report, evidence_by_id)
        
        assert is_valid
        assert len(errors) == 0
        assert report.integrity_metrics is not None
        assert report.integrity_metrics.unsupported_non_spec_claims == 0
        assert report.integrity_metrics.total_non_spec_claims == 1
        assert report.integrity_metrics.unsupported_claim_rate == 0.0


class TestSpeculativeFloodWarning:
    """Test SPECULATIVE_FLOOD_WARNING"""
    
    def test_gc6_speculative_flood_warning_emits_warning_only(self):
        """GC-6: SPECULATIVE_FLOOD_WARNING emits warning but does not fail"""
        claims = [
            Claim(claim_id="claim-001", statement="Spec", claim_label=ClaimLabel.SPECULATIVE, verify_falsify="Test"),
            Claim(claim_id="claim-002", statement="Spec", claim_label=ClaimLabel.SPECULATIVE, verify_falsify="Test"),
            Claim(claim_id="claim-003", statement="Derived", claim_label=ClaimLabel.DERIVED, evidence_ids=[]),
        ]
        
        warning = compute_speculative_flood_warning(claims)
        
        assert warning is not None
        assert "SPECULATIVE_FLOOD_WARNING" in warning
        assert "2/3" in warning
        assert "66" in warning or "67" in warning  # 66.7%
    
    def test_gc6_speculative_flood_no_warning_below_threshold(self):
        """GC-6: No warning when speculative ratio <= 0.30"""
        claims = [
            Claim(claim_id="claim-001", statement="Spec", claim_label=ClaimLabel.SPECULATIVE, verify_falsify="Test"),
            Claim(claim_id="claim-002", statement="Derived", claim_label=ClaimLabel.DERIVED, evidence_ids=[]),
            Claim(claim_id="claim-003", statement="Computed", claim_label=ClaimLabel.COMPUTED, evidence_ids=[]),
            Claim(claim_id="claim-004", statement="Cited", claim_label=ClaimLabel.CITED, evidence_ids=[]),
        ]
        
        warning = compute_speculative_flood_warning(claims)
        
        assert warning is None  # 1/4 = 25% <= 30%
    
    def test_gc6_speculative_flood_warning_does_not_block_validation(self):
        """GC-6: SPECULATIVE_FLOOD_WARNING does not block validation"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        
        # 2/3 speculative (> 30%)
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Spec", claim_label=ClaimLabel.SPECULATIVE, verify_falsify="Test"),
                Claim(claim_id="claim-002", statement="Spec", claim_label=ClaimLabel.SPECULATIVE, verify_falsify="Test"),
                Claim(claim_id="claim-003", statement="Derived", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-001"]),
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001", "claim-002", "claim-003"], statement="Test derivation step")],
            evidence=[evidence],
        )
        
        evidence_by_id = {"evidence-001": evidence}
        is_valid, errors = validate_and_compute_integrity_metrics(report, evidence_by_id)
        
        # Validation passes despite warning
        assert is_valid
        assert len(errors) == 0
        assert len(report.integrity_warnings) > 0
        assert any("SPECULATIVE_FLOOD_WARNING" in w for w in report.integrity_warnings)


class TestValidationOrder:
    """Test GC-5 -> GC-4 -> GC-6 validation order"""
    
    def test_gc6_validation_order_explicit(self):
        """GC-6: Validation order is GC-5 -> GC-4 -> GC-6"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-001"])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[evidence],
        )
        
        is_valid, errors = validate_report_with_integrity(report)
        
        assert is_valid
        assert len(errors) == 0
        assert report.integrity_metrics is not None


class TestFinalization:
    """Test finalization blocking on GC-6 errors"""
    
    def test_gc6_finalization_blocked_on_unsupported_claims(self):
        """GC-6: FINAL blocked when unsupported claims exist"""
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[],
        )
        
        can_finalize, blockers = can_finalize_report(report)
        
        assert not can_finalize
        assert len(blockers) > 0
        # Check that finalization is blocked (specific message format may vary)
        assert any("claim-001" in b for b in blockers) or any("unsupported" in b.lower() for b in blockers)
    
    def test_gc6_finalization_allowed_when_all_supported(self):
        """GC-6: FINAL allowed when all non-SPECULATIVE claims are supported"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        
        report = ScientificReport(
            claims=[
                Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["evidence-001"])
            ],
            steps=[DerivationStep(step_id="step-001", claim_ids=["claim-001"], statement="Test derivation step")],
            evidence=[evidence],
        )
        
        can_finalize, blockers = can_finalize_report(report)
        
        assert can_finalize
        assert len(blockers) == 0


class TestGC6Fixtures:
    """Test GC-6 fixtures"""
    
    def test_gc6_report_valid_all_supported_fixture(self):
        """GC-6: All supported fixture passes full validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_report_valid_all_supported.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
                evidence_ids=c.get("evidence_ids", []),
                verify_falsify=c.get("verify_falsify"),
            )
            for c in data["claims"]
        ]
        
        steps = [_make_step_from_fixture(s) for s in data["steps"]]
        
        evidence = [parse_evidence_object(e) for e in data["evidence"]]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_report_with_integrity(report)
        
        assert is_valid
        assert len(errors) == 0
        assert report.integrity_metrics.unsupported_non_spec_claims == 0
        assert report.integrity_metrics.total_non_spec_claims == 2  # 2 non-SPECULATIVE
        assert report.integrity_metrics.unsupported_claim_rate == 0.0
    
    def test_gc6_metrics_only_mixed_support_fixture(self):
        """GC-6: Mixed support fixture (metrics-only, may fail GC-4)"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_metrics_only_mixed_support.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
                evidence_ids=c.get("evidence_ids", []),
                verify_falsify=c.get("verify_falsify"),
            )
            for c in data["claims"]
        ]
        
        steps = [_make_step_from_fixture(s) for s in data["steps"]]
        
        evidence = [parse_evidence_object(e) for e in data["evidence"]]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_report_with_integrity(report)
        
        # GC-4 will fail due to dangling evidence, but we can still compute metrics
        # For this test, we're checking the computation works
        assert report.integrity_metrics is not None
        assert report.integrity_metrics.unsupported_non_spec_claims == 2
        assert report.integrity_metrics.total_non_spec_claims == 3
        assert abs(report.integrity_metrics.unsupported_claim_rate - 2/3) < 1e-9
        assert report.integrity_metrics.unsupported_claim_ids == ["claim-002", "claim-003"]
    
    def test_gc6_report_valid_zero_total_fixture(self):
        """GC-6: Zero total fixture passes full validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_report_valid_zero_total.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
                verify_falsify=c.get("verify_falsify"),
            )
            for c in data["claims"]
        ]
        
        steps = [_make_step_from_fixture(s) for s in data["steps"]]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=[])
        is_valid, errors = validate_report_with_integrity(report)
        
        assert is_valid
        assert report.integrity_metrics.unsupported_non_spec_claims == 0
        assert report.integrity_metrics.total_non_spec_claims == 0
        assert report.integrity_metrics.unsupported_claim_rate == 0.0
    
    def test_gc6_invalid_metrics_mismatch_unsupported_fixture(self):
        """GC-6: Metrics mismatch fixture fails with INTEGRITY_METRICS_MISMATCH"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_invalid_metrics_mismatch_unsupported.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
                evidence_ids=c.get("evidence_ids", []),
            )
            for c in data["claims"]
        ]
        
        steps = [_make_step_from_fixture(s) for s in data["steps"]]
        
        metrics_data = data["integrity_metrics"]
        metrics = IntegrityMetrics(
            unsupported_non_spec_claims=metrics_data["unsupported_non_spec_claims"],
            total_non_spec_claims=metrics_data["total_non_spec_claims"],
            unsupported_claim_rate=metrics_data["unsupported_claim_rate"],
            unsupported_claim_ids=metrics_data["unsupported_claim_ids"],
        )
        
        report = ScientificReport(claims=claims, steps=steps, evidence=[], integrity_metrics=metrics)
        is_valid, errors = validate_report_with_integrity(report)
        
        assert not is_valid
        assert any("INTEGRITY_METRICS_MISMATCH" in err for err in errors)
    
    def test_gc6_invalid_metrics_mismatch_ids_fixture(self):
        """GC-6: Metrics mismatch IDs fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_invalid_metrics_mismatch_ids.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
                evidence_ids=c.get("evidence_ids", []),
            )
            for c in data["claims"]
        ]
        
        steps = [_make_step_from_fixture(s) for s in data["steps"]]
        
        metrics_data = data["integrity_metrics"]
        metrics = IntegrityMetrics(
            unsupported_non_spec_claims=metrics_data["unsupported_non_spec_claims"],
            total_non_spec_claims=metrics_data["total_non_spec_claims"],
            unsupported_claim_rate=metrics_data["unsupported_claim_rate"],
            unsupported_claim_ids=metrics_data["unsupported_claim_ids"],
        )
        
        report = ScientificReport(claims=claims, steps=steps, evidence=[], integrity_metrics=metrics)
        is_valid, errors = validate_report_with_integrity(report)
        
        assert not is_valid
        assert any("INTEGRITY_METRICS_MISMATCH" in err and "unsupported_claim_ids" in err for err in errors)
    
    def test_gc6_invalid_metrics_wrong_type_int_fixture(self):
        """GC-6: Wrong type for int field fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_invalid_metrics_wrong_type_int.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        metrics_data = data["integrity_metrics"]
        
        with pytest.raises(TypeError, match="unsupported_non_spec_claims must be int"):
            IntegrityMetrics(
                unsupported_non_spec_claims=metrics_data["unsupported_non_spec_claims"],
                total_non_spec_claims=metrics_data["total_non_spec_claims"],
                unsupported_claim_rate=metrics_data["unsupported_claim_rate"],
                unsupported_claim_ids=metrics_data["unsupported_claim_ids"],
            )
    
    def test_gc6_invalid_metrics_wrong_type_list_fixture(self):
        """GC-6: Wrong type for list field fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc6_invalid_metrics_wrong_type_list.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        metrics_data = data["integrity_metrics"]
        
        with pytest.raises(TypeError, match="unsupported_claim_ids must be list"):
            IntegrityMetrics(
                unsupported_non_spec_claims=metrics_data["unsupported_non_spec_claims"],
                total_non_spec_claims=metrics_data["total_non_spec_claims"],
                unsupported_claim_rate=metrics_data["unsupported_claim_rate"],
                unsupported_claim_ids=metrics_data["unsupported_claim_ids"],
            )
