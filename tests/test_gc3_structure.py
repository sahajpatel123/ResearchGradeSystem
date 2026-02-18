"""
GC-3 Step/Claim Boundary Tests

Tests for strict structural validation of DerivationStep and ScientificReport.
"""

import json
import pytest
from pathlib import Path
from src.core.claim import Claim, ClaimLabel
from src.core.step import DerivationStep, StepStatus
from src.core.report import ScientificReport
from src.core.structure_validators import (
    StructureValidator,
    ValidationError,
    validate_report_structure,
)


class TestDerivationStepSchema:
    """Test DerivationStep schema validation"""
    
    def test_step_creation_valid(self):
        """GC-3: Valid step creation with non-empty claim_ids"""
        step = DerivationStep(
            step_id="step-001",
            claim_ids=["claim-001"],
            step_status=StepStatus.UNCHECKED,
        )
        assert step.step_id == "step-001"
        assert step.claim_ids == ["claim-001"]
        assert step.step_status == StepStatus.UNCHECKED
    
    def test_step_claim_ids_non_empty(self):
        """GC-3 V4: Step claim_ids must be non-empty (EMPTY_CLAIM_IDS)"""
        with pytest.raises(ValueError, match="claim_ids cannot be empty"):
            DerivationStep(
                step_id="step-001",
                claim_ids=[],
                step_status=StepStatus.UNCHECKED,
            )
    
    def test_step_duplicate_claim_in_step_rejected(self):
        """GC-3: Duplicate claim_id within single step rejected (DUPLICATE_CLAIM_IN_STEP)"""
        with pytest.raises(ValueError, match="DUPLICATE_CLAIM_IN_STEP"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001", "claim-001"],
                step_status=StepStatus.UNCHECKED,
            )
    
    def test_step_status_enum_required(self):
        """GC-3: step_status must be StepStatus enum"""
        with pytest.raises(TypeError, match="must be StepStatus enum"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status="UNCHECKED",  # String instead of enum
            )
    
    def test_indeterminate_requires_reason(self):
        """GC-3: INDETERMINATE status requires non-empty status_reason"""
        with pytest.raises(ValueError, match="requires non-empty status_reason"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.INDETERMINATE,
                status_reason=None,
            )
        
        with pytest.raises(ValueError, match="requires non-empty status_reason"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                step_status=StepStatus.INDETERMINATE,
                status_reason="   ",  # Whitespace only
            )
    
    def test_indeterminate_with_reason_valid(self):
        """GC-3: INDETERMINATE with valid reason is accepted"""
        step = DerivationStep(
            step_id="step-001",
            claim_ids=["claim-001"],
            step_status=StepStatus.INDETERMINATE,
            status_reason="Insufficient evidence to determine validity",
        )
        assert step.step_status == StepStatus.INDETERMINATE
        assert step.status_reason == "Insufficient evidence to determine validity"
    
    def test_step_create_factory(self):
        """GC-3: Step.create factory generates step_id"""
        step = DerivationStep.create(
            claim_ids=["claim-001", "claim-002"],
            step_status=StepStatus.CHECKED,
        )
        assert step.step_id is not None
        assert len(step.step_id) > 0
        assert step.claim_ids == ["claim-001", "claim-002"]
        assert step.step_status == StepStatus.CHECKED


class TestScientificReportSchema:
    """Test ScientificReport schema validation"""
    
    def test_report_creation_valid(self):
        """GC-3: Valid report creation"""
        claim = Claim.create("Test claim", ClaimLabel.DERIVED)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim.claim_id],
        )
        report = ScientificReport(claims=[claim], steps=[step])
        assert len(report.claims) == 1
        assert len(report.steps) == 1
    
    def test_claim_id_collision_rejected(self):
        """GC-3: Duplicate claim_id in claims list rejected (CLAIM_ID_COLLISION)"""
        claim1 = Claim(
            claim_id="claim-001",
            statement="First claim",
            claim_label=ClaimLabel.DERIVED,
        )
        claim2 = Claim(
            claim_id="claim-001",  # Duplicate
            statement="Second claim",
            claim_label=ClaimLabel.COMPUTED,
        )
        
        with pytest.raises(ValueError, match="CLAIM_ID_COLLISION"):
            ScientificReport(claims=[claim1, claim2], steps=[])
    
    def test_step_id_collision_rejected(self):
        """GC-3: Duplicate step_id in steps list rejected (STEP_ID_COLLISION)"""
        claim = Claim.create("Test", ClaimLabel.DERIVED)
        step1 = DerivationStep(
            step_id="step-001",
            claim_ids=[claim.claim_id],
        )
        step2 = DerivationStep(
            step_id="step-001",  # Duplicate
            claim_ids=[claim.claim_id],
        )
        
        with pytest.raises(ValueError, match="STEP_ID_COLLISION"):
            ScientificReport(claims=[claim], steps=[step1, step2])


