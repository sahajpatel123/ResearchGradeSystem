"""
GC-5 Wire-Boundary Parsers

Strict parsers for EvidenceObject and related types from raw JSON wire inputs.

Wire posture (matches GC-2/GC-4):
- NO TRIMMING: Reject whitespace variants deterministically
- Reject unicode invisibles (ZWSP, NBSP, BOM, WJ, ZWNJ, ZWJ)
- Reject non-ASCII characters (confusables)
- Reject type coercion (string required where string is required)
- Reject internal whitespace in ID tokens

All parsers either return validated typed objects or raise deterministic errors.
"""

from typing import Any, Dict
from src.core.evidence import (
    EvidenceObject,
    EvidenceType,
    EvidenceStatus,
    IndeterminateReason,
    EvidenceSource,
    PayloadRef,
)


def _check_unicode_invisibles(value: str, field_name: str) -> None:
    """Check for unicode invisible characters"""
    invisible_chars = [
        '\u200b',  # ZWSP
        '\u00a0',  # NBSP
        '\ufeff',  # BOM
        '\u2060',  # Word Joiner
        '\u200c',  # ZWNJ
        '\u200d',  # ZWJ
    ]
    
    for invisible in invisible_chars:
        if invisible in value:
            raise ValueError(
                f"Invalid {field_name}: {repr(value)} contains invisible unicode character (GC-5)"
            )


def _check_non_ascii(value: str, field_name: str) -> None:
    """Check for non-ASCII characters (confusables)"""
    try:
        value.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(
            f"Invalid {field_name}: {repr(value)} contains non-ASCII characters (GC-5)"
        )


def _check_internal_whitespace(value: str, field_name: str) -> None:
    """Check for internal whitespace in ID tokens (space, tab, newline)"""
    if ' ' in value or '\t' in value or '\n' in value or '\r' in value:
        raise ValueError(
            f"Invalid {field_name}: {repr(value)} contains internal whitespace (GC-5)"
        )


def parse_evidence_id(wire: Any) -> str:
    """
    WIRE BOUNDARY PARSER - Parse evidence_id from raw input.
    
    Strict rules (GC-5):
    - Must be a JSON string
    - Must be ASCII-only
    - Must not contain invisibles
    - Must have NO leading/trailing whitespace (no trimming)
    - Must not contain internal whitespace
    - Must not be empty
    
    Args:
        wire: Raw value from external source
        
    Returns:
        Validated evidence_id string
        
    Raises:
        TypeError: If wire is not a string
        ValueError: If wire violates any validation rule
    """
    # Type check
    if wire is None:
        raise ValueError("Invalid evidence_id: None (GC-5)")
    
    if not isinstance(wire, str):
        type_name = type(wire).__name__
        raise TypeError(
            f"Invalid evidence_id: {repr(wire)} (expected string, got {type_name}) (GC-5)"
        )
    
    # Empty check
    if wire == "":
        raise ValueError("Invalid evidence_id: empty string (GC-5)")
    
    # Check for unicode invisibles FIRST (before whitespace checks)
    _check_unicode_invisibles(wire, "evidence_id")
    
    # Whitespace-only check
    if not wire.strip():
        raise ValueError(
            f"Invalid evidence_id: {repr(wire)} is whitespace-only (GC-5)"
        )
    
    # GC-5 WIRE-BOUNDARY: NO TRIMMING
    # Reject any leading/trailing whitespace variants
    if wire != wire.strip():
        raise ValueError(
            f"Invalid evidence_id: {repr(wire)} has leading/trailing whitespace "
            f"(GC-5: whitespace variants rejected at wire boundary)"
        )
    
    # Check for non-ASCII
    _check_non_ascii(wire, "evidence_id")
    
    # Check for internal whitespace
    _check_internal_whitespace(wire, "evidence_id")
    
    return wire


