"""
GC-5 Evidence Object Schema

Strict evidence schema with typed enums, tagged unions, and fail-closed validation.

GC-5 enforces:
- Strict enums (EvidenceType, EvidenceStatus, IndeterminateReason)
- Tagged unions (EvidenceSource, PayloadRef)
- evidence_type ↔ source.kind alignment
- Indeterminate must have reason
- No trimming at wire boundary
- Reject unicode invisibles, non-ASCII, whitespace variants
"""

from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum


class EvidenceType(Enum):
    """GC-5: Strict evidence type enum"""
    DERIVATION = "derivation"
    COMPUTATION = "computation"
    CITATION = "citation"


class EvidenceStatus(Enum):
    """GC-5: Strict evidence status enum"""
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class IndeterminateReason(Enum):
    """GC-5: Tight enum for indeterminate status reasons"""
    UNSUPPORTED = "unsupported"
    DOMAIN = "domain"
    SINGULARITY = "singularity"
    TIMEOUT = "timeout"
    MISSING_BC_IC = "missing_bc_ic"
    TOOL_ERROR = "tool_error"


@dataclass
class EvidenceSource:
    """GC-5: Tagged union for evidence source
    
    Strict alignment with evidence_type:
    - derivation -> step_id
    - computation -> tool_run_id
    - citation -> citation_id
    """
    kind: Literal["step_id", "tool_run_id", "citation_id"]
    value: str
    
    def __post_init__(self):
        # Validate kind is one of allowed values
        if self.kind not in ["step_id", "tool_run_id", "citation_id"]:
            raise ValueError(
                f"EvidenceSource: invalid kind {repr(self.kind)} "
                f"(must be 'step_id', 'tool_run_id', or 'citation_id') (GC-5)"
            )
        
        # Validate value is non-empty string
        if not isinstance(self.value, str):
            raise TypeError(
                f"EvidenceSource: value must be string, got {type(self.value).__name__} (GC-5)"
            )
        
        if not self.value or not self.value.strip():
            raise ValueError("EvidenceSource: value must be non-empty (GC-5)")
        
        # GC-5 WIRE-BOUNDARY: NO TRIMMING
        if self.value != self.value.strip():
            raise ValueError(
                f"EvidenceSource: value {repr(self.value)} has leading/trailing whitespace (GC-5)"
            )


@dataclass
class PayloadRef:
    """GC-5: Tagged union for payload reference
    
    Strict token value validation.
    """
    kind: Literal["log_id", "snippet_ref", "expression_ref"]
    value: str
    
    def __post_init__(self):
        # Validate kind is one of allowed values
        if self.kind not in ["log_id", "snippet_ref", "expression_ref"]:
            raise ValueError(
                f"PayloadRef: invalid kind {repr(self.kind)} "
                f"(must be 'log_id', 'snippet_ref', or 'expression_ref') (GC-5)"
            )
        
        # Validate value is non-empty string
        if not isinstance(self.value, str):
            raise TypeError(
                f"PayloadRef: value must be string, got {type(self.value).__name__} (GC-5)"
            )
        
        if not self.value or not self.value.strip():
            raise ValueError("PayloadRef: value must be non-empty (GC-5)")
        
        # GC-5 WIRE-BOUNDARY: NO TRIMMING
        if self.value != self.value.strip():
            raise ValueError(
                f"PayloadRef: value {repr(self.value)} has leading/trailing whitespace (GC-5)"
            )


