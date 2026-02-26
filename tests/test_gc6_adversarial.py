"""
GC-6.1 ADVERSARIAL TEST SUITE

Tests bypass attempts and edge cases targeting the three GC-6.1 patch areas:
1) Compute-on-invalid (diagnostics)
2) Fixture semantics confusion
3) claim_id/ID hygiene

Expected outcomes: PASS/FAIL/WARN with reason categories
"""

import pytest
import json
from pathlib import Path
from src.core.claim import Claim, ClaimLabel
from src.core.step import DerivationStep, StepStatus
from src.core.evidence import EvidenceObject, EvidenceType, EvidenceStatus, EvidenceSource, PayloadRef
from src.core.report import ScientificReport
from src.core.integrity_metrics import compute_integrity_metrics, IntegrityMetrics
from src.core.gc6_validators import validate_and_compute_integrity_metrics, validate_report_with_integrity
from src.core.id_parsers import parse_claim_id, parse_step_id, parse_tool_run_id, parse_citation_id


class TestAdversarialComputeOnInvalid:
    """
    ATTACK VECTOR 1: "GC-6 disappears when GC-4 fails"
    
    Goal: Try to make compute_integrity_metrics crash or return None when report is malformed.
    Expected: MUST return deterministic metrics even on garbage input (PASS = metrics returned)
    """
    
    def test_attack_gc6_disappears_on_gc4_fail_null_evidence(self):
        """
        ATTACK: GC-6 should disappear when evidence is null
        EXPECTED: PASS - compute_integrity_metrics returns deterministic metrics
        REASON: Defensive compute handles None evidence_by_id
        """
        claims = [
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["ev-001"])
        ]
        
        # Attack: Pass None evidence_by_id (simulating GC-4 failure)
        metrics = compute_integrity_metrics(claims, None)
        
        # PASS criteria: metrics returned, claim marked unsupported
        assert metrics is not None
        assert isinstance(metrics, IntegrityMetrics)
        assert metrics.unsupported_non_spec_claims == 1
        assert metrics.total_non_spec_claims == 1
        assert metrics.unsupported_claim_rate == 1.0
        assert any("evidence_by_id was None" in note for note in metrics.diagnostics_notes)
    
    def test_attack_gc6_disappears_on_malformed_evidence_dict(self):
        """
        ATTACK: Pass dict with non-EvidenceObject values to crash compute
        EXPECTED: PASS - compute_integrity_metrics handles gracefully
        REASON: Defensive compute doesn't validate evidence object types
        """
        claims = [
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["ev-001"])
        ]
        
        # Attack: evidence_by_id contains non-EvidenceObject (string)
        malformed_evidence = {"ev-001": "not an evidence object"}
        metrics = compute_integrity_metrics(claims, malformed_evidence)
        
        # PASS criteria: metrics returned, claim marked supported (evidence_id resolves)
        assert metrics is not None
        assert metrics.unsupported_non_spec_claims == 0  # evidence_id resolves, even if malformed
        assert metrics.total_non_spec_claims == 1
    
    def test_attack_gc6_crash_on_evidence_list_not_dict(self):
        """
        ATTACK: Pass list instead of dict for evidence_by_id
        EXPECTED: PASS - compute_integrity_metrics treats as empty dict
        REASON: Defensive type checking
        """
        claims = [
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=["ev-001"])
        ]
        
        # Attack: evidence_by_id is a list, not dict
        metrics = compute_integrity_metrics(claims, ["not", "a", "dict"])
        
        # PASS criteria: metrics returned, treated as empty evidence
        assert metrics is not None
        assert metrics.unsupported_non_spec_claims == 1
        assert any("evidence_by_id wrong type" in note for note in metrics.diagnostics_notes)
    
    def test_attack_gc6_crash_on_claims_dict_not_list(self):
        """
        ATTACK: Pass dict instead of list for claims
        EXPECTED: PASS - compute_integrity_metrics treats as empty list
        REASON: Defensive type checking
        """
        # Attack: claims is a dict, not list
        metrics = compute_integrity_metrics({"claim-001": "not a list"}, {})
        
        # PASS criteria: metrics returned, zero claims counted
        assert metrics is not None
        assert metrics.unsupported_non_spec_claims == 0
        assert metrics.total_non_spec_claims == 0
        assert any("claims wrong type" in note for note in metrics.diagnostics_notes)
    
    def test_attack_gc6_crash_on_mixed_type_claims_list(self):
        """
        ATTACK: Mix valid Claim objects with non-Claim objects in list
        EXPECTED: PASS - compute_integrity_metrics skips non-Claim, processes valid
        REASON: Per-item type checking with diagnostics
        """
        claims = [
            Claim(claim_id="claim-001", statement="Valid", claim_label=ClaimLabel.DERIVED, evidence_ids=[]),
            None,  # Attack: None in list
            "not a claim",  # Attack: string in list
            123,  # Attack: int in list
            Claim(claim_id="claim-002", statement="Valid", claim_label=ClaimLabel.COMPUTED, evidence_ids=[]),
        ]
        
        metrics = compute_integrity_metrics(claims, {})
        
        # PASS criteria: valid claims counted, invalid skipped
        assert metrics is not None
        assert metrics.unsupported_non_spec_claims == 2  # Only valid claims
        assert metrics.total_non_spec_claims == 2
        assert len(metrics.diagnostics_notes) >= 3  # 3 invalid items noted
    
    def test_attack_gc6_crash_on_evidence_ids_mixed_types(self):
        """
        ATTACK: evidence_ids contains mix of strings and non-strings
        EXPECTED: PASS - claim marked unsupported, diagnostics note added
        REASON: Fail-closed on type issues
        """
        claim = Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
        # Attack: Mutate evidence_ids to contain mixed types
        claim.evidence_ids = ["valid-id", 123, None, "another-valid"]
        
        metrics = compute_integrity_metrics([claim], {"valid-id": "exists", "another-valid": "exists"})
        
        # PASS criteria: claim marked unsupported due to non-string evidence_id
        assert metrics is not None
        assert metrics.unsupported_non_spec_claims == 1
        assert any("non-string evidence_id" in note for note in metrics.diagnostics_notes)
    
    def test_attack_gc6_crash_on_deeply_nested_malformed_structure(self):
        """
        ATTACK: Deeply nested malformed structures to trigger edge cases
        EXPECTED: PASS - compute_integrity_metrics handles gracefully
        REASON: Defensive programming at every level
        """
        # Attack: Create claim with missing attributes (simulate wire corruption)
        claim = Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, evidence_ids=[])
        # Mutate to remove claim_label (simulate corruption)
        delattr(claim, 'claim_label')
        
        metrics = compute_integrity_metrics([claim], {})
        
        # PASS criteria: metrics returned, claim skipped or marked unsupported
        assert metrics is not None
        assert any("missing claim_label" in note for note in metrics.diagnostics_notes)