def parse_evidence_type(wire: Any) -> EvidenceType:
    """
    WIRE BOUNDARY PARSER - Parse evidence_type from raw input.
    
    Strict rules (GC-5):
    - Must be a JSON string
    - Must be one of: "derivation", "computation", "citation"
    - Case-sensitive, exact match
    
    Args:
        wire: Raw value from external source
        
    Returns:
        EvidenceType enum
        
    Raises:
        TypeError: If wire is not a string
        ValueError: If wire is not a valid evidence type
    """
    if wire is None:
        raise ValueError("Invalid evidence_type: None (GC-5)")
    
    if not isinstance(wire, str):
        type_name = type(wire).__name__
        raise ValueError(
            f"Invalid evidence_type: {repr(wire)} (expected string, got {type_name}) (GC-5: EVIDENCE_TYPE_INVALID)"
        )
    
    # Exact match, case-sensitive
    try:
        return EvidenceType(wire)
    except ValueError:
        valid_values = [e.value for e in EvidenceType]
        raise ValueError(
            f"Invalid evidence_type: {repr(wire)} "
            f"(must be one of {valid_values}, case-sensitive) (GC-5: EVIDENCE_TYPE_INVALID)"
        )


def parse_evidence_status(wire: Any) -> EvidenceStatus:
    """
    WIRE BOUNDARY PARSER - Parse evidence status from raw input.
    
    Strict rules (GC-5):
    - Must be a JSON string
    - Must be one of: "pass", "fail", "indeterminate"
    - Case-sensitive, exact match
    
    Args:
        wire: Raw value from external source
        
    Returns:
        EvidenceStatus enum
        
    Raises:
        TypeError: If wire is not a string
        ValueError: If wire is not a valid status
    """
    if wire is None:
        raise ValueError("Invalid evidence status: None (GC-5)")
    
    if not isinstance(wire, str):
        type_name = type(wire).__name__
        raise ValueError(
            f"Invalid evidence status: {repr(wire)} (expected string, got {type_name}) (GC-5: EVIDENCE_STATUS_INVALID)"
        )
    
    # Exact match, case-sensitive
    try:
        return EvidenceStatus(wire)
    except ValueError:
        valid_values = [e.value for e in EvidenceStatus]
        raise ValueError(
            f"Invalid evidence status: {repr(wire)} "
            f"(must be one of {valid_values}, case-sensitive) (GC-5: EVIDENCE_STATUS_INVALID)"
        )


def parse_indeterminate_reason(wire: Any) -> IndeterminateReason:
    """
    WIRE BOUNDARY PARSER - Parse indeterminate reason from raw input.
    
    Strict rules (GC-5):
    - Must be a JSON string
    - Must be one of tight enum: unsupported, domain, singularity, timeout, missing_bc_ic, tool_error
    - Case-sensitive, exact match
    
    Args:
        wire: Raw value from external source
        
    Returns:
        IndeterminateReason enum
        
    Raises:
        TypeError: If wire is not a string
        ValueError: If wire is not a valid reason
    """
    if wire is None:
        raise ValueError("Invalid indeterminate_reason: None (GC-5)")
    
    if not isinstance(wire, str):
        type_name = type(wire).__name__
        raise ValueError(
            f"Invalid indeterminate_reason: {repr(wire)} (expected string, got {type_name}) (GC-5: INDETERMINATE_REASON_INVALID)"
        )
    
    # Exact match, case-sensitive
    try:
        return IndeterminateReason(wire)
    except ValueError:
        valid_values = [e.value for e in IndeterminateReason]
        raise ValueError(
            f"Invalid indeterminate_reason: {repr(wire)} "
            f"(must be one of {valid_values}, case-sensitive) (GC-5: INDETERMINATE_REASON_INVALID)"
        )


