"""
GC-6 Integrity Metrics Schema and Computation

Computes unsupported claim rate for non-SPECULATIVE claims.
Metrics are computed-only and must never be accepted from wire without validation.
"""

from dataclasses import dataclass
from typing import Optional
from src.core.claim import Claim, ClaimLabel
from src.core.evidence import EvidenceObject


@dataclass
class IntegrityMetrics:
    """
    GC-6: Integrity metrics for a scientific report.
    
    These metrics measure claim support quality and are COMPUTED-ONLY.
    Never accept user-provided values without recomputing and validating.
    
    Fields:
    - unsupported_non_spec_claims: Count of non-SPECULATIVE claims that are unsupported
    - total_non_spec_claims: Total count of non-SPECULATIVE claims
    - unsupported_claim_rate: Ratio unsupported/total (0.0 if total==0)
    - unsupported_claim_ids: Sorted list of claim_ids that are unsupported (deterministic)
    
    A non-SPECULATIVE claim is unsupported iff (Option A strict):
    - evidence_ids is empty OR
    - ANY referenced evidence_id is dangling OR
    - ANY referenced EvidenceObject fails GC-5 validation
    """
    unsupported_non_spec_claims: int
    total_non_spec_claims: int
    unsupported_claim_rate: float
    unsupported_claim_ids: list[str]
    
    def __post_init__(self):
        # Type validation
        if not isinstance(self.unsupported_non_spec_claims, int):
            raise TypeError(
                f"unsupported_non_spec_claims must be int, got {type(self.unsupported_non_spec_claims).__name__} (GC-6)"
            )
        
        if not isinstance(self.total_non_spec_claims, int):
            raise TypeError(
                f"total_non_spec_claims must be int, got {type(self.total_non_spec_claims).__name__} (GC-6)"
            )
        
        if not isinstance(self.unsupported_claim_rate, (int, float)):
            raise TypeError(
                f"unsupported_claim_rate must be float, got {type(self.unsupported_claim_rate).__name__} (GC-6)"
            )
        
        if not isinstance(self.unsupported_claim_ids, list):
            raise TypeError(
                f"unsupported_claim_ids must be list, got {type(self.unsupported_claim_ids).__name__} (GC-6)"
            )
        
        # Value validation
        if self.unsupported_non_spec_claims < 0:
            raise ValueError(
                f"unsupported_non_spec_claims must be non-negative, got {self.unsupported_non_spec_claims} (GC-6)"
            )
        
        if self.total_non_spec_claims < 0:
            raise ValueError(
                f"total_non_spec_claims must be non-negative, got {self.total_non_spec_claims} (GC-6)"
            )
        
        if self.unsupported_non_spec_claims > self.total_non_spec_claims:
            raise ValueError(
                f"unsupported_non_spec_claims ({self.unsupported_non_spec_claims}) cannot exceed total_non_spec_claims ({self.total_non_spec_claims}) (GC-6)"
            )
        
        # Check for NaN/Infinity
        import math
        if math.isnan(self.unsupported_claim_rate) or math.isinf(self.unsupported_claim_rate):
            raise ValueError(
                f"unsupported_claim_rate must be finite, got {self.unsupported_claim_rate} (GC-6: METRICS_INVALID_NUMBER)"
            )
        
        # Rate validation
        if self.unsupported_claim_rate < 0.0 or self.unsupported_claim_rate > 1.0:
            raise ValueError(
                f"unsupported_claim_rate must be in [0.0, 1.0], got {self.unsupported_claim_rate} (GC-6)"
            )
        
        # Consistency check: rate must match ints
        expected_rate = 0.0 if self.total_non_spec_claims == 0 else self.unsupported_non_spec_claims / self.total_non_spec_claims
        epsilon = 1e-9
        if abs(self.unsupported_claim_rate - expected_rate) > epsilon:
            raise ValueError(
                f"unsupported_claim_rate ({self.unsupported_claim_rate}) does not match computed rate from ints ({expected_rate}) (GC-6: METRICS_INCONSISTENT)"
            )
        
        # Consistency check: unsupported_claim_ids count must match unsupported_non_spec_claims
        if len(self.unsupported_claim_ids) != self.unsupported_non_spec_claims:
            raise ValueError(
                f"unsupported_claim_ids length ({len(self.unsupported_claim_ids)}) does not match unsupported_non_spec_claims ({self.unsupported_non_spec_claims}) (GC-6: METRICS_INCONSISTENT)"
            )
        
        # Determinism check: unsupported_claim_ids must be sorted and unique
        if self.unsupported_claim_ids != sorted(set(self.unsupported_claim_ids)):
            raise ValueError(
                f"unsupported_claim_ids must be sorted and unique (GC-6: METRICS_NON_DETERMINISTIC)"
            )


