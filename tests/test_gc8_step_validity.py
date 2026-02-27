"""
GC-8 Derivation Step Validity Tests

Tests for structural enforcement and warning-only policy to prevent fake steps.
"""

import pytest
import json
from pathlib import Path
from src.core.step import DerivationStep, StepStatus
from src.core.gc8_validators import (
    parse_statement,
    validate_step_object,
    gc8_policy_warnings,
    validate_and_warn_step,
    GC8ValidationError,
    GC8PolicyWarning,
)


class TestStatementParsing:
    """Test parse_statement wire-boundary parser."""
    
    def test_parse_statement_valid(self):
        """GC-8: Valid statement passes."""
        assert parse_statement("Apply the quadratic formula") == "Apply the quadratic formula"
        assert parse_statement("Use integration by parts") == "Use integration by parts"
    
    def test_parse_statement_rejects_none(self):
        """GC-8: Reject None/null statement."""
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            parse_statement(None)
    
    def test_parse_statement_rejects_wrong_type(self):
        """GC-8: Reject non-string statement."""
        with pytest.raises(TypeError, match="DERIVATION_STEP_STATEMENT_INVALID_TYPE"):
            parse_statement(123)
        
        with pytest.raises(TypeError, match="DERIVATION_STEP_STATEMENT_INVALID_TYPE"):
            parse_statement(["statement"])
    
    def test_parse_statement_rejects_empty_string(self):
        """GC-8: Reject empty string statement."""
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            parse_statement("")
    
    def test_parse_statement_rejects_whitespace_only(self):
        """GC-8: Reject whitespace-only statement."""
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            parse_statement("   ")
        
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            parse_statement("\t\n")
    
    def test_parse_statement_rejects_invisible_only(self):
        """GC-8: Reject invisible-only statement (ZWSP, NBSP, etc.)."""
        # ZWSP only
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            parse_statement("\u200b\u200b\u200b")
        
        # NBSP only
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            parse_statement("\u00a0\u00a0")
    
    def test_parse_statement_no_trimming_normalization(self):
        """GC-8: No trimming normalization at wire boundary (store as-is if valid)."""
        # Leading/trailing whitespace preserved if non-empty after trim
        statement = "  Valid statement  "
        assert parse_statement(statement) == statement


class TestDerivationStepValidation:
    """Test DerivationStep schema validation (GC-8 hard rules)."""
    
    def test_derivation_step_requires_non_empty_statement(self):
        """GC-8: DerivationStep requires non-empty statement."""
        # Empty string
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                statement=""
            )
        
        # Whitespace-only
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                statement="   "
            )
        
        # None
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                statement=None
            )
    
    def test_derivation_step_requires_non_empty_claim_ids(self):
        """GC-8: DerivationStep requires non-empty claim_ids."""
        with pytest.raises(ValueError, match="EMPTY_CLAIM_IDS"):
            DerivationStep(
                step_id="step-001",
                claim_ids=[],
                statement="Valid statement"
            )
    
    def test_derivation_step_with_multiple_claim_ids_is_valid(self):
        """GC-8: DerivationStep with multiple claim_ids is valid."""
        step = DerivationStep(
            step_id="step-001",
            claim_ids=["claim-001", "claim-002"],
            statement="Prove both theorems simultaneously"
        )
        assert len(step.claim_ids) == 2
        assert step.statement == "Prove both theorems simultaneously"
    
    def test_derivation_step_statement_type_validation(self):
        """GC-8: DerivationStep rejects non-string statement."""
        with pytest.raises(TypeError, match="DERIVATION_STEP_STATEMENT_INVALID_TYPE"):
            DerivationStep(
                step_id="step-001",
                claim_ids=["claim-001"],
                statement=123
            )