def parse_evidence_source(wire: Any) -> EvidenceSource:
    """
    WIRE BOUNDARY PARSER - Parse evidence source tagged union from raw input.
    
    Strict rules (GC-5):
    - Must be a JSON object with "kind" and "value" keys
    - kind must be one of: "step_id", "tool_run_id", "citation_id"
    - value must be a strict token (ASCII, no whitespace variants, no invisibles)
    
    Args:
        wire: Raw value from external source
        
    Returns:
        EvidenceSource object
        
    Raises:
        TypeError: If wire is not a dict or fields have wrong types
        ValueError: If wire violates any validation rule
    """
    if wire is None:
        raise ValueError("Invalid evidence source: None (GC-5)")
    
    if not isinstance(wire, dict):
        type_name = type(wire).__name__
        raise TypeError(
            f"Invalid evidence source: {repr(wire)} (expected dict, got {type_name}) (GC-5)"
        )
    
    # Check required keys
    if "kind" not in wire:
        raise ValueError("Invalid evidence source: missing 'kind' field (GC-5)")
    
    if "value" not in wire:
        raise ValueError("Invalid evidence source: missing 'value' field (GC-5)")
    
    # Parse kind
    kind = wire["kind"]
    if not isinstance(kind, str):
        type_name = type(kind).__name__
        raise ValueError(
            f"Invalid evidence source kind: {repr(kind)} (expected string, got {type_name}) (GC-5: SOURCE_KIND_INVALID)"
        )
    
    if kind not in ["step_id", "tool_run_id", "citation_id"]:
        raise ValueError(
            f"Invalid evidence source kind: {repr(kind)} "
            f"(must be 'step_id', 'tool_run_id', or 'citation_id') (GC-5: SOURCE_KIND_INVALID)"
        )
    
    # Parse value with strict token validation
    value = wire["value"]
    if not isinstance(value, str):
        type_name = type(value).__name__
        raise TypeError(
            f"Invalid evidence source value: {repr(value)} (expected string, got {type_name}) (GC-5: SOURCE_VALUE_INVALID)"
        )
    
    if not value or not value.strip():
        raise ValueError("Invalid evidence source value: empty or whitespace-only (GC-5: SOURCE_VALUE_INVALID)")
    
    # Check for unicode invisibles
    _check_unicode_invisibles(value, "evidence source value")
    
    # NO TRIMMING - reject whitespace variants
    if value != value.strip():
        raise ValueError(
            f"Invalid evidence source value: {repr(value)} has leading/trailing whitespace (GC-5: SOURCE_VALUE_INVALID)"
        )
    
    # Check for non-ASCII
    _check_non_ascii(value, "evidence source value")
    
    # Check for internal whitespace
    _check_internal_whitespace(value, "evidence source value")
    
    return EvidenceSource(kind=kind, value=value)


