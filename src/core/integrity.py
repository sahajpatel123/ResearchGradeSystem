from typing import Optional
from src.core.claim import Claim, ClaimLabel


def compute_unsupported_claim_rate(claims: list[Claim]) -> float:
    """
    Compute unsupported-claim rate per GC-6.
    
    GC-6 definition:
    unsupported_non_spec_claims / total_non_spec_claims
    
    Note: Claim labels (GC-2) and extraction heuristics are scaffolding adjacent to GC-1.
    GC-1's core is what counts as a claim (statement asserting a math/physics fact that could
    be wrong and would affect correctness).
    """
    non_speculative_claims = [
        c for c in claims if c.claim_label != ClaimLabel.SPECULATIVE
    ]
    
    if len(non_speculative_claims) == 0:
        return 0.0
    
    unsupported_claims = [
        c for c in non_speculative_claims if not c.is_supported()
    ]
    
    return len(unsupported_claims) / len(non_speculative_claims)


def finalization_check(claims: list[Claim]) -> tuple[bool, list[str]]:
    """
    Check if a report can be finalized per GC-13.
    
    Zero-claims rule (aligned with GC-13 philosophy):
    - If zero claims extracted, system must NOT silently finalize.
    - Returns INCOMPLETE with explicit note: "no derivation possible yet" or
      "no checkable claims extracted" and a checklist asking for missing info.
    
    Returns:
        (can_finalize, reasons_list)
        - can_finalize: True only if all required artifacts present and valid
        - reasons: List of blocking reasons if cannot finalize
    """
    reasons = []
    
    if len(claims) == 0:
        reasons.append("No claims extracted - cannot finalize")
        reasons.append("Checklist:")
        reasons.append("  - Provide derivation steps with explicit claims")
        reasons.append("  - OR provide equations/identities to verify")
        reasons.append("  - OR provide source attributions/citations")
        reasons.append("  - OR explicitly state 'no derivation possible yet' with explanation")
        return (False, reasons)
    
    non_speculative_claims = [
        c for c in claims if c.claim_label != ClaimLabel.SPECULATIVE
    ]
    
    if len(non_speculative_claims) == 0:
        return (True, [])
    
    unsupported_claims = [
        c for c in non_speculative_claims if not c.is_supported()
    ]
    
    if len(unsupported_claims) > 0:
        reasons.append(
            f"Found {len(unsupported_claims)} unsupported non-SPECULATIVE claim(s)"
        )
        reasons.append(
            f"Unsupported claim rate: {len(unsupported_claims)}/{len(non_speculative_claims)} "
            f"= {compute_unsupported_claim_rate(claims):.2%}"
        )
        
        for claim in unsupported_claims[:5]:
            reasons.append(f"  - [{claim.claim_label.value}] {claim.statement[:80]}...")
        
        if len(unsupported_claims) > 5:
            reasons.append(f"  ... and {len(unsupported_claims) - 5} more")
        
        return (False, reasons)
    
    return (True, [])
