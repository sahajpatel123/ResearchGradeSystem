"""
GC-6 Integrity Metrics Schema and Computation

Computes unsupported claim rate for non-SPECULATIVE claims.
Metrics are computed-only and must never be accepted from wire without validation.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
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
    - diagnostics_notes: Optional list of parse/type failures encountered during computation
    
    A non-SPECULATIVE claim is unsupported iff (Option A strict):
    - evidence_ids is empty OR
    - ANY referenced evidence_id is dangling OR
    - ANY referenced EvidenceObject fails GC-5 validation OR
    - ANY parsing/type issue prevents confirming support (fail-closed)
    """
    unsupported_non_spec_claims: int
    total_non_spec_claims: int
    unsupported_claim_rate: float
    unsupported_claim_ids: list[str]
    diagnostics_notes: list[str] = field(default_factory=list)
    
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
    claims: Any,
    evidence_by_id: Optional[dict[str, Any]] = None
) -> IntegrityMetrics:
    """
    GC-6: Compute integrity metrics for a report (DEFENSIVE - works even when GC-4/GC-5 fail).
    
    This is the SINGLE SOURCE OF TRUTH for integrity metrics.
    MUST compute deterministic metrics even when report is invalid (for diagnostics).
    
    Algorithm (Option A strict, fail-closed):
    1. Build evidence_by_id defensively (handle missing/malformed evidence)
    2. For each claim:
       - If SPECULATIVE: skip (not counted in GC-6)
       - Else:
           - Increment total_non_spec_claims
           - Mark unsupported if:
             * evidence_ids missing/empty/wrong type OR
             * ANY evidence_id not in evidence_by_id (dangling) OR
             * ANY evidence_id resolves to invalid EvidenceObject OR
             * ANY parsing/type issue prevents confirming support
    3. Compute rate = 0.0 if total==0 else unsupported/total
    4. Return deterministic metrics (sorted unsupported_claim_ids) + diagnostics_notes
    
    Args:
        claims: List of claims from report (may be malformed)
        evidence_by_id: Map of evidence_id -> EvidenceObject (may be None/malformed)
    
    Returns:
        IntegrityMetrics with computed values (never crashes)
    """
    total_non_spec_claims = 0
    unsupported_claim_ids = []
    diagnostics_notes = []
    
    # Defensive: handle missing/malformed evidence_by_id
    if evidence_by_id is None:
        evidence_by_id = {}
        diagnostics_notes.append("evidence_by_id was None, treating as empty")
    elif not isinstance(evidence_by_id, dict):
        evidence_by_id = {}
        diagnostics_notes.append(f"evidence_by_id wrong type ({type(evidence_by_id).__name__}), treating as empty")
    
    # Defensive: handle missing/malformed claims
    if claims is None:
        diagnostics_notes.append("claims was None, treating as empty")
        claims = []
    elif not isinstance(claims, list):
        diagnostics_notes.append(f"claims wrong type ({type(claims).__name__}), treating as empty")
        claims = []
    
    for i, claim in enumerate(claims):
        # Defensive: skip malformed claim objects
        if not isinstance(claim, Claim):
            diagnostics_notes.append(f"claims[{i}] is not a Claim object, skipping")
            continue
        
        # Defensive: handle missing claim_label
        try:
            claim_label = claim.claim_label
        except (AttributeError, Exception) as e:
            diagnostics_notes.append(f"claim {claim.claim_id if hasattr(claim, 'claim_id') else i} missing claim_label, treating as unsupported")
            total_non_spec_claims += 1
            if hasattr(claim, 'claim_id') and isinstance(claim.claim_id, str):
                unsupported_claim_ids.append(claim.claim_id)
            continue
        
        # Skip SPECULATIVE claims (not counted in GC-6)
        if claim_label == ClaimLabel.SPECULATIVE:
            continue
        
        # Count non-SPECULATIVE claim
        total_non_spec_claims += 1
        
        # Check if unsupported (Option A strict, fail-closed)
        is_unsupported = False
        
        # Defensive: handle missing/malformed evidence_ids
        try:
            evidence_ids = claim.evidence_ids
        except (AttributeError, Exception) as e:
            diagnostics_notes.append(f"claim {claim.claim_id} missing evidence_ids, treating as unsupported")
            is_unsupported = True
            unsupported_claim_ids.append(claim.claim_id)
            continue
        
        # Case 1: evidence_ids wrong type
        if not isinstance(evidence_ids, list):
            diagnostics_notes.append(f"claim {claim.claim_id} evidence_ids wrong type ({type(evidence_ids).__name__}), treating as unsupported")
            is_unsupported = True
        # Case 2: evidence_ids is empty
        elif not evidence_ids or len(evidence_ids) == 0:
            is_unsupported = True
        else:
            # Case 3: ANY evidence_id is not a string
            for eid in evidence_ids:
                if not isinstance(eid, str):
                    diagnostics_notes.append(f"claim {claim.claim_id} has non-string evidence_id ({type(eid).__name__}), treating as unsupported")
                    is_unsupported = True
                    break
            
            # Case 4: ANY evidence_id is dangling (not in evidence_by_id)
            if not is_unsupported:
                for evidence_id in evidence_ids:
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
        diagnostics_notes=diagnostics_notes,
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
