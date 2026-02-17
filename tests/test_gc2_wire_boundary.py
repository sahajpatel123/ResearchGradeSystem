"""
GC-2 Wire Boundary Tests

Tests for strict wire-boundary parsing of claim labels from JSON/external sources.
Ensures parse_claim_label() is the single chokepoint for all ingestion.
"""

import json
import pytest
from pathlib import Path
from src.core.claim import ClaimLabel
from src.core.validators import parse_claim_label, validate_claim_label_from_dict


class TestParseClaimLabelWireBoundary:
    """Test the wire boundary parser parse_claim_label()"""
    
    def test_parse_claim_label_accepts_valid_labels(self):
        """Wire parser accepts all 4 valid labels"""
        assert parse_claim_label("DERIVED") == ClaimLabel.DERIVED
        assert parse_claim_label("COMPUTED") == ClaimLabel.COMPUTED
        assert parse_claim_label("CITED") == ClaimLabel.CITED
        assert parse_claim_label("SPECULATIVE") == ClaimLabel.SPECULATIVE
    
    def test_parse_claim_label_rejects_non_string_null(self):
        """Wire parser rejects None/null"""
        with pytest.raises(ValueError, match="Invalid ClaimLabel: None"):
            parse_claim_label(None)
    
    def test_parse_claim_label_rejects_non_string_bool(self):
        """Wire parser rejects boolean"""
        with pytest.raises(TypeError, match="expected string, got bool"):
            parse_claim_label(True)
        
        with pytest.raises(TypeError, match="expected string, got bool"):
            parse_claim_label(False)
    
    def test_parse_claim_label_rejects_non_string_number(self):
        """Wire parser rejects numbers"""
        with pytest.raises(TypeError, match="expected string, got number"):
            parse_claim_label(42)
        
        with pytest.raises(TypeError, match="expected string, got number"):
            parse_claim_label(3.14)
    
    def test_parse_claim_label_rejects_non_string_list(self):
        """Wire parser rejects lists"""
        with pytest.raises(TypeError, match="expected string, got list"):
            parse_claim_label(["DERIVED"])
        
        with pytest.raises(TypeError, match="expected string, got list"):
            parse_claim_label(["DERIVED", "COMPUTED"])
    
    def test_parse_claim_label_rejects_non_string_dict(self):
        """Wire parser rejects dicts"""
        with pytest.raises(TypeError, match="expected string, got dict"):
            parse_claim_label({"label": "DERIVED"})
    
    def test_parse_claim_label_rejects_empty_string(self):
        """Wire parser rejects empty string"""
        with pytest.raises(ValueError, match="Invalid ClaimLabel: empty string"):
            parse_claim_label("")
    
    def test_parse_claim_label_rejects_whitespace_leading(self):
        """Wire parser rejects leading whitespace"""
        with pytest.raises(ValueError, match="has invalid whitespace"):
            parse_claim_label(" DERIVED")
        
        with pytest.raises(ValueError, match="has invalid whitespace"):
            parse_claim_label("\tCOMPUTED")
    
    def test_parse_claim_label_rejects_whitespace_trailing(self):
        """Wire parser rejects trailing whitespace"""
        with pytest.raises(ValueError, match="has invalid whitespace"):
            parse_claim_label("CITED ")
        
        with pytest.raises(ValueError, match="has invalid whitespace"):
            parse_claim_label("SPECULATIVE\n")
    
    def test_parse_claim_label_rejects_lowercase(self):
        """Wire parser rejects lowercase"""
        with pytest.raises(ValueError, match="must be uppercase"):
            parse_claim_label("derived")
        
        with pytest.raises(ValueError, match="must be uppercase"):
            parse_claim_label("Computed")
    
    def test_parse_claim_label_rejects_invalid_label(self):
        """Wire parser rejects invalid label values"""
        with pytest.raises(ValueError, match="must be one of: DERIVED, COMPUTED, CITED, SPECULATIVE"):
            parse_claim_label("ASSUMED")
        
        with pytest.raises(ValueError, match="must be one of: DERIVED, COMPUTED, CITED, SPECULATIVE"):
            parse_claim_label("PROVEN")


