import pytest
from src.core.claim_extractor import ClaimExtractor, extract_claims
from src.core.claim import ClaimLabel


class TestClaimExtractorPositive:
    
    def test_extract_simple_equation(self):
        text = "The energy is $E = mc^2$."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert any("E = mc^2" in c.statement for c in claims)
    
    def test_extract_display_equation(self):
        latex = r"$$F = ma$$"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 1
        assert "F = ma" in claims[0].statement
        assert claims[0].suggested_label == ClaimLabel.DERIVED
    
    def test_extract_equation_environment(self):
        latex = r"\begin{equation}x^2 + y^2 = r^2\end{equation}"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 1
        assert "x^2 + y^2 = r^2" in claims[0].statement
    
    def test_extract_assertion_with_equals(self):
        text = "The velocity is equal to distance divided by time."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert any("velocity" in c.statement.lower() for c in claims)
    
    def test_extract_theorem_statement(self):
        text = "The Pythagorean theorem states that a^2 + b^2 = c^2."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        claim_statements = [c.statement for c in claims]
        assert any("theorem" in ct.lower() for ct in claim_statements)
    
    def test_extract_implication(self):
        text = "Therefore, the momentum is conserved."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.DERIVED
    
    def test_extract_multiple_equations(self):
        latex = r"$$E = mc^2$$ and $$p = mv$$"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 2
    
    def test_extract_cited_claim(self):
        text = "According to Einstein, energy and mass are equivalent."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.CITED
    
    def test_extract_computed_claim(self):
        text = "We compute the integral to be 42."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.COMPUTED
    
    def test_extract_derived_claim(self):
        text = "Thus, the force equals mass times acceleration."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.DERIVED
    
    def test_extract_satisfies_relation(self):
        text = "The function satisfies the differential equation."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_yields_statement(self):
        text = "This yields a value of 3.14."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_inequality(self):
        text = "The energy is greater than zero."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_proportionality(self):
        text = "The force is proportional to the acceleration."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_lemma_statement(self):
        text = "Lemma 1 states that the sum converges."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.CITED
    
    def test_extract_becomes_statement(self):
        text = "The equation becomes x = 5 after simplification."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_obeys_law(self):
        text = "The particle obeys Newton's second law."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_follows_from(self):
        text = "It follows that the velocity is constant."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_gives_result(self):
        text = "This gives us the final answer of 42."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_align_environment(self):
        latex = r"\begin{align}x &= 1 \\ y &= 2\end{align}"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 1
    
    def test_extract_bracket_equation(self):
        latex = r"\[E = \hbar\omega\]"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 1
    
    def test_extract_proposition(self):
        text = "Proposition 3 shows that the limit exists."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_corollary(self):
        text = "Corollary 2 implies that the function is continuous."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
    
    def test_extract_numerical_result(self):
        text = "The numerical simulation shows that x = 7.5."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.COMPUTED
    
    def test_extract_hence_statement(self):
        text = "Hence, the system is stable."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.DERIVED
    
    def test_extract_from_reference(self):
        text = "From Ref. [5], we know that the constant is 2.718."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.CITED


class TestClaimExtractorNegative:
    
    def test_pure_variable_declaration(self):
        text = "Let x be a real number."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) == 0
    
    def test_pure_definition_without_relation(self):
        text = "We define the velocity as the rate of change of position."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) == 0
    
    def test_denote_statement(self):
        text = "We denote the mass by m."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) == 0
    
    def test_leak_phrase_obviously(self):
        text = "Obviously, the result is positive."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.SPECULATIVE
    
    def test_leak_phrase_clearly(self):
        text = "Clearly, this implies convergence."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.SPECULATIVE
    
    def test_leak_phrase_well_known(self):
        text = "It is well-known that pi is irrational."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.SPECULATIVE
    
    def test_leak_phrase_by_symmetry(self):
        text = "By symmetry, the integral equals zero."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.SPECULATIVE
    
    def test_leak_phrase_trivially(self):
        text = "Trivially, the sum is finite."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.SPECULATIVE
    
    def test_leak_phrase_straightforward(self):
        text = "It is straightforward to show that x > 0."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 1
        assert claims[0].suggested_label == ClaimLabel.SPECULATIVE
    
    def test_multi_claim_sentence_splitting(self):
        text = "The energy is conserved and the momentum is constant."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) >= 2
    
    def test_empty_equation(self):
        latex = r"$$$$"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 0
    
    def test_equation_without_equals(self):
        latex = r"$$x + y$$"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims("", latex_blocks=[latex])
        assert len(claims) == 0
    
    def test_short_non_substantive_text(self):
        text = "Yes."
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) == 0
    
    def test_question_not_claim(self):
        text = "What is the value of x?"
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(text)
        assert len(claims) == 0