class TestStructuralValidation:
    """Test structural validation rules V1-V4"""
    
    def test_step_claim_ids_resolve(self):
        """GC-3 V1: Referenced claim_ids must exist"""
        claim = Claim.create("Test claim", ClaimLabel.DERIVED)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim.claim_id],
        )
        report = ScientificReport(claims=[claim], steps=[step])
        
        is_valid, errors = validate_report_structure(report)
        assert is_valid
        assert len(errors) == 0
    
    def test_dangling_claim_id_rejected(self):
        """GC-3 V1: Dangling claim_id reference rejected (DANGLING_CLAIM_ID)"""
        claim = Claim.create("Test claim", ClaimLabel.DERIVED)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim.claim_id, "non-existent-claim"],
        )
        report = ScientificReport(claims=[claim], steps=[step])
        
        is_valid, errors = validate_report_structure(report)
        assert not is_valid
        assert len(errors) == 1
        assert errors[0].category == "DANGLING_CLAIM_ID"
        assert "non-existent-claim" in errors[0].message
    
    def test_orphan_claim_rejected(self):
        """GC-3 V2: Orphan claim rejected (ORPHAN_CLAIM)"""
        claim1 = Claim.create("Referenced claim", ClaimLabel.DERIVED)
        claim2 = Claim.create("Orphan claim", ClaimLabel.SPECULATIVE)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim1.claim_id],  # Only references claim1
        )
        report = ScientificReport(claims=[claim1, claim2], steps=[step])
        
        is_valid, errors = validate_report_structure(report)
        assert not is_valid
        assert len(errors) == 1
        assert errors[0].category == "ORPHAN_CLAIM"
        assert claim2.claim_id in errors[0].message
    
    def test_claim_unique_owner_enforced(self):
        """GC-3 V3: Unique claim ownership enforced (DUPLICATE_CLAIM_OWNER)"""
        claim = Claim.create("Shared claim", ClaimLabel.DERIVED)
        step1 = DerivationStep(
            step_id="step-001",
            claim_ids=[claim.claim_id],
        )
        step2 = DerivationStep(
            step_id="step-002",
            claim_ids=[claim.claim_id],  # Same claim in different step
        )
        report = ScientificReport(claims=[claim], steps=[step1, step2])
        
        is_valid, errors = validate_report_structure(report)
        assert not is_valid
        assert len(errors) == 1
        assert errors[0].category == "DUPLICATE_CLAIM_OWNER"
        assert errors[0].claim_id == claim.claim_id
        assert "step-001" in errors[0].message
        assert "step-002" in errors[0].message
    
    def test_multiple_claims_single_step_valid(self):
        """GC-3: Multiple claims in single step is valid"""
        claim1 = Claim.create("First claim", ClaimLabel.DERIVED)
        claim2 = Claim.create("Second claim", ClaimLabel.COMPUTED)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim1.claim_id, claim2.claim_id],
        )
        report = ScientificReport(claims=[claim1, claim2], steps=[step])
        
        is_valid, errors = validate_report_structure(report)
        assert is_valid
        assert len(errors) == 0
    
    def test_step_dependencies_validated(self):
        """GC-3: Step dependencies must reference existing steps (DANGLING_STEP_DEP)"""
        claim = Claim.create("Test claim", ClaimLabel.DERIVED)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim.claim_id],
            depends_on=["non-existent-step"],
        )
        report = ScientificReport(claims=[claim], steps=[step])
        
        is_valid, errors = validate_report_structure(report)
        assert not is_valid
        assert len(errors) == 1
        assert errors[0].category == "DANGLING_STEP_DEP"
        assert "non-existent-step" in errors[0].message
    
    def test_valid_step_dependencies(self):
        """GC-3: Valid step dependencies accepted"""
        claim1 = Claim.create("First claim", ClaimLabel.DERIVED)
        claim2 = Claim.create("Second claim", ClaimLabel.COMPUTED)
        step1 = DerivationStep(
            step_id="step-001",
            claim_ids=[claim1.claim_id],
        )
        step2 = DerivationStep(
            step_id="step-002",
            claim_ids=[claim2.claim_id],
            depends_on=["step-001"],
        )
        report = ScientificReport(claims=[claim1, claim2], steps=[step1, step2])
        
        is_valid, errors = validate_report_structure(report)
        assert is_valid
        assert len(errors) == 0