def compute_integrity_metrics(
    claims: list[Claim],
    evidence_by_id: dict[str, EvidenceObject]
) -> IntegrityMetrics:
    """
    GC-6: Compute integrity metrics for a report.
    
    This is the SINGLE SOURCE OF TRUTH for integrity metrics.
    
    Algorithm (Option A strict):
    1. Build evidence_by_id from validated GC-5 evidence objects
    2. For each claim:
       - If SPECULATIVE: skip (not counted in GC-6)
       - Else:
           - Increment total_non_spec_claims
           - Mark unsupported if:
             * evidence_ids is empty OR
             * ANY evidence_id not in evidence_by_id (dangling) OR
             * ANY evidence_id resolves to invalid EvidenceObject (defensive)
    3. Compute rate = 0.0 if total==0 else unsupported/total
    4. Return deterministic metrics (sorted unsupported_claim_ids)
    
    Args:
        claims: List of claims from report
        evidence_by_id: Map of evidence_id -> EvidenceObject (GC-5 validated)
    
    Returns:
        IntegrityMetrics with computed values
    """
    total_non_spec_claims = 0
    unsupported_claim_ids = []
    
    for claim in claims:
        # Skip SPECULATIVE claims (not counted in GC-6)
        if claim.claim_label == ClaimLabel.SPECULATIVE:
            continue
        
        # Count non-SPECULATIVE claim
        total_non_spec_claims += 1
        
        # Check if unsupported (Option A strict)
        is_unsupported = False
        
        # Case 1: evidence_ids is empty
        if not claim.evidence_ids or len(claim.evidence_ids) == 0:
            is_unsupported = True
        else:
            # Case 2: ANY evidence_id is dangling
            for evidence_id in claim.evidence_ids:
                if evidence_id not in evidence_by_id:
                    is_unsupported = True
                    break
        
        if is_unsupported:
            unsupported_claim_ids.append(claim.claim_id)
    
    # Sort and deduplicate unsupported_claim_ids for determinism
    unsupported_claim_ids = sorted(set(unsupported_claim_ids))
    
    unsupported_non_spec_claims = len(unsupported_claim_ids)
    
    # Compute rate (canonical: derived from ints)
    if total_non_spec_claims == 0:
        unsupported_claim_rate = 0.0
    else:
        unsupported_claim_rate = unsupported_non_spec_claims / total_non_spec_claims
    
    return IntegrityMetrics(
        unsupported_non_spec_claims=unsupported_non_spec_claims,
        total_non_spec_claims=total_non_spec_claims,
        unsupported_claim_rate=unsupported_claim_rate,
        unsupported_claim_ids=unsupported_claim_ids,
    )


def compute_speculative_flood_warning(claims: list[Claim]) -> Optional[str]:
    """
    GC-6: Check if report has excessive SPECULATIVE claims (warning-only).
    
    Returns warning string if speculative_ratio > 0.30, else None.
    """
    if not claims or len(claims) == 0:
        return None
    
    speculative_count = sum(1 for c in claims if c.claim_label == ClaimLabel.SPECULATIVE)
    total_claims = len(claims)
    speculative_ratio = speculative_count / total_claims
    
    if speculative_ratio > 0.30:
        return f"SPECULATIVE_FLOOD_WARNING: {speculative_count}/{total_claims} claims are SPECULATIVE ({speculative_ratio:.1%} > 30%)"
    
    return None
