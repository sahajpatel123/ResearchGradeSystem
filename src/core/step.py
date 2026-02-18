"""
GC-3 Step/Claim Boundary Schema

Defines DerivationStep and ScientificReport schemas with strict structural validation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class StepStatus(Enum):
    """
    GC-3: Step status tracking.
    
    - UNCHECKED: Step not yet verified
    - CHECKED: Step verified and valid
    - FAILED: Step verification failed
    - INDETERMINATE: Step verification inconclusive (requires status_reason)
    """
    UNCHECKED = "UNCHECKED"
    CHECKED = "CHECKED"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


@dataclass
class DerivationStep:
    """
    GC-3: Derivation step linking to claims.
    
    A step represents a logical unit in a derivation that references one or more claims.
    Every step MUST reference at least one claim (claim_ids non-empty).
    
    Fields:
    - step_id: Unique identifier for this step
    - claim_ids: List of claim IDs referenced by this step (REQUIRED, NON-EMPTY)
    - depends_on: Optional list of step IDs this step depends on
    - step_status: Current verification status
    - status_reason: Required explanation if step_status is INDETERMINATE
    """
    step_id: str
    claim_ids: list[str]
    step_status: StepStatus = StepStatus.UNCHECKED
    depends_on: list[str] = field(default_factory=list)
    status_reason: Optional[str] = None
    
    def __post_init__(self):
        # V4: claim_ids must be non-empty
        if not self.claim_ids:
            raise ValueError(f"Step {self.step_id}: claim_ids cannot be empty (GC-3 V4: EMPTY_CLAIM_IDS)")
        
        # Validate claim_ids is a list
        if not isinstance(self.claim_ids, list):
            raise TypeError(f"Step {self.step_id}: claim_ids must be a list, got {type(self.claim_ids).__name__}")
        
        # Check for duplicate claim_ids within this step
        if len(self.claim_ids) != len(set(self.claim_ids)):
            duplicates = [cid for cid in self.claim_ids if self.claim_ids.count(cid) > 1]
            raise ValueError(
                f"Step {self.step_id}: duplicate claim_ids within step: {set(duplicates)} "
                f"(GC-3: DUPLICATE_CLAIM_IN_STEP)"
            )
        
        # Validate step_status is StepStatus enum
        if not isinstance(self.step_status, StepStatus):
            raise TypeError(
                f"Step {self.step_id}: step_status must be StepStatus enum, "
                f"got {type(self.step_status).__name__}"
            )
        
        # INDETERMINATE requires status_reason
        if self.step_status == StepStatus.INDETERMINATE:
            if not self.status_reason or not self.status_reason.strip():
                raise ValueError(
                    f"Step {self.step_id}: step_status INDETERMINATE requires non-empty status_reason (GC-3)"
                )
        
        # Validate depends_on is a list
        if not isinstance(self.depends_on, list):
            raise TypeError(
                f"Step {self.step_id}: depends_on must be a list, got {type(self.depends_on).__name__}"
            )
    
    @staticmethod
    def create(
        claim_ids: list[str],
        step_status: StepStatus = StepStatus.UNCHECKED,
        depends_on: Optional[list[str]] = None,
        status_reason: Optional[str] = None,
    ) -> "DerivationStep":
        """Create a new DerivationStep with generated step_id."""
        return DerivationStep(
            step_id=str(uuid4()),
            claim_ids=claim_ids,
            step_status=step_status,
            depends_on=depends_on or [],
            status_reason=status_reason,
        )
