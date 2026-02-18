"""
GC-3 ScientificReport Schema

Container for claims and derivation steps with structural validation.
"""

from dataclasses import dataclass, field
from typing import Optional
from src.core.claim import Claim
from src.core.step import DerivationStep


@dataclass
class ScientificReport:
    """
    GC-3: Scientific report containing claims and derivation steps.
    
    A report is the top-level container that holds:
    - claims: List of all claims (from GC-1/GC-2)
    - steps: List of derivation steps that reference claims
    
    Structural invariants (enforced by validators, not __post_init__):
    - Every claim must be referenced by exactly one step (no orphans)
    - Every step.claim_ids[i] must reference an existing claim
    - No claim can be owned by multiple steps
    - Every step must have non-empty claim_ids
    """
    claims: list[Claim]
    steps: list[DerivationStep]
    report_id: Optional[str] = None
    
    def __post_init__(self):
        # Basic type validation
        if not isinstance(self.claims, list):
            raise TypeError(f"claims must be a list, got {type(self.claims).__name__}")
        
        if not isinstance(self.steps, list):
            raise TypeError(f"steps must be a list, got {type(self.steps).__name__}")
        
        # Check for duplicate claim_ids in claims list
        claim_ids = [c.claim_id for c in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            duplicates = [cid for cid in claim_ids if claim_ids.count(cid) > 1]
            raise ValueError(
                f"Duplicate claim_ids in claims list: {set(duplicates)} (GC-3: CLAIM_ID_COLLISION)"
            )
        
        # Check for duplicate step_ids in steps list
        step_ids = [s.step_id for s in self.steps]
        if len(step_ids) != len(set(step_ids)):
            duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
            raise ValueError(
                f"Duplicate step_ids in steps list: {set(duplicates)} (GC-3: STEP_ID_COLLISION)"
            )
