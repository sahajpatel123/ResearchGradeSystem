from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class ClaimLabel(Enum):
    """
    GC-2: Claim labels - EXACTLY 4, case-sensitive.
    
    Valid labels:
    - DERIVED: Claim derived through logical/mathematical steps
    - COMPUTED: Claim verified through computation/simulation
    - CITED: Claim attributed to external source
    - SPECULATIVE: Claim not yet verified
    
    Note: GC-2 enforces label validity only. Evidence compatibility and 
    citation requirements are enforced later by GC-4/GC-12.
    """
    DERIVED = "DERIVED"
    COMPUTED = "COMPUTED"
    CITED = "CITED"
    SPECULATIVE = "SPECULATIVE"


@dataclass
class Claim:
    claim_id: str
    statement: str
    claim_label: ClaimLabel
    step_id: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)
    claim_span: Optional[tuple[int, int]] = None

    def __post_init__(self):
        if not self.statement or not self.statement.strip():
            raise ValueError("Claim statement must be non-empty after trimming whitespace")
        
        if self.claim_label is None:
            raise ValueError("Claim label is required (GC-2)")
        
        if not isinstance(self.claim_label, ClaimLabel):
            raise TypeError(
                f"Claim label must be ClaimLabel enum, got {type(self.claim_label).__name__}"
            )

    @staticmethod
    def create(
        statement: str,
        claim_label: ClaimLabel,
        step_id: Optional[str] = None,
        claim_span: Optional[tuple[int, int]] = None,
    ) -> "Claim":
        return Claim(
            claim_id=str(uuid4()),
            statement=statement,
            claim_label=claim_label,
            step_id=step_id,
            evidence_ids=[],
            claim_span=claim_span,
        )

    def is_supported(self) -> bool:
        if self.claim_label == ClaimLabel.SPECULATIVE:
            return True
        return len(self.evidence_ids) > 0


@dataclass
class ClaimDraft:
    statement: str
    claim_span: Optional[tuple[int, int]] = None
    suggested_label: ClaimLabel = ClaimLabel.SPECULATIVE

    def __post_init__(self):
        if not self.statement or not self.statement.strip():
            raise ValueError("Claim statement must be non-empty after trimming whitespace")

    def to_claim(self, step_id: Optional[str] = None) -> Claim:
        return Claim.create(
            statement=self.statement,
            claim_label=self.suggested_label,
            step_id=step_id,
            claim_span=self.claim_span,
        )
