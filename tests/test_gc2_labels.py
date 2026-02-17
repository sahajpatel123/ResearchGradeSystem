"""
GC-2 Claim Label Validation Tests

Tests enforce strict validation per GC-2:
- EXACTLY 4 labels: DERIVED, COMPUTED, CITED, SPECULATIVE
- Case-sensitive, exact ASCII strings
- No whitespace variants, no lowercase, no lists
"""

import json
import pytest
from pathlib import Path
from src.core.claim import Claim, ClaimLabel
from src.core.validators import validate_claim_label_string, validate_claim_label_from_dict


class TestClaimLabelEnum:
    
    def test_claim_label_enum_allows_only_four(self):
        """GC-2: Enum must have exactly 4 labels"""
        labels = list(ClaimLabel)
        assert len(labels) == 4
        
        label_values = {label.value for label in labels}
        assert label_values == {"DERIVED", "COMPUTED", "CITED", "SPECULATIVE"}
    
    def test_claim_label_enum_case_sensitive(self):
        """GC-2: Labels are case-sensitive"""
        assert ClaimLabel.DERIVED.value == "DERIVED"
        assert ClaimLabel.COMPUTED.value == "COMPUTED"
        assert ClaimLabel.CITED.value == "CITED"
        assert ClaimLabel.SPECULATIVE.value == "SPECULATIVE"
        
        assert ClaimLabel.DERIVED.value != "derived"
        assert ClaimLabel.COMPUTED.value != "Computed"
    
    def test_claim_label_enum_exact_strings(self):
        """GC-2: Labels must be exact strings (no whitespace)"""
        for label in ClaimLabel:
            assert label.value == label.value.strip()
            assert " " not in label.value


class TestClaimLabelValidation:
    
    def test_claim_label_missing_fails(self):
        """GC-2: Missing label must fail"""
        with pytest.raises(ValueError, match="Claim label is required"):
            Claim(
                claim_id="test-001",
                statement="Test statement",
                claim_label=None,
            )
    
    def test_claim_label_invalid_value_fails(self):
        """GC-2: Invalid label value must fail"""
        with pytest.raises(ValueError, match="Invalid claim label: 'ASSUMED'"):
            validate_claim_label_string("ASSUMED")
        
        with pytest.raises(ValueError, match="Invalid claim label: 'PROVEN'"):
            validate_claim_label_string("PROVEN")
        
        with pytest.raises(ValueError, match="Invalid claim label: 'VERIFIED'"):
            validate_claim_label_string("VERIFIED")
    
    def test_claim_label_trailing_space_fails(self):
        """GC-2: Trailing space must fail"""
        with pytest.raises(ValueError, match="invalid whitespace: 'DERIVED '"):
            validate_claim_label_string("DERIVED ")
        
        with pytest.raises(ValueError, match="invalid whitespace: 'COMPUTED '"):
            validate_claim_label_string("COMPUTED ")
    
    def test_claim_label_leading_space_fails(self):
        """GC-2: Leading space must fail"""
        with pytest.raises(ValueError, match="invalid whitespace: ' CITED'"):
            validate_claim_label_string(" CITED")
        
        with pytest.raises(ValueError, match="invalid whitespace: ' SPECULATIVE'"):
            validate_claim_label_string(" SPECULATIVE")
    
    def test_claim_label_lowercase_fails(self):
        """GC-2: Lowercase must fail"""
        with pytest.raises(ValueError, match="must be uppercase: got 'derived'"):
            validate_claim_label_string("derived")
        
        with pytest.raises(ValueError, match="must be uppercase: got 'computed'"):
            validate_claim_label_string("computed")
        
        with pytest.raises(ValueError, match="must be uppercase: got 'cited'"):
            validate_claim_label_string("cited")
        
        with pytest.raises(ValueError, match="must be uppercase: got 'speculative'"):
            validate_claim_label_string("speculative")
    
    def test_claim_label_mixed_case_fails(self):
        """GC-2: Mixed case must fail"""
        with pytest.raises(ValueError, match="must be uppercase: got 'Derived'"):
            validate_claim_label_string("Derived")
        
        with pytest.raises(ValueError, match="must be uppercase: got 'Computed'"):
            validate_claim_label_string("Computed")
    
    def test_claim_label_list_type_fails(self):
        """GC-2: List type must fail"""
        with pytest.raises(TypeError, match="cannot be a list"):
            validate_claim_label_string(["DERIVED"])
        
        with pytest.raises(TypeError, match="cannot be a list"):
            validate_claim_label_string(["DERIVED", "COMPUTED"])
    
    def test_claim_label_dict_type_fails(self):
        """GC-2: Dict type must fail"""
        with pytest.raises(TypeError, match="cannot be a dict"):
            validate_claim_label_string({"label": "DERIVED"})
    
    def test_claim_label_null_fails(self):
        """GC-2: Null/None must fail"""
        with pytest.raises(ValueError, match="cannot be None"):
            validate_claim_label_string(None)
    
    def test_claim_label_empty_string_fails(self):
        """GC-2: Empty string must fail"""
        with pytest.raises(ValueError, match="cannot be empty string"):
            validate_claim_label_string("")
    
    def test_claim_label_integer_type_fails(self):
        """GC-2: Integer type must fail"""
        with pytest.raises(TypeError, match="must be string, got int"):
            validate_claim_label_string(42)
    
    def test_claim_label_valid_accepts_all_four(self):
        """GC-2: All 4 valid labels must be accepted"""
        assert validate_claim_label_string("DERIVED") == ClaimLabel.DERIVED
        assert validate_claim_label_string("COMPUTED") == ClaimLabel.COMPUTED
        assert validate_claim_label_string("CITED") == ClaimLabel.CITED
        assert validate_claim_label_string("SPECULATIVE") == ClaimLabel.SPECULATIVE