class TestParseClaimLabelUnicodeInvisibles:
    """Test wire parser rejects unicode invisible characters"""
    
    def test_parse_claim_label_rejects_zwsp(self):
        """Wire parser rejects ZWSP (Zero-Width Space U+200B)"""
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("DERIVED\u200b")
        
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("\u200bDERIVED")
        
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("DER\u200bIVED")
    
    def test_parse_claim_label_rejects_nbsp(self):
        """Wire parser rejects NBSP (Non-Breaking Space U+00A0)"""
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("CITED\u00a0")
        
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("\u00a0CITED")
    
    def test_parse_claim_label_rejects_bom(self):
        """Wire parser rejects BOM (Byte Order Mark U+FEFF)"""
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("\ufeffCOMPUTED")
    
    def test_parse_claim_label_rejects_word_joiner(self):
        """Wire parser rejects Word Joiner (U+2060)"""
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("SPECULATIVE\u2060")
    
    def test_parse_claim_label_rejects_zwnj(self):
        """Wire parser rejects ZWNJ (Zero-Width Non-Joiner U+200C)"""
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("DERIVED\u200c")
    
    def test_parse_claim_label_rejects_zwj(self):
        """Wire parser rejects ZWJ (Zero-Width Joiner U+200D)"""
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            parse_claim_label("COMPUTED\u200d")


class TestParseClaimLabelUnicodeConfusables:
    """Test wire parser rejects unicode confusables (lookalike characters)"""
    
    def test_parse_claim_label_rejects_greek_epsilon(self):
        """Wire parser rejects Greek Epsilon (Ε U+0395) instead of ASCII E"""
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            parse_claim_label("DΕRIVED")  # Greek Epsilon instead of E
    
    def test_parse_claim_label_rejects_cyrillic_a(self):
        """Wire parser rejects Cyrillic A (А U+0410) instead of ASCII A"""
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            parse_claim_label("SPECULАTIVE")  # Cyrillic A instead of ASCII A
    
    def test_parse_claim_label_rejects_cyrillic_i(self):
        """Wire parser rejects Cyrillic I (І U+0406) instead of ASCII I"""
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            parse_claim_label("CІTED")  # Cyrillic I instead of ASCII I
    
    def test_parse_claim_label_rejects_fullwidth_d(self):
        """Wire parser rejects fullwidth D (Ｄ U+FF24)"""
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            parse_claim_label("ＤERIVED")
    
    def test_parse_claim_label_rejects_emoji_suffix(self):
        """Wire parser rejects emoji suffix"""
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            parse_claim_label("DERIVED✅")


class TestJSONIngestionUsesWireParser:
    """Test that JSON ingestion paths use parse_claim_label()"""
    
    def test_validate_claim_label_from_dict_uses_wire_parser(self):
        """validate_claim_label_from_dict must use parse_claim_label()"""
        # Valid case
        data = {"claim_label": "DERIVED"}
        assert validate_claim_label_from_dict(data) == ClaimLabel.DERIVED
        
        # Invalid case - should use wire parser's error messages
        data_zwsp = {"claim_label": "DERIVED\u200b"}
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            validate_claim_label_from_dict(data_zwsp)
        
        data_confusable = {"claim_label": "DΕRIVED"}
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            validate_claim_label_from_dict(data_confusable)
    
    def test_json_fixture_ingestion_enforces_wire_parser(self):
        """JSON fixture loading must enforce wire parser validation"""
        # This test verifies that when we load JSON fixtures,
        # the wire parser is enforced (tested via validate_claim_label_from_dict)
        
        # Test with a valid label
        valid_data = {"claim_label": "COMPUTED"}
        label = validate_claim_label_from_dict(valid_data)
        assert label == ClaimLabel.COMPUTED
        
        # Test with ZWSP - must fail at wire boundary
        zwsp_data = {"claim_label": "COMPUTED\u200b"}
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            validate_claim_label_from_dict(zwsp_data)


class TestWireBoundaryHighRiskFixtures:
    """Test high-risk unicode fixtures fail deterministically"""
    
    def test_gc2_invalid_label_zwsp_fixture(self):
        """ZWSP fixture must fail at wire boundary"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_zwsp.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_nbsp_fixture(self):
        """NBSP fixture must fail at wire boundary"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_nbsp.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="contains invisible unicode character"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_confusable_fixture(self):
        """Unicode confusable fixture must fail at wire boundary"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_confusable.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="contains non-ASCII characters"):
            validate_claim_label_from_dict(claim_data)


class TestWireBoundaryIsSingleChokepoint:
    """Verify parse_claim_label() is the single chokepoint"""
    
    def test_wire_parser_is_documented_as_chokepoint(self):
        """Wire parser docstring must identify it as single chokepoint"""
        assert "WIRE BOUNDARY PARSER" in parse_claim_label.__doc__
        assert "Single chokepoint" in parse_claim_label.__doc__ or "ONLY function" in parse_claim_label.__doc__
    
    def test_validate_from_dict_delegates_to_wire_parser(self):
        """validate_claim_label_from_dict must delegate to parse_claim_label"""
        # Test that error messages come from parse_claim_label, not custom logic
        data = {"claim_label": "DERIVED\u200b"}
        
        try:
            validate_claim_label_from_dict(data)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            # Error message should match parse_claim_label's format
            assert "Invalid ClaimLabel:" in str(e) or "contains invisible unicode character" in str(e)
