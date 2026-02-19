"""
GC-5 Evidence Object Schema Tests

Comprehensive tests for strict evidence validation, wire-boundary parsing, and fixtures.
"""

import json
import pytest
from pathlib import Path
from src.core.evidence import (
    EvidenceObject,
    EvidenceType,
    EvidenceStatus,
    IndeterminateReason,
    EvidenceSource,
    PayloadRef,
)
from src.core.gc5_wire_parsers import (
    parse_evidence_id,
    parse_evidence_type,
    parse_evidence_status,
    parse_indeterminate_reason,
    parse_evidence_source,
    parse_payload_ref,
    parse_evidence_object,
)
from src.core.claim import Claim, ClaimLabel
from src.core.step import DerivationStep, StepStatus
from src.core.report import ScientificReport


class TestEvidenceEnums:
    """Test GC-5 strict enums"""
    
    def test_evidence_type_enum_values(self):
        """GC-5: EvidenceType has exactly 3 values"""
        assert EvidenceType.DERIVATION.value == "derivation"
        assert EvidenceType.COMPUTATION.value == "computation"
        assert EvidenceType.CITATION.value == "citation"
        assert len(EvidenceType) == 3
    
    def test_evidence_status_enum_values(self):
        """GC-5: EvidenceStatus has exactly 3 values"""
        assert EvidenceStatus.PASS.value == "pass"
        assert EvidenceStatus.FAIL.value == "fail"
        assert EvidenceStatus.INDETERMINATE.value == "indeterminate"
        assert len(EvidenceStatus) == 3
    
    def test_indeterminate_reason_enum_values(self):
        """GC-5: IndeterminateReason has exactly 6 tight values"""
        assert IndeterminateReason.UNSUPPORTED.value == "unsupported"
        assert IndeterminateReason.DOMAIN.value == "domain"
        assert IndeterminateReason.SINGULARITY.value == "singularity"
        assert IndeterminateReason.TIMEOUT.value == "timeout"
        assert IndeterminateReason.MISSING_BC_IC.value == "missing_bc_ic"
        assert IndeterminateReason.TOOL_ERROR.value == "tool_error"
        assert len(IndeterminateReason) == 6


class TestEvidenceSource:
    """Test GC-5 EvidenceSource tagged union"""
    
    def test_evidence_source_valid_step_id(self):
        """GC-5: Valid EvidenceSource with step_id"""
        source = EvidenceSource(kind="step_id", value="step-001")
        assert source.kind == "step_id"
        assert source.value == "step-001"
    
    def test_evidence_source_valid_tool_run_id(self):
        """GC-5: Valid EvidenceSource with tool_run_id"""
        source = EvidenceSource(kind="tool_run_id", value="tool-run-12345")
        assert source.kind == "tool_run_id"
        assert source.value == "tool-run-12345"
    
    def test_evidence_source_valid_citation_id(self):
        """GC-5: Valid EvidenceSource with citation_id"""
        source = EvidenceSource(kind="citation_id", value="einstein-1905")
        assert source.kind == "citation_id"
        assert source.value == "einstein-1905"
    
    def test_evidence_source_rejects_invalid_kind(self):
        """GC-5: EvidenceSource rejects invalid kind"""
        with pytest.raises(ValueError, match="invalid kind"):
            EvidenceSource(kind="invalid_kind", value="test")
    
    def test_evidence_source_rejects_empty_value(self):
        """GC-5: EvidenceSource rejects empty value"""
        with pytest.raises(ValueError, match="value must be non-empty"):
            EvidenceSource(kind="step_id", value="")
    
    def test_evidence_source_rejects_whitespace_value(self):
        """GC-5: EvidenceSource rejects whitespace variants (NO TRIMMING)"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            EvidenceSource(kind="step_id", value=" step-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            EvidenceSource(kind="step_id", value="step-001 ")


class TestPayloadRef:
    """Test GC-5 PayloadRef tagged union"""
    
    def test_payload_ref_valid_log_id(self):
        """GC-5: Valid PayloadRef with log_id"""
        ref = PayloadRef(kind="log_id", value="log-001")
        assert ref.kind == "log_id"
        assert ref.value == "log-001"
    
    def test_payload_ref_valid_snippet_ref(self):
        """GC-5: Valid PayloadRef with snippet_ref"""
        ref = PayloadRef(kind="snippet_ref", value="snippet-001")
        assert ref.kind == "snippet_ref"
        assert ref.value == "snippet-001"
    
    def test_payload_ref_valid_expression_ref(self):
        """GC-5: Valid PayloadRef with expression_ref"""
        ref = PayloadRef(kind="expression_ref", value="expr-001")
        assert ref.kind == "expression_ref"
        assert ref.value == "expr-001"
    
    def test_payload_ref_rejects_invalid_kind(self):
        """GC-5: PayloadRef rejects invalid kind"""
        with pytest.raises(ValueError, match="invalid kind"):
            PayloadRef(kind="invalid_kind", value="test")
    
    def test_payload_ref_rejects_empty_value(self):
        """GC-5: PayloadRef rejects empty value"""
        with pytest.raises(ValueError, match="value must be non-empty"):
            PayloadRef(kind="log_id", value="")
    
    def test_payload_ref_rejects_whitespace_value(self):
        """GC-5: PayloadRef rejects whitespace variants (NO TRIMMING)"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            PayloadRef(kind="log_id", value=" log-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            PayloadRef(kind="log_id", value="log-001 ")