class TestClaimLabelFromDict:
    
    def test_claim_label_from_dict_missing_key_fails(self):
        """GC-2: Missing 'claim_label' key must fail"""
        data = {"statement": "Test"}
        with pytest.raises(KeyError, match="Missing required field 'claim_label'"):
            validate_claim_label_from_dict(data)
    
    def test_claim_label_from_dict_valid(self):
        """GC-2: Valid label in dict must succeed"""
        data = {"claim_label": "DERIVED"}
        assert validate_claim_label_from_dict(data) == ClaimLabel.DERIVED
        
        data = {"claim_label": "COMPUTED"}
        assert validate_claim_label_from_dict(data) == ClaimLabel.COMPUTED


class TestGC2Fixtures:
    
    def test_gc2_valid_all_labels_fixture(self):
        """GC-2: Valid fixture with all 4 labels"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_valid_all_labels.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        assert len(data["claims"]) == 4
        
        labels_found = set()
        for claim_data in data["claims"]:
            label = validate_claim_label_from_dict(claim_data)
            labels_found.add(label)
        
        assert labels_found == {
            ClaimLabel.DERIVED,
            ClaimLabel.COMPUTED,
            ClaimLabel.CITED,
            ClaimLabel.SPECULATIVE
        }
    
    def test_gc2_invalid_label_assumed_fixture(self):
        """GC-2: Invalid label 'ASSUMED' must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_assumed.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="Invalid ClaimLabel: 'ASSUMED'"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_lowercase_fixture(self):
        """GC-2: Lowercase label must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_lowercase.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="must be uppercase"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_trailing_space_fixture(self):
        """GC-2: Trailing space must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_trailing_space.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="has invalid whitespace"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_leading_space_fixture(self):
        """GC-2: Leading space must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_leading_space.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="has invalid whitespace"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_null_fixture(self):
        """GC-2: Null label must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_null.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="Invalid ClaimLabel: None"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_empty_fixture(self):
        """GC-2: Empty string label must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_empty.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(ValueError, match="Invalid ClaimLabel: empty string"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_list_fixture(self):
        """GC-2: List label must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_list.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(TypeError, match="expected string, got list"):
            validate_claim_label_from_dict(claim_data)
    
    def test_gc2_invalid_label_missing_fixture(self):
        """GC-2: Missing label field must fail"""
        fixture_path = Path(__file__).parent / "fixtures" / "gc2_invalid_label_missing.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        claim_data = data["claims"][0]
        with pytest.raises(KeyError, match="Missing required field 'claim_label'"):
            validate_claim_label_from_dict(claim_data)


class TestClaimConstructionWithLabels:
    
    def test_claim_create_with_all_valid_labels(self):
        """GC-2: Claim.create must work with all 4 valid labels"""
        claim1 = Claim.create("Statement 1", ClaimLabel.DERIVED)
        assert claim1.claim_label == ClaimLabel.DERIVED
        
        claim2 = Claim.create("Statement 2", ClaimLabel.COMPUTED)
        assert claim2.claim_label == ClaimLabel.COMPUTED
        
        claim3 = Claim.create("Statement 3", ClaimLabel.CITED)
        assert claim3.claim_label == ClaimLabel.CITED
        
        claim4 = Claim.create("Statement 4", ClaimLabel.SPECULATIVE)
        assert claim4.claim_label == ClaimLabel.SPECULATIVE
    
    def test_claim_direct_construction_with_invalid_type(self):
        """GC-2: Direct construction with non-enum type must fail"""
        with pytest.raises(TypeError, match="must be ClaimLabel enum, got str"):
            Claim(
                claim_id="test-001",
                statement="Test",
                claim_label="DERIVED",  # String instead of enum
            )
    
    def test_claim_direct_construction_with_integer(self):
        """GC-2: Direct construction with integer must fail"""
        with pytest.raises(TypeError, match="must be ClaimLabel enum, got int"):
            Claim(
                claim_id="test-001",
                statement="Test",
                claim_label=1,
            )
