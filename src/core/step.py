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
    GC-7: Step status tracking (wire format: lowercase).
    
    - unchecked: Step not yet verified
    - checked: Step verified and valid
    - failed: Step verification failed
    - indeterminate: Step verification inconclusive (requires status_reason)
    """
    UNCHECKED = "unchecked"
    CHECKED = "checked"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


@dataclass
class DerivationStep:
    """
    GC-3/GC-8: Derivation step linking to claims.
    
    A step represents a logical unit in a derivation that references one or more claims.
    Every step MUST reference at least one claim (claim_ids non-empty).
    Every step MUST have a non-empty statement describing the derivation action.
    
    Fields:
    - step_id: Unique identifier for this step
    - claim_ids: List of claim IDs referenced by this step (REQUIRED, NON-EMPTY - GC-3/GC-8)
    - statement: Description of the derivation action (REQUIRED, NON-EMPTY - GC-8)
    - depends_on: Optional list of step IDs this step depends on
    - step_status: Current verification status (GC-7)
    - status_reason: Required explanation if step_status is INDETERMINATE (GC-7)
    """
    step_id: str
    claim_ids: list[str]
    statement: str
    step_status: StepStatus = StepStatus.UNCHECKED
    depends_on: list[str] = field(default_factory=list)
    status_reason: Optional[str] = None
    
    def __post_init__(self):
        # GC-8: statement must be non-empty (type check)
        if self.statement is None:
            raise ValueError(f"Step {self.step_id}: statement cannot be None (GC-8: DERIVATION_STEP_EMPTY_STATEMENT)")
        if not isinstance(self.statement, str):
            raise TypeError(f"Step {self.step_id}: statement must be string, got {type(self.statement).__name__} (GC-8: DERIVATION_STEP_STATEMENT_INVALID_TYPE)")
        
        # GC-8: statement must be non-empty (emptiness check with invisible character detection)
        trimmed_statement = self.statement.strip()
        # Check for invisible-only content after ASCII whitespace trim
        if trimmed_statement:
            invisible_chars = {'\u200b', '\u00a0', '\ufeff', '\u2060', '\u200c', '\u200d'}
            if all(c in invisible_chars for c in trimmed_statement):
                trimmed_statement = ""
        if not trimmed_statement:
            raise ValueError(f"Step {self.step_id}: statement is empty, whitespace-only, or invisible-only (GC-8: DERIVATION_STEP_EMPTY_STATEMENT)")
        
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
        
        # GC-7: INDETERMINATE requires status_reason
        # GC-7.1a: Distinguish between missing (None) and empty-when-present
        if self.step_status == StepStatus.INDETERMINATE:
            if self.status_reason is None:
                raise ValueError(
                    f"Step {self.step_id}: step_status INDETERMINATE requires status_reason (GC-7: INDETERMINATE_MISSING_REASON)"
                )
            # Check for empty/whitespace/invisible-only (GC-7.1a: STATUS_REASON_EMPTY_WHEN_PRESENT)
            trimmed = self.status_reason.strip()
            # Check for invisible-only content after ASCII whitespace trim
            if trimmed:
                invisible_chars = {'\u200b', '\u00a0', '\ufeff', '\u2060', '\u200c', '\u200d'}
                if all(c in invisible_chars for c in trimmed):
                    trimmed = ""
            if not trimmed:
                raise ValueError(
                    f"Step {self.step_id}: status_reason is empty, whitespace-only, or invisible-only (GC-7: STATUS_REASON_EMPTY_WHEN_PRESENT)"
                )
        
        # GC-7.1a: FAILED steps MAY include status_reason (optional), but if present must be non-empty
        if self.step_status == StepStatus.FAILED and self.status_reason is not None:
            # Check for empty/whitespace/invisible-only (GC-7.1a: STATUS_REASON_EMPTY_WHEN_PRESENT)
            trimmed = self.status_reason.strip()
            # Check for invisible-only content after ASCII whitespace trim
            if trimmed:
                invisible_chars = {'\u200b', '\u00a0', '\ufeff', '\u2060', '\u200c', '\u200d'}
                if all(c in invisible_chars for c in trimmed):
                    trimmed = ""
            if not trimmed:
                raise ValueError(
                    f"Step {self.step_id}: status_reason is empty, whitespace-only, or invisible-only (GC-7: STATUS_REASON_EMPTY_WHEN_PRESENT)"
                )
        
        # GC-7: status_reason NOT ALLOWED for checked/unchecked (fail-closed)
        if self.step_status in {StepStatus.CHECKED, StepStatus.UNCHECKED} and self.status_reason:
            raise ValueError(
                f"Step {self.step_id}: status_reason not allowed for step_status {self.step_status.value} "
                f"(GC-7: STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED)"
            )
        
        # Validate depends_on is a list
        if not isinstance(self.depends_on, list):
            raise TypeError(
                f"Step {self.step_id}: depends_on must be a list, got {type(self.depends_on).__name__}"
            )
    
    @staticmethod
    def create(
        claim_ids: list[str],
        statement: str,
        step_status: StepStatus = StepStatus.UNCHECKED,
        depends_on: Optional[list[str]] = None,
        status_reason: Optional[str] = None,
    ) -> "DerivationStep":
        """Create a new DerivationStep with generated step_id."""
        return DerivationStep(
            step_id=str(uuid4()),
            claim_ids=claim_ids,
            statement=statement,
            step_status=step_status,
            depends_on=depends_on or [],
            status_reason=status_reason,
        )
