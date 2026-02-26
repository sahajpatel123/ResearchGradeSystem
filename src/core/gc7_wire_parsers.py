"""
GC-7 Wire-Boundary Parsers (Strict, Reject-Only)

Parsers for step_status and status_reason with no trimming at wire boundary.
"""

from typing import Any, Optional
from src.core.step import StepStatus


def parse_step_status(wire: Any) -> StepStatus:
    """
    Parse step_status at wire boundary (GC-7).
    
    Strict validation:
    - Must be JSON string
    - Must be exact lowercase token: "unchecked" | "checked" | "failed" | "indeterminate"
    - No trimming, reject whitespace variants
    - No case variants (e.g., "CHECKED" rejected)
    
    Args:
        wire: Value from wire
    
    Returns:
        StepStatus enum member
    
    Raises:
        TypeError: If not a string
        ValueError: If not a valid step_status token (GC-7: STEP_STATUS_INVALID)
    """
    # Type check: must be string
    if wire is None:
        raise ValueError("Invalid step_status: None (GC-7: STEP_STATUS_INVALID)")
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid step_status: must be string, got {type(wire).__name__} (GC-7: STEP_STATUS_INVALID)"
        )
    
    # Empty check
    if wire == "":
        raise ValueError("Invalid step_status: empty string (GC-7: STEP_STATUS_INVALID)")
    
    # Exact token match (lowercase only)
    valid_tokens = {
        "unchecked": StepStatus.UNCHECKED,
        "checked": StepStatus.CHECKED,
        "failed": StepStatus.FAILED,
        "indeterminate": StepStatus.INDETERMINATE,
    }
    
    if wire not in valid_tokens:
        raise ValueError(
            f"Invalid step_status: '{wire}' is not a valid token. "
            f"Must be one of: {list(valid_tokens.keys())} (GC-7: STEP_STATUS_INVALID)"
        )
    
    return valid_tokens[wire]


def parse_status_reason(wire: Any, required: bool = False) -> Optional[str]:
    """
    Parse status_reason at wire boundary (GC-7).
    
    Strict validation:
    - Must be JSON string or null
    - If present, must be non-empty after trim (trim for emptiness check only, not normalization)
    - Reject whitespace-only or invisible-only strings
    - No trimming for storage (store as-is if valid)
    
    Error category taxonomy (GC-7.1a):
    - INDETERMINATE_MISSING_REASON: only when step_status == indeterminate and reason is None/null
    - STATUS_REASON_EMPTY_WHEN_PRESENT: when field is present but empty/whitespace-only/invisible-only
    
    Args:
        wire: Value from wire
        required: If True, None/null triggers error
    
    Returns:
        status_reason string or None
    
    Raises:
        TypeError: If not a string or null
        ValueError: If required but missing, or if empty/whitespace-only/invisible-only
    """
    # None/null handling
    if wire is None:
        if required:
            raise ValueError(
                "Invalid status_reason: None/null when required (GC-7: INDETERMINATE_MISSING_REASON)"
            )
        return None
    
    # Type check: must be string
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid status_reason: must be string or null, got {type(wire).__name__}"
        )
    
    # Empty check (after trim for emptiness only)
    # GC-7.1a: Treat invisible-only strings as empty (Option A - consistency with whitespace-only)
    # Invisible characters: ZWSP (\u200b), NBSP (\u00a0), BOM (\ufeff), WJ (\u2060), ZWNJ (\u200c), ZWJ (\u200d)
    trimmed = wire.strip()
    
    # Check for invisible-only content after ASCII whitespace trim
    # If trimmed is non-empty but contains only invisible Unicode, treat as empty
    if trimmed:
        invisible_chars = {'\u200b', '\u00a0', '\ufeff', '\u2060', '\u200c', '\u200d'}
        if all(c in invisible_chars for c in trimmed):
            trimmed = ""
    
    if trimmed == "":
        # GC-7.1a: Use STATUS_REASON_EMPTY_WHEN_PRESENT for empty/whitespace/invisible-only
        # This applies to both required (indeterminate) and optional (failed) cases
        raise ValueError(
            "Invalid status_reason: empty, whitespace-only, or invisible-only string (GC-7: STATUS_REASON_EMPTY_WHEN_PRESENT)"
        )
    
    # Return as-is (no normalization trimming)
    return wire