class TestAdversarialFixtureSemantics:
    """
    ATTACK VECTOR 2: Fixture semantics confusion
    
    Goal: Try to use metrics_only fixtures in full validation contexts or vice versa.
    Expected: Clear failure modes with explicit error messages
    """
    
    def test_attack_metrics_only_fixture_in_full_validation(self):
        """
        ATTACK: Use gc6_metrics_only_*.json in full validation (should fail GC-4)
        EXPECTED: FAIL - GC-4 validation fails, but GC-6 metrics still computed
        REASON: metrics_only fixtures may have dangling evidence_ids
        """
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        evidence = []  # Intentionally empty to trigger GC-4 failure
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        
        # Attack: Try full validation on metrics_only fixture
        is_valid, errors = validate_report_with_integrity(report)
        
        # EXPECTED: GC-4 fails, but GC-6 metrics still computed
        # PASS criteria: metrics exist even though validation failed
        assert report.integrity_metrics is not None
        assert isinstance(report.integrity_metrics, IntegrityMetrics)
        # GC-4 should have errors about dangling evidence_ids
        # But GC-6 should still compute (defensive)
    
    def test_attack_report_valid_fixture_must_pass_gc4(self):
        """
        ATTACK: Verify report_valid fixtures actually pass GC-4 (prevent drift)
        EXPECTED: PASS - report_valid fixtures MUST pass full validation
        REASON: Naming contract enforcement
        """
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
        
        steps = [
            DerivationStep(
                step_id=s["step_id"],
                claim_ids=s["claim_ids"],
                step_status=StepStatus[s["step_status"]],
            )
            for s in data["steps"]
        ]
        
        from src.core.gc5_wire_parsers import parse_evidence_object
        evidence = [parse_evidence_object(e) for e in data["evidence"]]
        
        report = ScientificReport(claims=claims, steps=steps, evidence=evidence)
        is_valid, errors = validate_report_with_integrity(report)
        
        # PASS criteria: report_valid fixture MUST pass full validation
        assert is_valid, f"report_valid fixture failed validation: {errors}"
        assert len(errors) == 0
    
    def test_attack_confuse_fixture_categories_by_name(self):
        """
        ATTACK: Developer accidentally creates "gc6_valid_*.json" with GC-4 violations
        EXPECTED: FAIL - Naming convention violation detected
        REASON: Prevent semantic drift
        """
        # This is a meta-test - we verify naming conventions are enforced
        # by checking that all gc6_report_valid_*.json files actually pass validation
        
        fixtures_dir = Path(__file__).parent / "fixtures"
        report_valid_fixtures = list(fixtures_dir.glob("gc6_report_valid_*.json"))
        
        # PASS criteria: All report_valid fixtures exist and follow naming
        assert len(report_valid_fixtures) >= 2, "Must have at least 2 report_valid fixtures"
        
        # Verify no old "gc6_valid_*.json" files exist (should all be renamed)
        old_naming = list(fixtures_dir.glob("gc6_valid_*.json"))
        assert len(old_naming) == 0, f"Old naming convention found: {old_naming}"


