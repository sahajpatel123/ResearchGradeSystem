import json
import pytest
from pathlib import Path
from src.core.claim import Claim, ClaimLabel
from src.core.integrity import finalization_check, compute_unsupported_claim_rate


class TestFixtures:
    
    def test_report_incomplete_valid_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "report_incomplete_valid.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        assert data["status"] == "INCOMPLETE"
        assert len(data["claims"]) == 2
        
        claims = []
        for claim_data in data["claims"]:
            claim = Claim(
                claim_id=claim_data["claim_id"],
                statement=claim_data["statement"],
                claim_label=ClaimLabel[claim_data["claim_label"]],
                step_id=claim_data["step_id"],
                evidence_ids=claim_data["evidence_ids"],
                claim_span=claim_data["claim_span"],
            )
            claims.append(claim)
        
        can_finalize, reasons = finalization_check(claims)
        assert can_finalize is False
        assert len(reasons) > 0
        
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 1.0
    
    def test_report_invalid_whitespace_statement_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "report_invalid_whitespace_statement.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        assert data["status"] == "INVALID"
        
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            claim_data = data["claims"][0]
            Claim(
                claim_id=claim_data["claim_id"],
                statement=claim_data["statement"],
                claim_label=ClaimLabel[claim_data["claim_label"]],
                step_id=claim_data["step_id"],
                evidence_ids=claim_data["evidence_ids"],
                claim_span=claim_data["claim_span"],
            )
    
    def test_report_zero_claims_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "report_zero_claims.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        assert data["status"] == "INCOMPLETE"
        assert len(data["claims"]) == 0
        assert data["can_finalize"] is False
        
        can_finalize, reasons = finalization_check([])
        assert can_finalize is False
        assert "No claims extracted - cannot finalize" in reasons[0]
        assert "Checklist:" in reasons[1]
        assert len(reasons) >= 5


class TestWhitespaceValidation:
    
    def test_claim_rejects_empty_statement(self):
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            Claim.create("", ClaimLabel.DERIVED)
    
    def test_claim_rejects_whitespace_only_statement(self):
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            Claim.create("   ", ClaimLabel.DERIVED)
    
    def test_claim_rejects_tabs_only_statement(self):
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            Claim.create("\t\t\t", ClaimLabel.DERIVED)
    
    def test_claim_rejects_newlines_only_statement(self):
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            Claim.create("\n\n", ClaimLabel.DERIVED)
    
    def test_claim_accepts_valid_statement(self):
        claim = Claim.create("E = mc^2", ClaimLabel.DERIVED)
        assert claim.statement == "E = mc^2"
    
    def test_claim_draft_rejects_empty_statement(self):
        from src.core.claim import ClaimDraft
        
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            ClaimDraft("")
    
    def test_claim_draft_rejects_whitespace_only_statement(self):
        from src.core.claim import ClaimDraft
        
        with pytest.raises(ValueError, match="Claim statement must be non-empty after trimming whitespace"):
            ClaimDraft("   ")


class TestZeroClaimsFinalization:
    
    def test_zero_claims_blocks_finalization(self):
        can_finalize, reasons = finalization_check([])
        assert can_finalize is False
        assert "No claims extracted - cannot finalize" in reasons[0]
    
    def test_zero_claims_provides_checklist(self):
        can_finalize, reasons = finalization_check([])
        assert "Checklist:" in reasons[1]
        assert any("derivation steps" in r for r in reasons)
        assert any("equations/identities" in r for r in reasons)
        assert any("source attributions" in r for r in reasons)
        assert any("no derivation possible yet" in r for r in reasons)
    
    def test_only_speculative_claims_can_finalize(self):
        claims = [
            Claim.create("This might be true", ClaimLabel.SPECULATIVE),
            Claim.create("Perhaps this holds", ClaimLabel.SPECULATIVE),
        ]
        can_finalize, reasons = finalization_check(claims)
        assert can_finalize is True
        assert len(reasons) == 0
    
    def test_unsupported_rate_with_zero_claims(self):
        rate = compute_unsupported_claim_rate([])
        assert rate == 0.0
