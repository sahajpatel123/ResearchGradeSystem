"""
GC-4 Evidence Attachment Tests

Tests for strict evidence validation and wire-boundary parsing.
"""

import json
import pytest
from pathlib import Path
from src.core.claim import Claim, ClaimLabel
from src.core.step import DerivationStep, StepStatus
from src.core.evidence import EvidenceObject
from src.core.report import ScientificReport
from src.core.evidence_validators import (
    parse_evidence_id,
    parse_evidence_ids,
    EvidenceValidator,
    validate_evidence_attachment,
)


class TestEvidenceObjectSchema:
    """Test EvidenceObject schema validation"""
    
    def test_evidence_creation_valid(self):
        """GC-4: Valid evidence object creation"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type="derivation",
            content="Proof steps",
        )
        assert evidence.evidence_id == "evidence-001"
        assert evidence.evidence_type == "derivation"
    
    def test_evidence_id_required(self):
        """GC-4: evidence_id must be non-empty"""
        with pytest.raises(ValueError, match="evidence_id must be non-empty"):
            EvidenceObject(evidence_id="")
        
        with pytest.raises(ValueError, match="whitespace-only"):
            EvidenceObject(evidence_id="   ")
    
    def test_evidence_id_whitespace_variants_rejected(self):
        """GC-4 WIRE-BOUNDARY HARDENING: evidence_id with whitespace variants rejected"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            EvidenceObject(evidence_id="  evidence-001  ")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            EvidenceObject(evidence_id=" evidence-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            EvidenceObject(evidence_id="evidence-001 ")


class TestWireBoundaryParsing:
    """Test wire-boundary parsers for evidence_ids"""
    
    def test_parse_evidence_id_valid(self):
        """GC-4: Valid evidence_id accepted (exact match, no trimming)"""
        assert parse_evidence_id("evidence-001") == "evidence-001"
        assert parse_evidence_id("evidence-002") == "evidence-002"
    
    def test_parse_evidence_id_rejects_none(self):
        """GC-4: None rejected"""
        with pytest.raises(ValueError, match="Invalid evidence_id: None"):
            parse_evidence_id(None)
    
    def test_parse_evidence_id_rejects_non_string(self):
        """GC-4: Non-string types rejected"""
        with pytest.raises(TypeError, match="expected string, got int"):
            parse_evidence_id(123)
        
        with pytest.raises(TypeError, match="expected string, got list"):
            parse_evidence_id(["evidence-001"])
        
        with pytest.raises(TypeError, match="expected string, got dict"):
            parse_evidence_id({"id": "evidence-001"})
    
    def test_parse_evidence_id_rejects_empty(self):
        """GC-4: Empty string rejected"""
        with pytest.raises(ValueError, match="empty string"):
            parse_evidence_id("")
    
    def test_parse_evidence_id_rejects_whitespace(self):
        """GC-4: Whitespace-only rejected"""
        with pytest.raises(ValueError, match="whitespace-only"):
            parse_evidence_id("   ")
        
        with pytest.raises(ValueError, match="whitespace-only"):
            parse_evidence_id("\t\n")
    
    def test_parse_evidence_id_rejects_leading_trailing_whitespace(self):
        """GC-4 WIRE-BOUNDARY HARDENING: Leading/trailing whitespace variants rejected (NO TRIMMING)"""
        # Leading space
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id(" evidence-001")
        
        # Trailing space
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id("evidence-001 ")
        
        # Both leading and trailing
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id("  evidence-001  ")
        
        # Leading tab
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id("\tevidence-001")
        
        # Trailing newline
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id("evidence-001\n")
        
        # Trailing carriage return
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id("evidence-001\r")
    
    def test_parse_evidence_id_rejects_zwsp(self):
        """GC-4: ZWSP rejected"""
        with pytest.raises(ValueError, match="invisible unicode character"):
            parse_evidence_id("evidence-001\u200b")
    
    def test_parse_evidence_id_rejects_nbsp(self):
        """GC-4: NBSP rejected"""
        with pytest.raises(ValueError, match="invisible unicode character"):
            parse_evidence_id("evidence-001\u00a0")
    
    def test_parse_evidence_id_rejects_non_ascii(self):
        """GC-4: Non-ASCII characters rejected"""
        with pytest.raises(ValueError, match="non-ASCII characters"):
            parse_evidence_id("evidence-Ε01")  # Greek Epsilon
    
    def test_parse_evidence_ids_valid(self):
        """GC-4: Valid evidence_ids list accepted"""
        result = parse_evidence_ids(["evidence-001", "evidence-002"])
        assert result == ["evidence-001", "evidence-002"]
    
    def test_parse_evidence_ids_empty_list_valid(self):
        """GC-4: Empty list is valid (for SPECULATIVE claims)"""
        result = parse_evidence_ids([])
        assert result == []
    
    def test_parse_evidence_ids_rejects_non_list(self):
        """GC-4: Non-list types rejected"""
        with pytest.raises(TypeError, match="expected list, got str"):
            parse_evidence_ids("evidence-001")
    
    def test_parse_evidence_ids_rejects_duplicates(self):
        """GC-4: Duplicate evidence_ids rejected"""
        with pytest.raises(ValueError, match="EVIDENCE_ID_DUP_IN_CLAIM"):
            parse_evidence_ids(["evidence-001", "evidence-001"])
    
    def test_parse_evidence_ids_rejects_invalid_entry(self):
        """GC-4: Invalid entry in list rejected"""
        with pytest.raises(ValueError, match="Invalid evidence_ids\\[1\\]"):
            parse_evidence_ids(["evidence-001", ""])