class TestGC3Fixtures:
    """Test GC-3 fixtures for validation"""
    
    def test_gc3_valid_report_fixture(self):
        """GC-3: Valid report fixture passes validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_valid_report.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # Manually construct report from fixture
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
                evidence_ids=c.get("evidence_ids", []),
            )
            for c in data["claims"]
        ]
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
                depends_on=s.get("depends_on", []),
                status_reason=s.get("status_reason"),
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps)
        is_valid, errors = validate_report_structure(report)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_gc3_invalid_dangling_claim_id_fixture(self):
        """GC-3: Dangling claim_id fixture fails validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_dangling_claim_id.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
            )
            for c in data["claims"]
        ]
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps)
        is_valid, errors = validate_report_structure(report)
        
        assert not is_valid
        assert any(e.category == "DANGLING_CLAIM_ID" for e in errors)
    
    def test_gc3_invalid_orphan_claim_fixture(self):
        """GC-3: Orphan claim fixture fails validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_orphan_claim.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
            )
            for c in data["claims"]
        ]
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps)
        is_valid, errors = validate_report_structure(report)
        
        assert not is_valid
        assert any(e.category == "ORPHAN_CLAIM" for e in errors)
    
    def test_gc3_invalid_duplicate_owner_fixture(self):
        """GC-3: Duplicate claim owner fixture fails validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_duplicate_owner.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
            )
            for c in data["claims"]
        ]
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps)
        is_valid, errors = validate_report_structure(report)
        
        assert not is_valid
        assert any(e.category == "DUPLICATE_CLAIM_OWNER" for e in errors)
    
    def test_gc3_invalid_empty_claim_ids_fixture(self):
        """GC-3: Empty claim_ids fixture fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_empty_claim_ids.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="EMPTY_CLAIM_IDS"):
            steps = [
                DerivationStep(
                    step_id=s["step_id"],
                    claim_ids=s["claim_ids"],
                    step_status=StepStatus[s["step_status"]],
                )
                for s in data["steps"]
            ]
    
    def test_gc3_invalid_claim_id_collision_fixture(self):
        """GC-3: Claim ID collision fixture fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_claim_id_collision.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="CLAIM_ID_COLLISION"):
            claims = [
                Claim(
                    claim_id=c["claim_id"],
                    statement=c["statement"],
                    claim_label=ClaimLabel[c["claim_label"]],
                )
                for c in data["claims"]
            ]
            report = ScientificReport(claims=claims, steps=[])
    
    def test_gc3_invalid_step_id_collision_fixture(self):
        """GC-3: Step ID collision fixture fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_step_id_collision.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
            )
            for c in data["claims"]
        ]
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        with pytest.raises(ValueError, match="STEP_ID_COLLISION"):
            report = ScientificReport(claims=claims, steps=steps)
    
    def test_gc3_invalid_duplicate_in_step_fixture(self):
        """GC-3: Duplicate claim in step fixture fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_duplicate_in_step.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="DUPLICATE_CLAIM_IN_STEP"):
            steps = [
                DerivationStep(
                    step_id=s["step_id"],
                    claim_ids=s["claim_ids"],
                    step_status=StepStatus[s["step_status"]],
                )
                for s in data["steps"]
            ]
    
    def test_gc3_invalid_dangling_step_dep_fixture(self):
        """GC-3: Dangling step dependency fixture fails validation"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_dangling_step_dep.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claims = [
            Claim(
                claim_id=c["claim_id"],
                statement=c["statement"],
                claim_label=ClaimLabel[c["claim_label"]],
            )
            for c in data["claims"]
        ]
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
                depends_on=s.get("depends_on", []),
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps)
        is_valid, errors = validate_report_structure(report)
        
        assert not is_valid
        assert any(e.category == "DANGLING_STEP_DEP" for e in errors)
    
    def test_gc3_invalid_indeterminate_no_reason_fixture(self):
        """GC-3: INDETERMINATE without reason fixture fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc3_invalid_indeterminate_no_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="requires non-empty status_reason"):
            steps = [
                DerivationStep(
                    step_id=s["step_id"],
                    claim_ids=s["claim_ids"],
                    step_status=StepStatus[s["step_status"]],
                    status_reason=s.get("status_reason"),
                )
                for s in data["steps"]
            ]


class TestValidationErrorReporting:
    """Test deterministic error reporting"""
    
    def test_validation_error_structure(self):
        """GC-3: ValidationError has deterministic structure"""
        error = ValidationError(
            category="DANGLING_CLAIM_ID",
            message="Step references non-existent claim",
            step_id="step-001",
            claim_id="claim-999",
        )
        
        assert error.category == "DANGLING_CLAIM_ID"
        assert error.step_id == "step-001"
        assert error.claim_id == "claim-999"
        
        error_str = str(error)
        assert "DANGLING_CLAIM_ID" in error_str
        assert "step-001" in error_str
        assert "claim-999" in error_str
    
    def test_multiple_errors_reported(self):
        """GC-3: Multiple validation errors reported together"""
        claim1 = Claim.create("Claim 1", ClaimLabel.DERIVED)
        claim2 = Claim.create("Orphan claim", ClaimLabel.SPECULATIVE)
        
        step = DerivationStep(
            step_id="step-001",
            claim_ids=[claim1.claim_id, "non-existent"],
        )
        
        report = ScientificReport(claims=[claim1, claim2], steps=[step])
        is_valid, errors = validate_report_structure(report)
        
        assert not is_valid
        assert len(errors) == 2
        
        categories = {e.category for e in errors}
        assert "DANGLING_CLAIM_ID" in categories
        assert "ORPHAN_CLAIM" in categories