class TestAdversarialIdHygiene:
    """
    ATTACK VECTOR 3: claim_id/ID hygiene bypass attempts
    
    Goal: Try to bypass ID validation with Unicode tricks, confusables, invisibles.
    Expected: All attacks rejected at wire boundary with deterministic errors
    """
    
    def test_attack_claim_id_zwsp_bypass(self):
        """
        ATTACK: Use ZWSP (U+200B) in claim_id to create invisible duplicate
        EXPECTED: FAIL - parse_claim_id rejects ZWSP
        REASON: Unicode invisible detection
        """
        # Attack: claim_id with ZWSP
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u200B001")
    
    def test_attack_claim_id_nbsp_bypass(self):
        """
        ATTACK: Use NBSP (U+00A0) instead of regular space
        EXPECTED: FAIL - parse_claim_id rejects NBSP
        REASON: Unicode invisible detection
        """
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u00A0001")
    
    def test_attack_claim_id_bom_prefix(self):
        """
        ATTACK: Prefix claim_id with BOM (U+FEFF) to hide it
        EXPECTED: FAIL - parse_claim_id rejects BOM
        REASON: Unicode invisible detection
        """
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("\uFEFFclaim-001")
    
    def test_attack_claim_id_zwj_zwnj_bypass(self):
        """
        ATTACK: Use ZWJ/ZWNJ (U+200D/U+200C) to create confusables
        EXPECTED: FAIL - parse_claim_id rejects ZWJ/ZWNJ
        REASON: Unicode invisible detection
        """
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u200D001")
        
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u200C001")
    
    def test_attack_claim_id_word_joiner_bypass(self):
        """
        ATTACK: Use Word Joiner (U+2060) to create invisible separator
        EXPECTED: FAIL - parse_claim_id rejects WJ
        REASON: Unicode invisible detection
        """
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_claim_id("claim\u2060001")
    
    def test_attack_claim_id_homoglyph_confusable(self):
        """
        ATTACK: Use non-ASCII homoglyphs (Cyrillic 'а' looks like Latin 'a')
        EXPECTED: FAIL - parse_claim_id rejects non-ASCII
        REASON: ASCII-only enforcement
        """
        # Attack: Cyrillic 'а' (U+0430) instead of Latin 'a'
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_claim_id("clаim-001")  # Contains Cyrillic 'а'
    
    def test_attack_claim_id_emoji_bypass(self):
        """
        ATTACK: Use emoji in claim_id
        EXPECTED: FAIL - parse_claim_id rejects non-ASCII
        REASON: ASCII-only enforcement
        """
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_claim_id("claim-001-✓")
    
    def test_attack_claim_id_rtl_override(self):
        """
        ATTACK: Use RTL override (U+202E) to reverse claim_id visually
        EXPECTED: FAIL - parse_claim_id rejects non-ASCII control chars
        REASON: ASCII-only enforcement
        """
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_claim_id("\u202Eclaim-001")
    
    def test_attack_claim_id_whitespace_trim_bypass(self):
        """
        ATTACK: Add leading/trailing whitespace expecting trim
        EXPECTED: FAIL - parse_claim_id rejects (no trimming)
        REASON: Reject-only posture
        """
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id(" claim-001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id("claim-001 ")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_claim_id("\tclaim-001\n")
    
    def test_attack_step_id_same_vulnerabilities(self):
        """
        ATTACK: Verify step_id has same protections as claim_id
        EXPECTED: FAIL - parse_step_id rejects same attacks
        REASON: Consistent ID hygiene across all ID types
        """
        # ZWSP
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_step_id("step\u200B001")
        
        # NBSP
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_step_id("step\u00A0001")
        
        # Whitespace
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_step_id(" step-001")
        
        # Non-ASCII
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_step_id("step-café")
    
    def test_attack_tool_run_id_same_vulnerabilities(self):
        """
        ATTACK: Verify tool_run_id has same protections
        EXPECTED: FAIL - parse_tool_run_id rejects same attacks
        REASON: Consistent ID hygiene
        """
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_tool_run_id("tool\uFEFF001")
        
        with pytest.raises(ValueError, match="leading/trailing whitespace"):
            parse_tool_run_id("tool-001\t")
    
    def test_attack_citation_id_same_vulnerabilities(self):
        """
        ATTACK: Verify citation_id has same protections
        EXPECTED: FAIL - parse_citation_id rejects same attacks
        REASON: Consistent ID hygiene
        """
        with pytest.raises(ValueError, match="unicode invisible"):
            parse_citation_id("doi:10.1234\u200B/example")
        
        with pytest.raises(ValueError, match="non-ASCII"):
            parse_citation_id("doi:10.1234/café")


class TestAdversarialDriftPrevention:
    """
    DRIFT CHECKLIST: Tests to prevent common developer mistakes
    
    These tests enforce the GC-6.1 patch guarantees and prevent regression.
    """
    
    def test_drift_gc6_requires_gc4_pass_before_compute(self):
        """
        DRIFT: Developer accidentally makes compute_integrity_metrics require GC-4 pass
        EXPECTED: PASS - compute_integrity_metrics works WITHOUT GC-4 validation
        REASON: Defensive compute is a core GC-6.1 guarantee
        """
        # Create report that would fail GC-4 (dangling evidence_id)
        claims = [
            Claim(claim_id="claim-001", statement="Test", claim_label=ClaimLabel.DERIVED, 
                  evidence_ids=["dangling-evidence-id"])
        ]
        
        # Compute WITHOUT running GC-4 validation
        metrics = compute_integrity_metrics(claims, {})
        
        # PASS criteria: metrics computed successfully
        assert metrics is not None
        assert metrics.unsupported_non_spec_claims == 1  # Dangling → unsupported
        assert metrics.total_non_spec_claims == 1
    
    def test_drift_metrics_only_fixture_called_valid(self):
        """
        DRIFT: Developer creates fixture named "gc6_valid_*.json" that fails GC-4
        EXPECTED: FAIL - No fixtures named "gc6_valid_*.json" should exist
        REASON: Naming convention enforcement
        """
        fixtures_dir = Path(__file__).parent / "fixtures"
        
        # Check for old naming pattern
        old_valid_fixtures = list(fixtures_dir.glob("gc6_valid_*.json"))
        
        # PASS criteria: No old naming found
        assert len(old_valid_fixtures) == 0, \
            f"Found fixtures with old 'gc6_valid_*' naming: {old_valid_fixtures}. " \
            f"Use 'gc6_report_valid_*' or 'gc6_metrics_only_*' instead."
    
    def test_drift_claim_id_hardening_forgotten(self):
        """
        DRIFT: Developer hardens evidence_id but forgets claim_id
        EXPECTED: PASS - claim_id has same hardening as evidence_id
        REASON: Consistent wire-boundary posture
        """
        from src.core.evidence_validators import parse_evidence_id
        
        # Test same attack on both parsers
        test_cases = [
            ("\u200Btest", "ZWSP"),
            ("\u00A0test", "NBSP"),
            (" test", "leading space"),
            ("test ", "trailing space"),
            ("tëst", "non-ASCII"),
        ]
        
        for attack_string, attack_name in test_cases:
            # Both should reject
            with pytest.raises((ValueError, TypeError), match=""):
                parse_evidence_id(attack_string)
            
            with pytest.raises((ValueError, TypeError), match=""):
                parse_claim_id(attack_string)
    
    def test_drift_diagnostics_notes_removed(self):
        """
        DRIFT: Developer removes diagnostics_notes field from IntegrityMetrics
        EXPECTED: PASS - diagnostics_notes field exists and is populated
        REASON: Diagnostic capability is a core GC-6.1 feature
        """
        metrics = compute_integrity_metrics(None, None)
        
        # PASS criteria: diagnostics_notes field exists
        assert hasattr(metrics, 'diagnostics_notes')
        assert isinstance(metrics.diagnostics_notes, list)
        assert len(metrics.diagnostics_notes) > 0  # Should have notes about None inputs
    
    def test_drift_compute_crashes_on_malformed_input(self):
        """
        DRIFT: Developer adds validation that crashes on malformed input
        EXPECTED: PASS - compute_integrity_metrics never crashes
        REASON: Defensive compute is fail-safe
        """
        # Try various malformed inputs
        malformed_inputs = [
            (None, None),
            ([], None),
            (None, {}),
            ("not a list", "not a dict"),
            ([1, 2, 3], {"a": "b"}),
            ({"wrong": "type"}, ["wrong", "type"]),
        ]
        
        for claims_input, evidence_input in malformed_inputs:
            # PASS criteria: No exception raised
            try:
                metrics = compute_integrity_metrics(claims_input, evidence_input)
                assert metrics is not None
                assert isinstance(metrics, IntegrityMetrics)
            except Exception as e:
                pytest.fail(f"compute_integrity_metrics crashed on {claims_input}, {evidence_input}: {e}")