class TestUnsupportedClaimRate:
    
    def test_no_claims(self):
        from src.core.integrity import compute_unsupported_claim_rate
        claims = []
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 0.0
    
    def test_all_speculative(self):
        from src.core.integrity import compute_unsupported_claim_rate
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.SPECULATIVE),
            Claim.create("claim 2", ClaimLabel.SPECULATIVE),
        ]
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 0.0
    
    def test_all_supported(self):
        from src.core.integrity import compute_unsupported_claim_rate
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.COMPUTED),
        ]
        claims[0].evidence_ids = ["evidence_1"]
        claims[1].evidence_ids = ["evidence_2"]
        
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 0.0
    
    def test_all_unsupported(self):
        from src.core.integrity import compute_unsupported_claim_rate
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.COMPUTED),
        ]
        
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 1.0
    
    def test_mixed_support(self):
        from src.core.integrity import compute_unsupported_claim_rate
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.COMPUTED),
            Claim.create("claim 3", ClaimLabel.CITED),
            Claim.create("claim 4", ClaimLabel.SPECULATIVE),
        ]
        claims[0].evidence_ids = ["evidence_1"]
        
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 2.0 / 3.0
    
    def test_rate_ignores_speculative(self):
        from src.core.integrity import compute_unsupported_claim_rate
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.SPECULATIVE),
            Claim.create("claim 3", ClaimLabel.SPECULATIVE),
        ]
        
        rate = compute_unsupported_claim_rate(claims)
        assert rate == 1.0


class TestFinalizationCheck:
    
    def test_no_claims_blocks_finalization(self):
        from src.core.integrity import finalization_check
        
        can_finalize, reasons = finalization_check([])
        assert can_finalize is False
        assert len(reasons) > 0
        assert "No claims extracted - cannot finalize" in reasons[0]
    
    def test_only_speculative_can_finalize(self):
        from src.core.integrity import finalization_check
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.SPECULATIVE),
            Claim.create("claim 2", ClaimLabel.SPECULATIVE),
        ]
        
        can_finalize, reasons = finalization_check(claims)
        assert can_finalize is True
        assert len(reasons) == 0
    
    def test_all_supported_can_finalize(self):
        from src.core.integrity import finalization_check
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.COMPUTED),
        ]
        claims[0].evidence_ids = ["evidence_1"]
        claims[1].evidence_ids = ["evidence_2"]
        
        can_finalize, reasons = finalization_check(claims)
        assert can_finalize is True
        assert len(reasons) == 0
    
    def test_unsupported_blocks_finalization(self):
        from src.core.integrity import finalization_check
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.COMPUTED),
        ]
        
        can_finalize, reasons = finalization_check(claims)
        assert can_finalize is False
        assert len(reasons) > 0
        assert "unsupported" in reasons[0].lower()
    
    def test_partial_support_blocks_finalization(self):
        from src.core.integrity import finalization_check
        from src.core.claim import Claim, ClaimLabel
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.COMPUTED),
            Claim.create("claim 3", ClaimLabel.CITED),
        ]
        claims[0].evidence_ids = ["evidence_1"]
        
        can_finalize, reasons = finalization_check(claims)
        assert can_finalize is False
        assert len(reasons) > 0
