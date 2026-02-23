"""
Tests for ID Wire-Boundary Parsers (GC-6.1)

Tests strict validation of claim_id, step_id, tool_run_id, citation_id.
"""

import pytest
from src.core.id_parsers import (
    parse_claim_id,
    parse_step_id,
    parse_tool_run_id,
    parse_citation_id,
)


class TestParseClaimId:
    """Test parse_claim_id wire-boundary parser"""
    
    def test_parse_claim_id_valid(self):
        """GC-6.1: Valid claim_id passes"""
        assert parse_claim_id("claim-001") == "claim-001"
        assert parse_claim_id("claim_abc_123") == "claim_abc_123"
        assert parse_claim_id("CLAIM-XYZ") == "CLAIM-XYZ"
    
    def test_parse_claim_id_rejects_none(self):
        """GC-6.1: Reject None"""
        with pytest.raises(ValueError, match="Invalid claim_id: None"):
            parse_claim_id(None)
    
    def test_parse_claim_id_rejects_wrong_type(self):
        """GC-6.1: Reject non-string types"""
        with pytest.raises(TypeError, match="must be string"):
            parse_claim_id(123)
        
        with pytest.raises(TypeError, match="must be string"):
            parse_claim_id(["claim-001"])
    
    def test_parse_claim_id_rejects_empty(self):
        """GC-6.1: Reject empty string"""
        with pytest.raises(ValueError, match="empty string"):
            parse_claim_id("")
    
    def test_parse_claim_id_rejects_whitespace_variants(self):
        """GC-6.1: Reject leading/trailing whitespace (no trimming)"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id(" claim-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id("claim-001 ")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id("\tclaim-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id("claim-001\n")
    
    def test_parse_claim_id_rejects_invisibles_and_non_ascii(self):
        """GC-6.1: Reject unicode invisibles and non-ASCII"""
        # ZWSP (U+200B)
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u200B001")
        
        # NBSP (U+00A0)
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u00A0001")
        
        # BOM (U+FEFF)
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("\uFEFFclaim-001")
        
        # WJ (U+2060)
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u2060001")
        
        # ZWNJ (U+200C)
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u200C001")
        
        # ZWJ (U+200D)
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u200D001")
        
        # Non-ASCII characters
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_claim_id("claim-café")
        
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_claim_id("claim-™")


class TestParseStepId:
    """Test parse_step_id wire-boundary parser"""
    
    def test_parse_step_id_valid(self):
        """GC-6.1: Valid step_id passes"""
        assert parse_step_id("step-001") == "step-001"
        assert parse_step_id("step_abc_123") == "step_abc_123"
    
    def test_parse_step_id_rejects_whitespace_variants(self):
        """GC-6.1: Reject leading/trailing whitespace"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_step_id(" step-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_step_id("step-001 ")
    
    def test_parse_step_id_rejects_invisibles(self):
        """GC-6.1: Reject unicode invisibles"""
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_step_id("step\u200B001")


class TestParseToolRunId:
    """Test parse_tool_run_id wire-boundary parser"""
    
    def test_parse_tool_run_id_valid(self):
        """GC-6.1: Valid tool_run_id passes"""
        assert parse_tool_run_id("tool-run-001") == "tool-run-001"
        assert parse_tool_run_id("tool_abc_123") == "tool_abc_123"
    
    def test_parse_tool_run_id_rejects_whitespace_variants(self):
        """GC-6.1: Reject leading/trailing whitespace"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_tool_run_id(" tool-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_tool_run_id("tool-001\t")
    
    def test_parse_tool_run_id_rejects_invisibles(self):
        """GC-6.1: Reject unicode invisibles"""
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_tool_run_id("tool\u00A0001")


class TestParseCitationId:
    """Test parse_citation_id wire-boundary parser"""
    
    def test_parse_citation_id_valid(self):
        """GC-6.1: Valid citation_id passes"""
        assert parse_citation_id("citation-001") == "citation-001"
        assert parse_citation_id("doi:10.1234/example") == "doi:10.1234/example"
    
    def test_parse_citation_id_rejects_whitespace_variants(self):
        """GC-6.1: Reject leading/trailing whitespace"""
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_citation_id(" citation-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_citation_id("citation-001\n")
    
    def test_parse_citation_id_rejects_invisibles(self):
        """GC-6.1: Reject unicode invisibles"""
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_citation_id("citation\uFEFF001")