class TestEvidenceObjectSchema:
    """Test GC-5 EvidenceObject schema validation"""
    
    def test_evidence_object_valid_derivation(self):
        """GC-5: Valid derivation evidence object"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        assert evidence.evidence_id == "evidence-001"
        assert evidence.evidence_type == EvidenceType.DERIVATION
        assert evidence.source.kind == "step_id"
        assert evidence.status == EvidenceStatus.PASS
    
    def test_evidence_object_valid_computation(self):
        """GC-5: Valid computation evidence object"""
        evidence = EvidenceObject(
            evidence_id="evidence-002",
            evidence_type=EvidenceType.COMPUTATION,
            source=EvidenceSource(kind="tool_run_id", value="tool-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="snippet_ref", value="snippet-001"),
        )
        assert evidence.evidence_type == EvidenceType.COMPUTATION
        assert evidence.source.kind == "tool_run_id"
    
    def test_evidence_object_valid_citation(self):
        """GC-5: Valid citation evidence object"""
        evidence = EvidenceObject(
            evidence_id="evidence-003",
            evidence_type=EvidenceType.CITATION,
            source=EvidenceSource(kind="citation_id", value="einstein-1905"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="expression_ref", value="expr-001"),
        )
        assert evidence.evidence_type == EvidenceType.CITATION
        assert evidence.source.kind == "citation_id"
    
    def test_evidence_object_valid_indeterminate_with_reason(self):
        """GC-5: Valid indeterminate evidence with status_reason"""
        evidence = EvidenceObject(
            evidence_id="evidence-004",
            evidence_type=EvidenceType.COMPUTATION,
            source=EvidenceSource(kind="tool_run_id", value="tool-001"),
            status=EvidenceStatus.INDETERMINATE,
            status_reason=IndeterminateReason.TIMEOUT,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        assert evidence.status == EvidenceStatus.INDETERMINATE
        assert evidence.status_reason == IndeterminateReason.TIMEOUT
    
    def test_evidence_object_alignment_derivation_step_id(self):
        """GC-5: Alignment rule - derivation requires step_id"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        assert evidence.evidence_type == EvidenceType.DERIVATION
        assert evidence.source.kind == "step_id"
    
    def test_evidence_object_alignment_computation_tool_run_id(self):
        """GC-5: Alignment rule - computation requires tool_run_id"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.COMPUTATION,
            source=EvidenceSource(kind="tool_run_id", value="tool-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        assert evidence.evidence_type == EvidenceType.COMPUTATION
        assert evidence.source.kind == "tool_run_id"
    
    def test_evidence_object_alignment_citation_citation_id(self):
        """GC-5: Alignment rule - citation requires citation_id"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.CITATION,
            source=EvidenceSource(kind="citation_id", value="cite-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
        )
        assert evidence.evidence_type == EvidenceType.CITATION
        assert evidence.source.kind == "citation_id"
    
    def test_evidence_object_rejects_alignment_mismatch(self):
        """GC-5: EVIDENCE_SOURCE_KIND_MISMATCH - derivation with tool_run_id"""
        with pytest.raises(ValueError, match="EVIDENCE_SOURCE_KIND_MISMATCH"):
            EvidenceObject(
                evidence_id="evidence-001",
                evidence_type=EvidenceType.DERIVATION,
                source=EvidenceSource(kind="tool_run_id", value="tool-001"),
                status=EvidenceStatus.PASS,
                payload_ref=PayloadRef(kind="log_id", value="log-001"),
            )
    
    def test_evidence_object_indeterminate_requires_reason(self):
        """GC-5: INDETERMINATE_MISSING_REASON - indeterminate without status_reason"""
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            EvidenceObject(
                evidence_id="evidence-001",
                evidence_type=EvidenceType.COMPUTATION,
                source=EvidenceSource(kind="tool_run_id", value="tool-001"),
                status=EvidenceStatus.INDETERMINATE,
                status_reason=None,
                payload_ref=PayloadRef(kind="log_id", value="log-001"),
            )
    
    def test_evidence_object_rejects_status_reason_when_not_indeterminate(self):
        """GC-5: status_reason present when status is not indeterminate"""
        with pytest.raises(ValueError, match="status_reason present when status=pass"):
            EvidenceObject(
                evidence_id="evidence-001",
                evidence_type=EvidenceType.DERIVATION,
                source=EvidenceSource(kind="step_id", value="step-001"),
                status=EvidenceStatus.PASS,
                status_reason=IndeterminateReason.TIMEOUT,
                payload_ref=PayloadRef(kind="log_id", value="log-001"),
            )
    
    def test_evidence_object_valid_notes(self):
        """GC-5: Valid notes field"""
        evidence = EvidenceObject(
            evidence_id="evidence-001",
            evidence_type=EvidenceType.DERIVATION,
            source=EvidenceSource(kind="step_id", value="step-001"),
            status=EvidenceStatus.PASS,
            payload_ref=PayloadRef(kind="log_id", value="log-001"),
            notes="This is a valid note",
        )
        assert evidence.notes == "This is a valid note"
    
    def test_evidence_object_rejects_empty_notes(self):
        """GC-5: NOTES_EMPTY - notes present but empty after trim"""
        with pytest.raises(ValueError, match="NOTES_EMPTY"):
            EvidenceObject(
                evidence_id="evidence-001",
                evidence_type=EvidenceType.DERIVATION,
                source=EvidenceSource(kind="step_id", value="step-001"),
                status=EvidenceStatus.PASS,
                payload_ref=PayloadRef(kind="log_id", value="log-001"),
                notes="   ",
            )
    
    def test_evidence_object_rejects_whitespace_evidence_id(self):
        """GC-5: evidence_id with whitespace variants rejected (NO TRIMMING)"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            EvidenceObject(
                evidence_id=" evidence-001",
                evidence_type=EvidenceType.DERIVATION,
                source=EvidenceSource(kind="step_id", value="step-001"),
                status=EvidenceStatus.PASS,
                payload_ref=PayloadRef(kind="log_id", value="log-001"),
            )


class TestWireBoundaryParsers:
    """Test GC-5 wire-boundary parsers"""
    
    def test_parse_evidence_id_valid(self):
        """GC-5: parse_evidence_id accepts valid ID"""
        assert parse_evidence_id("evidence-001") == "evidence-001"
        assert parse_evidence_id("evidence-123-abc") == "evidence-123-abc"
    
    def test_parse_evidence_id_rejects_whitespace(self):
        """GC-5: parse_evidence_id rejects whitespace variants (NO TRIMMING)"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id(" evidence-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_id("evidence-001 ")
    
    def test_parse_evidence_id_rejects_internal_whitespace(self):
        """GC-5: parse_evidence_id rejects internal whitespace"""
        with pytest.raises(ValueError, match="internal whitespace"):
            parse_evidence_id("evidence 001")
    
    def test_parse_evidence_id_rejects_zwsp(self):
        """GC-5: parse_evidence_id rejects ZWSP (invisible unicode)"""
        with pytest.raises(ValueError, match="invisible unicode character"):
            parse_evidence_id("evidence-001\u200b")
    
    def test_parse_evidence_id_rejects_non_ascii(self):
        """GC-5: parse_evidence_id rejects non-ASCII characters"""
        with pytest.raises(ValueError, match="non-ASCII characters"):
            parse_evidence_id("evidence-Ε01")  # Greek Epsilon
    
    def test_parse_evidence_type_valid(self):
        """GC-5: parse_evidence_type accepts valid types"""
        assert parse_evidence_type("derivation") == EvidenceType.DERIVATION
        assert parse_evidence_type("computation") == EvidenceType.COMPUTATION
        assert parse_evidence_type("citation") == EvidenceType.CITATION
    
    def test_parse_evidence_type_rejects_invalid(self):
        """GC-5: parse_evidence_type rejects invalid type (EVIDENCE_TYPE_INVALID)"""
        with pytest.raises(ValueError, match="EVIDENCE_TYPE_INVALID"):
            parse_evidence_type("invalid_type")
    
    def test_parse_evidence_type_case_sensitive(self):
        """GC-5: parse_evidence_type is case-sensitive"""
        with pytest.raises(ValueError, match="EVIDENCE_TYPE_INVALID"):
            parse_evidence_type("Derivation")
    
    def test_parse_evidence_status_valid(self):
        """GC-5: parse_evidence_status accepts valid statuses"""
        assert parse_evidence_status("pass") == EvidenceStatus.PASS
        assert parse_evidence_status("fail") == EvidenceStatus.FAIL
        assert parse_evidence_status("indeterminate") == EvidenceStatus.INDETERMINATE
    
    def test_parse_evidence_status_rejects_invalid(self):
        """GC-5: parse_evidence_status rejects invalid status (EVIDENCE_STATUS_INVALID)"""
        with pytest.raises(ValueError, match="EVIDENCE_STATUS_INVALID"):
            parse_evidence_status("invalid_status")
    
    def test_parse_indeterminate_reason_valid(self):
        """GC-5: parse_indeterminate_reason accepts valid reasons"""
        assert parse_indeterminate_reason("unsupported") == IndeterminateReason.UNSUPPORTED
        assert parse_indeterminate_reason("timeout") == IndeterminateReason.TIMEOUT
        assert parse_indeterminate_reason("tool_error") == IndeterminateReason.TOOL_ERROR
    
    def test_parse_indeterminate_reason_rejects_invalid(self):
        """GC-5: parse_indeterminate_reason rejects invalid reason (INDETERMINATE_REASON_INVALID)"""
        with pytest.raises(ValueError, match="INDETERMINATE_REASON_INVALID"):
            parse_indeterminate_reason("invalid_reason")
    
    def test_parse_evidence_source_valid(self):
        """GC-5: parse_evidence_source accepts valid tagged union"""
        source = parse_evidence_source({"kind": "step_id", "value": "step-001"})
        assert source.kind == "step_id"
        assert source.value == "step-001"
    
    def test_parse_evidence_source_rejects_invalid_kind(self):
        """GC-5: parse_evidence_source rejects invalid kind (SOURCE_KIND_INVALID)"""
        with pytest.raises(ValueError, match="SOURCE_KIND_INVALID"):
            parse_evidence_source({"kind": "invalid_kind", "value": "test"})
    
    def test_parse_evidence_source_rejects_whitespace_value(self):
        """GC-5: parse_evidence_source rejects whitespace in value (SOURCE_VALUE_INVALID)"""
        with pytest.raises(ValueError, match="SOURCE_VALUE_INVALID"):
            parse_evidence_source({"kind": "step_id", "value": " step-001"})
    
    def test_parse_payload_ref_valid(self):
        """GC-5: parse_payload_ref accepts valid tagged union"""
        ref = parse_payload_ref({"kind": "log_id", "value": "log-001"})
        assert ref.kind == "log_id"
        assert ref.value == "log-001"
    
    def test_parse_payload_ref_rejects_invalid_kind(self):
        """GC-5: parse_payload_ref rejects invalid kind (PAYLOAD_REF_KIND_INVALID)"""
        with pytest.raises(ValueError, match="PAYLOAD_REF_KIND_INVALID"):
            parse_payload_ref({"kind": "invalid_kind", "value": "test"})
    
    def test_parse_payload_ref_rejects_whitespace_value(self):
        """GC-5: parse_payload_ref rejects whitespace in value (PAYLOAD_REF_VALUE_INVALID)"""
        with pytest.raises(ValueError, match="PAYLOAD_REF_VALUE_INVALID"):
            parse_payload_ref({"kind": "log_id", "value": "log-001 "})
    
    def test_parse_evidence_object_valid(self):
        """GC-5: parse_evidence_object accepts valid complete object"""
        wire = {
            "evidence_id": "evidence-001",
            "evidence_type": "derivation",
            "source": {"kind": "step_id", "value": "step-001"},
            "status": "pass",
            "status_reason": None,
            "payload_ref": {"kind": "log_id", "value": "log-001"},
            "notes": None,
        }
        evidence = parse_evidence_object(wire)
        assert evidence.evidence_id == "evidence-001"
        assert evidence.evidence_type == EvidenceType.DERIVATION
        assert evidence.status == EvidenceStatus.PASS
    
    def test_parse_evidence_object_missing_field(self):
        """GC-5: parse_evidence_object rejects missing required field (EVIDENCE_MISSING_FIELD)"""
        wire = {
            "evidence_id": "evidence-001",
            "evidence_type": "derivation",
            "source": {"kind": "step_id", "value": "step-001"},
            "status": "pass",
            # Missing payload_ref
        }
        with pytest.raises(ValueError, match="EVIDENCE_MISSING_FIELD_PAYLOAD_REF"):
            parse_evidence_object(wire)