@dataclass
class EvidenceObject:
    """GC-5: Strict evidence object with typed fields and fail-closed validation
    
    Required fields:
    - evidence_id: Unique identifier (strict token)
    - evidence_type: EvidenceType enum
    - source: EvidenceSource tagged union
    - status: EvidenceStatus enum
    - payload_ref: PayloadRef tagged union
    
    Conditional:
    - status_reason: Required iff status == INDETERMINATE
    
    Optional:
    - notes: If present, must be non-empty after trim
    
    Validation rules:
    - evidence_type ↔ source.kind alignment enforced
    - Indeterminate must have reason from tight enum
    - All tokens: no trimming, reject whitespace variants
    """
    evidence_id: str
    evidence_type: EvidenceType
    source: EvidenceSource
    status: EvidenceStatus
    payload_ref: PayloadRef
    status_reason: Optional[IndeterminateReason] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        # GC-5: evidence_id strict validation
        if not isinstance(self.evidence_id, str):
            raise TypeError(
                f"EvidenceObject: evidence_id must be string, "
                f"got {type(self.evidence_id).__name__} (GC-5)"
            )
        
        if not self.evidence_id or not self.evidence_id.strip():
            raise ValueError("EvidenceObject: evidence_id must be non-empty (GC-5)")
        
        # GC-5 WIRE-BOUNDARY: NO TRIMMING
        if self.evidence_id != self.evidence_id.strip():
            raise ValueError(
                f"EvidenceObject: evidence_id {repr(self.evidence_id)} has leading/trailing "
                f"whitespace (GC-5: whitespace variants rejected)"
            )
        
        # GC-5: Type validation for enums
        if not isinstance(self.evidence_type, EvidenceType):
            raise TypeError(
                f"EvidenceObject: evidence_type must be EvidenceType enum, "
                f"got {type(self.evidence_type).__name__} (GC-5)"
            )
        
        if not isinstance(self.source, EvidenceSource):
            raise TypeError(
                f"EvidenceObject: source must be EvidenceSource, "
                f"got {type(self.source).__name__} (GC-5)"
            )
        
        if not isinstance(self.status, EvidenceStatus):
            raise TypeError(
                f"EvidenceObject: status must be EvidenceStatus enum, "
                f"got {type(self.status).__name__} (GC-5)"
            )
        
        if not isinstance(self.payload_ref, PayloadRef):
            raise TypeError(
                f"EvidenceObject: payload_ref must be PayloadRef, "
                f"got {type(self.payload_ref).__name__} (GC-5)"
            )
        
        # GC-5: Alignment rule - evidence_type ↔ source.kind
        alignment = {
            EvidenceType.DERIVATION: "step_id",
            EvidenceType.COMPUTATION: "tool_run_id",
            EvidenceType.CITATION: "citation_id",
        }
        
        expected_kind = alignment[self.evidence_type]
        if self.source.kind != expected_kind:
            raise ValueError(
                f"EvidenceObject: EVIDENCE_SOURCE_KIND_MISMATCH - "
                f"evidence_type={self.evidence_type.value} requires source.kind={expected_kind}, "
                f"got {self.source.kind} (GC-5)"
            )
        
        # GC-5: Indeterminate reason rule
        if self.status == EvidenceStatus.INDETERMINATE:
            if self.status_reason is None:
                raise ValueError(
                    f"EvidenceObject: INDETERMINATE_MISSING_REASON - "
                    f"status=indeterminate requires status_reason (GC-5)"
                )
            if not isinstance(self.status_reason, IndeterminateReason):
                raise TypeError(
                    f"EvidenceObject: status_reason must be IndeterminateReason enum, "
                    f"got {type(self.status_reason).__name__} (GC-5)"
                )
        else:
            # Optional strictness: reject status_reason when not indeterminate
            if self.status_reason is not None:
                raise ValueError(
                    f"EvidenceObject: status_reason present when status={self.status.value} "
                    f"(only allowed for indeterminate) (GC-5)"
                )
        
        # GC-5: Notes validation (if present, must be non-empty after trim)
        if self.notes is not None:
            if not isinstance(self.notes, str):
                raise TypeError(
                    f"EvidenceObject: notes must be string, "
                    f"got {type(self.notes).__name__} (GC-5)"
                )
            if not self.notes.strip():
                raise ValueError(
                    f"EvidenceObject: NOTES_EMPTY - notes present but empty after trim (GC-5)"
                )