class TestGC8PolicyWarnings:
    """Test GC-8 warning-only policy checks."""
    
    def test_gc8_placeholder_phrase_emits_warning_not_fail(self):
        """GC-8: Placeholder phrase emits warning, does not fail validation."""
        # Structurally valid step with placeholder phrase
        step = DerivationStep(
            step_id="step-001",
            claim_ids=["claim-001"],
            statement="Using standard methods, we obtain the result"
        )
        
        # Step is valid (no exception raised)
        assert step.statement == "Using standard methods, we obtain the result"
        
        # But policy warnings should detect placeholder
        warnings = gc8_policy_warnings(step.step_id, step.statement)
        assert len(warnings) > 0
        assert any(w.warning_id == "DERIVATION_STEP_FAKE_PLACEHOLDER_WARNING" for w in warnings)
    
    def test_gc8_policy_detects_various_placeholder_phrases(self):
        """GC-8: Policy detects various placeholder phrase patterns."""
        test_cases = [
            ("Using standard methods to solve", "using standard methods"),
            ("After simplification, we get x=5", "after simplification"),
            ("It is obvious that the answer is 42", "it is obvious"),
            ("Therefore the answer follows directly", "therefore the answer follows"),
            ("Now continue solving the equation", "now continue solving"),
        ]
        
        for statement, expected_phrase in test_cases:
            warnings = gc8_policy_warnings("step-001", statement)
            assert len(warnings) > 0, f"Expected warning for: {statement}"
            assert warnings[0].warning_id == "DERIVATION_STEP_FAKE_PLACEHOLDER_WARNING"
    
    def test_gc8_policy_no_warnings_for_valid_statements(self):
        """GC-8: No warnings for valid, specific statements."""
        valid_statements = [
            "Apply the quadratic formula to derive x = (-b ± sqrt(b^2 - 4ac)) / 2a",
            "Integrate by parts with u = x, dv = e^x dx",
            "Substitute y = x^2 to transform the differential equation",
        ]
        
        for statement in valid_statements:
            warnings = gc8_policy_warnings("step-001", statement)
            # May have weak action semantics warning, but not placeholder warning
            placeholder_warnings = [w for w in warnings if w.warning_id == "DERIVATION_STEP_FAKE_PLACEHOLDER_WARNING"]
            assert len(placeholder_warnings) == 0, f"Unexpected warning for: {statement}"


class TestGC8ValidateStepObject:
    """Test validate_step_object wire-boundary validator."""
    
    def test_validate_step_object_valid(self):
        """GC-8: Valid step object passes validation."""
        step_wire = {
            "step_id": "step-001",
            "claim_ids": ["claim-001"],
            "statement": "Apply the quadratic formula",
            "step_status": "checked"
        }
        
        parsed, errors = validate_step_object(step_wire)
        assert len(errors) == 0
        assert parsed["statement"] == "Apply the quadratic formula"
        assert parsed["claim_ids"] == ["claim-001"]
    
    def test_validate_step_object_empty_statement(self):
        """GC-8: Empty statement triggers validation error."""
        step_wire = {
            "step_id": "step-001",
            "claim_ids": ["claim-001"],
            "statement": "",
            "step_status": "unchecked"
        }
        
        parsed, errors = validate_step_object(step_wire)
        assert len(errors) == 1
        assert errors[0].category == "DERIVATION_STEP_EMPTY_STATEMENT"
    
    def test_validate_step_object_empty_claim_ids(self):
        """GC-8: Empty claim_ids triggers validation error."""
        step_wire = {
            "step_id": "step-001",
            "claim_ids": [],
            "statement": "Valid statement",
            "step_status": "unchecked"
        }
        
        parsed, errors = validate_step_object(step_wire)
        assert len(errors) == 1
        assert errors[0].category == "DERIVATION_STEP_EMPTY_CLAIM_IDS"


class TestGC8ValidationLayering:
    """Test GC-8 validation layering: parse -> hard validation -> policy warnings."""
    
    def test_validation_layering_full_pipeline(self):
        """GC-8: Full validation pipeline executes in correct order."""
        # Valid step with placeholder phrase
        step_wire = {
            "step_id": "step-001",
            "claim_ids": ["claim-001"],
            "statement": "Using standard methods, we obtain the result",
            "step_status": "checked"
        }
        
        parsed, errors, warnings = validate_and_warn_step(step_wire)
        
        # No hard errors
        assert len(errors) == 0
        
        # But has policy warning
        assert len(warnings) > 0
        assert warnings[0].warning_id == "DERIVATION_STEP_FAKE_PLACEHOLDER_WARNING"
    
    def test_validation_layering_hard_errors_skip_warnings(self):
        """GC-8: Hard validation errors skip policy warning checks."""
        # Invalid step (empty statement)
        step_wire = {
            "step_id": "step-001",
            "claim_ids": ["claim-001"],
            "statement": "",
            "step_status": "unchecked"
        }
        
        parsed, errors, warnings = validate_and_warn_step(step_wire)
        
        # Has hard error
        assert len(errors) == 1
        assert errors[0].category == "DERIVATION_STEP_EMPTY_STATEMENT"
        
        # No warnings (skipped due to hard error)
        assert len(warnings) == 0