class TestGC5Fixtures:
    """Test GC-5 fixtures"""
    
    def test_gc5_valid_derivation_fixture(self):
        """GC-5: Valid derivation fixture loads and validates"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_valid_derivation.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # Parse evidence using wire parser
        evidence_data = data["evidence"][0]
        evidence = parse_evidence_object(evidence_data)
        
        assert evidence.evidence_type == EvidenceType.DERIVATION
        assert evidence.source.kind == "step_id"
        assert evidence.status == EvidenceStatus.PASS
    
    def test_gc5_valid_computation_fixture(self):
        """GC-5: Valid computation fixture loads and validates"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_valid_computation.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        evidence = parse_evidence_object(evidence_data)
        
        assert evidence.evidence_type == EvidenceType.COMPUTATION
        assert evidence.source.kind == "tool_run_id"
        assert evidence.status == EvidenceStatus.PASS
    
    def test_gc5_valid_citation_fixture(self):
        """GC-5: Valid citation fixture loads and validates"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_valid_citation.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        evidence = parse_evidence_object(evidence_data)
        
        assert evidence.evidence_type == EvidenceType.CITATION
        assert evidence.source.kind == "citation_id"
        assert evidence.status == EvidenceStatus.PASS
    
    def test_gc5_valid_indeterminate_fixture(self):
        """GC-5: Valid indeterminate fixture loads and validates"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_valid_indeterminate.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        evidence = parse_evidence_object(evidence_data)
        
        assert evidence.status == EvidenceStatus.INDETERMINATE
        assert evidence.status_reason == IndeterminateReason.TIMEOUT
    
    def test_gc5_invalid_evidence_type_fixture(self):
        """GC-5: Invalid evidence_type fixture fails with EVIDENCE_TYPE_INVALID"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_evidence_type.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="EVIDENCE_TYPE_INVALID"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_source_kind_mismatch_fixture(self):
        """GC-5: Source kind mismatch fixture fails with EVIDENCE_SOURCE_KIND_MISMATCH"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_source_kind_mismatch.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="EVIDENCE_SOURCE_KIND_MISMATCH"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_indeterminate_missing_reason_fixture(self):
        """GC-5: Indeterminate missing reason fixture fails with INDETERMINATE_MISSING_REASON"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_indeterminate_missing_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="INDETERMINATE_MISSING_REASON"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_status_reason_when_not_indeterminate_fixture(self):
        """GC-5: status_reason when not indeterminate fixture fails"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_status_reason_when_not_indeterminate.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="status_reason present when status=pass"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_missing_payload_ref_fixture(self):
        """GC-5: Missing payload_ref fixture fails with EVIDENCE_MISSING_FIELD_PAYLOAD_REF"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_missing_payload_ref.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="EVIDENCE_MISSING_FIELD_PAYLOAD_REF"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_notes_empty_fixture(self):
        """GC-5: Empty notes fixture fails with NOTES_EMPTY"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_notes_empty.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="NOTES_EMPTY"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_evidence_id_whitespace_fixture(self):
        """GC-5: evidence_id whitespace fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_evidence_id_whitespace.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_evidence_id_zwsp_fixture(self):
        """GC-5: evidence_id ZWSP fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_evidence_id_zwsp.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="invisible unicode character"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_evidence_id_internal_whitespace_fixture(self):
        """GC-5: evidence_id internal whitespace fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_evidence_id_internal_whitespace.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="internal whitespace"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_source_value_whitespace_fixture(self):
        """GC-5: source.value whitespace fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_source_value_whitespace.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="SOURCE_VALUE_INVALID"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_payload_ref_value_whitespace_fixture(self):
        """GC-5: payload_ref.value whitespace fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_payload_ref_value_whitespace.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="PAYLOAD_REF_VALUE_INVALID"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_source_kind_fixture(self):
        """GC-5: Invalid source.kind fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_source_kind.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="SOURCE_KIND_INVALID"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_payload_ref_kind_fixture(self):
        """GC-5: Invalid payload_ref.kind fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_payload_ref_kind.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="PAYLOAD_REF_KIND_INVALID"):
            parse_evidence_object(evidence_data)
    
    def test_gc5_invalid_indeterminate_reason_fixture(self):
        """GC-5: Invalid indeterminate_reason fixture fails at wire parsing"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc5_invalid_indeterminate_reason.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        evidence_data = data["evidence"][0]
        with pytest.raises(ValueError, match="INDETERMINATE_REASON_INVALID"):
            parse_evidence_object(evidence_data)