class TestEvidenceValidation:
    """Test GC-4 evidence validation rules"""
    
    def test_non_spec_requires_evidence_ids(self):
        """GC-4: Non-SPECULATIVE claims must have ≥1 evidence_id (NON_SPEC_MISSING_EVIDENCE)"""
        claim = Claim(
            claim_id="claim-001",
            statement="Energy is conserved",
            claim_label=ClaimLabel.DERIVED,
            evidence_ids=[],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("NON_SPEC_MISSING_EVIDENCE" in err for err in errors)
    
    def test_derived_with_evidence_valid(self):
        """GC-4: DERIVED claim with evidence_ids is valid"""
        evidence = EvidenceObject(evidence_id="evidence-001")
        claim = Claim(
            claim_id="claim-001",
            statement="The theorem holds",
            claim_label=ClaimLabel.DERIVED,
            evidence_ids=["evidence-001"],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[evidence])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert is_valid
        assert len(errors) == 0
    
    def test_computed_requires_evidence(self):
        """GC-4: COMPUTED claim requires evidence"""
        claim = Claim(
            claim_id="claim-001",
            statement="Simulation confirms result",
            claim_label=ClaimLabel.COMPUTED,
            evidence_ids=[],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("NON_SPEC_MISSING_EVIDENCE" in err for err in errors)
    
    def test_cited_requires_evidence(self):
        """GC-4: CITED claim requires evidence"""
        claim = Claim(
            claim_id="claim-001",
            statement="According to Einstein (1905)",
            claim_label=ClaimLabel.CITED,
            evidence_ids=[],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("NON_SPEC_MISSING_EVIDENCE" in err for err in errors)
    
    def test_spec_requires_verify_falsify(self):
        """GC-4: SPECULATIVE claim must have verify_falsify (SPEC_MISSING_VERIFY_FALSIFY)"""
        claim = Claim(
            claim_id="claim-001",
            statement="This might work",
            claim_label=ClaimLabel.SPECULATIVE,
            evidence_ids=[],
            verify_falsify=None,
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("SPEC_MISSING_VERIFY_FALSIFY" in err for err in errors)
    
    def test_spec_whitespace_verify_falsify_rejected(self):
        """GC-4: SPECULATIVE with whitespace-only verify_falsify rejected"""
        claim = Claim(
            claim_id="claim-001",
            statement="This might work",
            claim_label=ClaimLabel.SPECULATIVE,
            evidence_ids=[],
            verify_falsify="   ",
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("SPEC_MISSING_VERIFY_FALSIFY" in err for err in errors)
    
    def test_spec_with_verify_falsify_valid(self):
        """GC-4: SPECULATIVE with valid verify_falsify is valid"""
        claim = Claim(
            claim_id="claim-001",
            statement="This might work",
            claim_label=ClaimLabel.SPECULATIVE,
            evidence_ids=[],
            verify_falsify="Could test by running experiment X",
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert is_valid
        assert len(errors) == 0
    
    def test_evidence_ids_must_resolve(self):
        """GC-4: evidence_ids must resolve to report.evidence (DANGLING_EVIDENCE_ID)"""
        evidence = EvidenceObject(evidence_id="evidence-001")
        claim = Claim(
            claim_id="claim-001",
            statement="The proof is complete",
            claim_label=ClaimLabel.DERIVED,
            evidence_ids=["evidence-001", "evidence-999"],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[evidence])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("DANGLING_EVIDENCE_ID" in err and "evidence-999" in err for err in errors)
    
    def test_duplicate_evidence_ids_rejected(self):
        """GC-4: Duplicate evidence_ids within claim rejected (EVIDENCE_ID_DUP_IN_CLAIM)"""
        evidence = EvidenceObject(evidence_id="evidence-001")
        claim = Claim(
            claim_id="claim-001",
            statement="The calculation is correct",
            claim_label=ClaimLabel.COMPUTED,
            evidence_ids=["evidence-001", "evidence-001"],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(claims=[claim], steps=[step], evidence=[evidence])
        
        is_valid, errors = validate_evidence_attachment(report)
        assert not is_valid
        assert any("EVIDENCE_ID_DUP_IN_CLAIM" in err for err in errors)
    
    def test_multiple_evidence_ids_valid(self):
        """GC-4: Multiple evidence_ids is valid"""
        evidence1 = EvidenceObject(evidence_id="evidence-001")
        evidence2 = EvidenceObject(evidence_id="evidence-002")
        claim = Claim(
            claim_id="claim-001",
            statement="The theorem is proven",
            claim_label=ClaimLabel.DERIVED,
            evidence_ids=["evidence-001", "evidence-002"],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        report = ScientificReport(
            claims=[claim],
            steps=[step],
            evidence=[evidence1, evidence2],
        )
        
        is_valid, errors = validate_evidence_attachment(report)
        assert is_valid
        assert len(errors) == 0


class TestGC4Fixtures:
    """Test GC-4 fixtures for validation"""
    
    def test_gc4_valid_all_evidence_fixture(self):
        """GC-4: Valid fixture with all 4 claim types passes"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_valid_all_evidence.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # Construct report from fixture
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
                depends_on=s.get("depends_on", []),
            )
            for s in data["steps"]
        ]
        
        evidence = [
            EvidenceObject(
                evidence_id=e["evidence_id"],
                evidence_type=e.get("evidence_type"),
                content=e.get("content"),
                source=e.get("source"),
            )
            for e in data["evidence"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_evidence_attachment(report)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_gc4_invalid_non_spec_missing_evidence_fixture(self):
        """GC-4: Non-SPECULATIVE missing evidence fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_non_spec_missing_evidence.json"
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        evidence = [
            EvidenceObject(evidence_id=e["evidence_id"])
            for e in data.get("evidence", [])
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_evidence_attachment(report)
        
        assert not is_valid
        assert any("NON_SPEC_MISSING_EVIDENCE" in err for err in errors)
    
    def test_gc4_invalid_spec_missing_verify_falsify_fixture(self):
        """GC-4: SPECULATIVE missing verify_falsify fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_spec_missing_verify_falsify.json"
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=[])
        is_valid, errors = validate_evidence_attachment(report)
        
        assert not is_valid
        assert any("SPEC_MISSING_VERIFY_FALSIFY" in err for err in errors)
    
    def test_gc4_invalid_dangling_evidence_id_fixture(self):
        """GC-4: Dangling evidence_id fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_dangling_evidence_id.json"
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        evidence = [
            EvidenceObject(evidence_id=e["evidence_id"])
            for e in data["evidence"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_evidence_attachment(report)
        
        assert not is_valid
        assert any("DANGLING_EVIDENCE_ID" in err and "evidence-999" in err for err in errors)
    
    def test_gc4_invalid_duplicate_evidence_ids_fixture(self):
        """GC-4: Duplicate evidence_ids fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_duplicate_evidence_ids.json"
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        evidence = [
            EvidenceObject(evidence_id=e["evidence_id"])
            for e in data["evidence"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_evidence_attachment(report)
        
        assert not is_valid
        assert any("EVIDENCE_ID_DUP_IN_CLAIM" in err for err in errors)
    
    def test_gc4_invalid_evidence_ids_wrong_type_fixture(self):
        """GC-4: evidence_ids wrong type fixture fails at construction"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_evidence_ids_wrong_type.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # This should fail at Claim construction due to type validation
        with pytest.raises(TypeError, match="evidence_ids must be a list"):
            claims = [
                Claim(
                    claim_id=c["claim_id"],
                    statement=c["statement"],
                    claim_label=ClaimLabel[c["claim_label"]],
                    evidence_ids=c.get("evidence_ids", []),
                )
                for c in data["claims"]
            ]
    
    def test_gc4_invalid_evidence_id_zwsp_fixture(self):
        """GC-4: evidence_id with ZWSP fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_evidence_id_zwsp.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # Test wire parser rejects ZWSP
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="invisible unicode character"):
            parse_evidence_ids(claim_data["evidence_ids"])
    
    def test_gc4_invalid_spec_whitespace_verify_falsify_fixture(self):
        """GC-4: SPECULATIVE with whitespace verify_falsify fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_spec_whitespace_verify_falsify.json"
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=[])
        is_valid, errors = validate_evidence_attachment(report)
        
        assert not is_valid
        assert any("SPEC_MISSING_VERIFY_FALSIFY" in err for err in errors)
    
    def test_gc4_invalid_evidence_id_leading_space_fixture(self):
        """GC-4 WIRE-BOUNDARY HARDENING: Leading space fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_evidence_id_leading_space.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_ids(claim_data["evidence_ids"])
    
    def test_gc4_invalid_evidence_id_trailing_space_fixture(self):
        """GC-4 WIRE-BOUNDARY HARDENING: Trailing space fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_evidence_id_trailing_space.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_ids(claim_data["evidence_ids"])
    
    def test_gc4_invalid_evidence_id_leading_tab_fixture(self):
        """GC-4 WIRE-BOUNDARY HARDENING: Leading tab fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_evidence_id_leading_tab.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_ids(claim_data["evidence_ids"])
    
    def test_gc4_invalid_evidence_id_trailing_newline_fixture(self):
        """GC-4 WIRE-BOUNDARY HARDENING: Trailing newline fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_evidence_id_trailing_newline.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_ids(claim_data["evidence_ids"])
    
    def test_gc4_invalid_multiple_dangling_evidence_ids_fixture(self):
        """GC-4 REGRESSION: Multiple dangling evidence_ids all detected (not just first)"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc4_invalid_multiple_dangling_evidence_ids.json"
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        evidence = [
            EvidenceObject(evidence_id=e["evidence_id"])
            for e in data["evidence"]
        ]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_evidence_attachment(report)
        
        assert not is_valid
        # Both evidence-002 and evidence-999 should be detected as dangling
        dangling_errors = [err for err in errors if "DANGLING_EVIDENCE_ID" in err]
        assert len(dangling_errors) == 2
        assert any("evidence-002" in err for err in dangling_errors)
        assert any("evidence-999" in err for err in dangling_errors)


class TestScientificReportEvidence:
    """Test ScientificReport evidence list validation"""
    
    def test_report_evidence_list_valid(self):
        """GC-4: Report with evidence list is valid"""
        evidence = EvidenceObject(evidence_id="evidence-001")
        claim = Claim(
            claim_id="claim-001",
            statement="Test",
            claim_label=ClaimLabel.DERIVED,
            evidence_ids=["evidence-001"],
        )
        step = DerivationStep(step_id="step-001", claim_ids=["claim-001"])
        
        report = ScientificReport(claims=[claim], steps=[step], evidence=[evidence])
        assert len(report.evidence) == 1
        assert report.evidence[0].evidence_id == "evidence-001"
    
    def test_report_duplicate_evidence_ids_rejected(self):
        """GC-4: Duplicate evidence_ids in evidence list rejected"""
        evidence1 = EvidenceObject(evidence_id="evidence-001")
        evidence2 = EvidenceObject(evidence_id="evidence-001")
        
        with pytest.raises(ValueError, match="EVIDENCE_ID_COLLISION"):
            report = ScientificReport(
                claims=[],
                steps=[],
                evidence=[evidence1, evidence2],
            )