class TestGC8Fixtures:
    """Test GC-8 fixtures."""
    
    def test_fixture_pass_single_step(self):
        """PASS fixture: Valid single step."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_pass_single_step.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        step = DerivationStep(
            step_id=step_data["step_id"],
            claim_ids=step_data["claim_ids"],
            statement=step_data["statement"],
            step_status=StepStatus[step_data["step_status"].upper()]
        )
        
        assert step.statement == "Apply the quadratic formula to derive the roots of the equation"
        assert len(step.claim_ids) == 1
    
    def test_fixture_pass_multi_claim_step(self):
        """PASS fixture: Valid step with multiple claim_ids."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_pass_multi_claim_step.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        step = DerivationStep(
            step_id=step_data["step_id"],
            claim_ids=step_data["claim_ids"],
            statement=step_data["statement"],
            step_status=StepStatus[step_data["step_status"].upper()]
        )
        
        assert len(step.claim_ids) == 2
        assert "parallel line properties" in step.statement
    
    def test_fixture_fail_empty_claim_ids(self):
        """FAIL fixture: Empty claim_ids list."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_fail_empty_claim_ids.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="EMPTY_CLAIM_IDS"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                statement=step_data["statement"],
                step_status=StepStatus[step_data["step_status"].upper()]
            )
    
    def test_fixture_fail_empty_statement(self):
        """FAIL fixture: Empty string statement."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_fail_empty_statement.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                statement=step_data["statement"],
                step_status=StepStatus[step_data["step_status"].upper()]
            )
    
    def test_fixture_fail_whitespace_statement(self):
        """FAIL fixture: Whitespace-only statement."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_fail_whitespace_statement.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                statement=step_data["statement"],
                step_status=StepStatus[step_data["step_status"].upper()]
            )
    
    def test_fixture_fail_null_statement(self):
        """FAIL fixture: Null statement."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_fail_null_statement.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                statement=step_data.get("statement"),
                step_status=StepStatus[step_data["step_status"].upper()]
            )
    
    def test_fixture_fail_invisible_statement(self):
        """FAIL fixture: Invisible-only statement."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_fail_invisible_statement.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        with pytest.raises(ValueError, match="DERIVATION_STEP_EMPTY_STATEMENT"):
            DerivationStep(
                step_id=step_data["step_id"],
                claim_ids=step_data["claim_ids"],
                statement=step_data["statement"],
                step_status=StepStatus[step_data["step_status"].upper()]
            )
    
    def test_fixture_warn_placeholder_phrase(self):
        """WARN fixture: Placeholder phrase (PASS + warning)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc8_warn_placeholder_phrase.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        step_data = data["steps"][0]
        # Should NOT raise - structurally valid
        step = DerivationStep(
            step_id=step_data["step_id"],
            claim_ids=step_data["claim_ids"],
            statement=step_data["statement"],
            step_status=StepStatus[step_data["step_status"].upper()]
        )
        
        # But should emit warning
        warnings = gc8_policy_warnings(step.step_id, step.statement)
        assert len(warnings) > 0
        assert any(w.warning_id == "DERIVATION_STEP_FAKE_PLACEHOLDER_WARNING" for w in warnings)


class TestGC3vsGC8ResponsibilitySplit:
    """Test GC-3 vs GC-8 responsibility split (non-overlapping categories)."""
    
    def test_gc8_does_not_duplicate_gc3_claim_resolution_errors(self):
        """GC-8: Does NOT check if claim_ids resolve (that's GC-3's job)."""
        # GC-8 only checks structural validity: claim_ids is non-empty list
        # GC-8 does NOT check if claim_ids resolve to actual claims (GC-3 owns that)
        
        # This step has non-empty claim_ids (GC-8 structural check passes)
        # Even though claim_ids may not resolve to actual claims (GC-3 would catch that)
        step = DerivationStep(
            step_id="step-001",
            claim_ids=["nonexistent-claim"],  # GC-8 doesn't care if this resolves
            statement="Valid statement"
        )
        
        # GC-8 validation passes (structural check only)
        assert len(step.claim_ids) == 1
        assert step.statement == "Valid statement"
        
        # GC-3 would catch the dangling claim_id during report validation
        # But that's GC-3's responsibility, not GC-8's
