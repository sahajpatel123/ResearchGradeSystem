"""
GC-3/GC-4 ScientificReport Schema

Container for claims, derivation steps, and evidence with structural validation.
"""

from dataclasses import dataclass, field
from typing import Optional
from src.core.claim import Claim
from src.core.step import DerivationStep
from src.core.evidence import EvidenceObject


@dataclass
class ScientificReport:
    """
    GC-3/GC-4: Scientific report containing claims, steps, and evidence.
    
    A report is the top-level container that holds:
    - claims: List of all claims (from GC-1/GC-2)
    - steps: List of derivation steps that reference claims (GC-3)
    - evidence: List of evidence objects supporting claims (GC-4)
    
    Structural invariants (enforced by validators, not __post_init__):
    - GC-3: Every claim must be referenced by exactly one step (no orphans)
    - GC-3: Every step.claim_ids[i] must reference an existing claim
    - GC-3: No claim can be owned by multiple steps
    - GC-3: Every step must have non-empty claim_ids
    - GC-4: Non-SPECULATIVE claims must have ≥1 evidence_id
    - GC-4: SPECULATIVE claims must have verify_falsify
    - GC-4: Every evidence_id must resolve to report.evidence[]
    """
    claims: list[Claim]
    steps: list[DerivationStep]
    evidence: list[EvidenceObject] = field(default_factory=list)
    report_id: Optional[str] = None
    
    def __post_init__(self):
        # Basic type validation
        if not isinstance(self.claims, list):
            raise TypeError(f"claims must be a list, got {type(self.claims).__name__}")
        
        if not isinstance(self.steps, list):
            raise TypeError(f"steps must be a list, got {type(self.steps).__name__}")
        
        if not isinstance(self.evidence, list):
            raise TypeError(f"evidence must be a list, got {type(self.evidence).__name__}")
        
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
        
        # GC-4: Check for duplicate evidence_ids in evidence list
        evidence_ids = [e.evidence_id for e in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            duplicates = [eid for eid in evidence_ids if evidence_ids.count(eid) > 1]
            raise ValueError(
                f"Duplicate evidence_ids in evidence list: {set(duplicates)} (GC-4: EVIDENCE_ID_COLLISION)"
            )