def parse_payload_ref(wire: Any) -> PayloadRef:
    """
    WIRE BOUNDARY PARSER - Parse payload reference tagged union from raw input.
    
    Strict rules (GC-5):
    - Must be a JSON object with "kind" and "value" keys
    - kind must be one of: "log_id", "snippet_ref", "expression_ref"
    - value must be a strict token (ASCII, no whitespace variants, no invisibles)
    
    Args:
        wire: Raw value from external source
        
    Returns:
        PayloadRef object
        
    Raises:
        TypeError: If wire is not a dict or fields have wrong types
        ValueError: If wire violates any validation rule
    """
    if wire is None:
        raise ValueError("Invalid payload_ref: None (GC-5)")
    
    if not isinstance(wire, dict):
        type_name = type(wire).__name__
        raise TypeError(
            f"Invalid payload_ref: {repr(wire)} (expected dict, got {type_name}) (GC-5)"
        )
    
    # Check required keys
    if "kind" not in wire:
        raise ValueError("Invalid payload_ref: missing 'kind' field (GC-5)")
    
    if "value" not in wire:
        raise ValueError("Invalid payload_ref: missing 'value' field (GC-5)")
    
    # Parse kind
    kind = wire["kind"]
    if not isinstance(kind, str):
        type_name = type(kind).__name__
        raise ValueError(
            f"Invalid payload_ref kind: {repr(kind)} (expected string, got {type_name}) (GC-5: PAYLOAD_REF_KIND_INVALID)"
        )
    
    if kind not in ["log_id", "snippet_ref", "expression_ref"]:
        raise ValueError(
            f"Invalid payload_ref kind: {repr(kind)} "
            f"(must be 'log_id', 'snippet_ref', or 'expression_ref') (GC-5: PAYLOAD_REF_KIND_INVALID)"
        )
    
    # Parse value with strict token validation
    value = wire["value"]
    if not isinstance(value, str):
        type_name = type(value).__name__
        raise TypeError(
            f"Invalid payload_ref value: {repr(value)} (expected string, got {type_name}) (GC-5: PAYLOAD_REF_VALUE_INVALID)"
        )
    
    if not value or not value.strip():
        raise ValueError("Invalid payload_ref value: empty or whitespace-only (GC-5: PAYLOAD_REF_VALUE_INVALID)")
    
    # Check for unicode invisibles
    _check_unicode_invisibles(value, "payload_ref value")
    
    # NO TRIMMING - reject whitespace variants
    if value != value.strip():
        raise ValueError(
            f"Invalid payload_ref value: {repr(value)} has leading/trailing whitespace (GC-5: PAYLOAD_REF_VALUE_INVALID)"
        )
    
    # Check for non-ASCII
    _check_non_ascii(value, "payload_ref value")
    
    # Check for internal whitespace
    _check_internal_whitespace(value, "payload_ref value")
    
    return PayloadRef(kind=kind, value=value)


def parse_evidence_object(wire: Any) -> EvidenceObject:
    """
    WIRE BOUNDARY PARSER - Parse complete EvidenceObject from raw input.
    
    Strict rules (GC-5):
    - All required fields must be present
    - All fields must pass their respective parsers
    - evidence_type ↔ source.kind alignment enforced
    - Indeterminate must have reason
    - Notes if present must be non-empty after trim
    
    Args:
        wire: Raw value from external source (expected to be dict)
        
    Returns:
        EvidenceObject with validated fields
        
    Raises:
        TypeError: If wire is not a dict or fields have wrong types
        ValueError: If wire violates any validation rule
    """
    if wire is None:
        raise ValueError("Invalid evidence object: None (GC-5)")
    
    if not isinstance(wire, dict):
        type_name = type(wire).__name__
        raise TypeError(
            f"Invalid evidence object: {repr(wire)} (expected dict, got {type_name}) (GC-5)"
        )
    
    # Check required fields
    required_fields = ["evidence_id", "evidence_type", "source", "status", "payload_ref"]
    for field in required_fields:
        if field not in wire:
            raise ValueError(
                f"Invalid evidence object: missing required field '{field}' (GC-5: EVIDENCE_MISSING_FIELD_{field.upper()})"
            )
    
    # Parse each field with strict validation
    evidence_id = parse_evidence_id(wire["evidence_id"])
    evidence_type = parse_evidence_type(wire["evidence_type"])
    source = parse_evidence_source(wire["source"])
    status = parse_evidence_status(wire["status"])
    payload_ref = parse_payload_ref(wire["payload_ref"])
    
    # Parse optional status_reason
    status_reason = None
    if "status_reason" in wire and wire["status_reason"] is not None:
        status_reason = parse_indeterminate_reason(wire["status_reason"])
    
    # Parse optional notes
    notes = None
    if "notes" in wire and wire["notes"] is not None:
        notes = wire["notes"]
        if not isinstance(notes, str):
            type_name = type(notes).__name__
            raise TypeError(
                f"Invalid notes: {repr(notes)} (expected string, got {type_name}) (GC-5)"
            )
    
    # Construct EvidenceObject (will trigger __post_init__ validation)
    return EvidenceObject(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source=source,
        status=status,
        payload_ref=payload_ref,
        status_reason=status_reason,
        notes=notes,
    )
