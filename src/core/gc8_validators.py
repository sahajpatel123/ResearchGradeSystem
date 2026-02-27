"""
GC-8 Derivation Step Validity Validators

Prevents fake steps through structural enforcement and warning-only policy.

Responsibility split:
- GC-3 owns: claim_ids resolution, unique ownership, no orphan claims
- GC-8 owns: claim_ids non-empty (structural), statement non-empty, placeholder detection (warning-only)

Validation layering:
1) Parse step fields/types (handled by DerivationStep.__post_init__)
2) GC-8 hard structural validation (claim_ids non-empty, statement non-empty)
3) GC-8 policy warning checks (placeholder phrases - warning-only, no hard fail)
"""

from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class GC8ValidationError:
    """GC-8 validation error."""
    category: str
    message: str
    step_id: Optional[str] = None


@dataclass
class GC8PolicyWarning:
    """GC-8 policy warning (does not block validation)."""
    warning_id: str
    message: str
    step_id: str


# Placeholder phrase patterns (warning-only detection)
PLACEHOLDER_PHRASES = [
    # Vague progress indicators
    "using standard methods",
    "after simplification",
    "it is obvious",
    "therefore the answer follows",
    "now continue solving",
    "by inspection",
    "clearly we have",
    "trivially",
    "without loss of generality",
    # Narrative laundering
    "as we can see",
    "as shown above",
    "from the previous step",
    "continuing from before",
    # Weak action semantics
    "we get",
    "we obtain",
    "we have",
    "this gives",
    "this yields",
]


def parse_statement(wire: Any) -> str:
    """
    Parse statement at wire boundary (GC-8).
    
    Strict validation:
    - Must be JSON string
    - Must be non-empty after trim (trim for emptiness check only, not normalization)
    - Reject whitespace-only or invisible-only strings
    - No trimming for storage (store as-is if valid)
    
    Args:
        wire: Value from wire
    
    Returns:
        statement string
    
    Raises:
        TypeError: If not a string
        ValueError: If empty/whitespace-only/invisible-only
    """
    # None/null handling
    if wire is None:
        raise ValueError(
            "Invalid statement: None/null (GC-8: DERIVATION_STEP_EMPTY_STATEMENT)"
        )
    
    # Type check: must be string
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid statement: must be string, got {type(wire).__name__} (GC-8: DERIVATION_STEP_STATEMENT_INVALID_TYPE)"
        )
    
    # Empty check (after trim for emptiness only)
    # GC-8: Treat invisible-only strings as empty (consistency with GC-7.1a)
    trimmed = wire.strip()
    
    # Check for invisible-only content after ASCII whitespace trim
    if trimmed:
        invisible_chars = {'\u200b', '\u00a0', '\ufeff', '\u2060', '\u200c', '\u200d'}
        if all(c in invisible_chars for c in trimmed):
            trimmed = ""
    
    if trimmed == "":
        raise ValueError(
            "Invalid statement: empty, whitespace-only, or invisible-only string (GC-8: DERIVATION_STEP_EMPTY_STATEMENT)"
        )
    
    # Return as-is (no normalization trimming)
    return wire


def validate_step_object(step_wire: dict) -> tuple[dict, list[GC8ValidationError]]:
    """
    Validate step object at wire boundary (GC-8 hard validation only).
    
    This performs GC-8 structural validation:
    - statement must be non-empty
    - claim_ids must be non-empty list
    
    Note: GC-3 owns claim_ids resolution/ownership checks.
    GC-8 only checks structural validity (non-empty).
    
    Args:
        step_wire: Step object from wire
    
    Returns:
        Tuple of (parsed_step_dict, errors)
    """
    errors = []
    parsed = {}
    
    # Parse statement (GC-8 hard validation)
    try:
        statement = parse_statement(step_wire.get("statement"))
        parsed["statement"] = statement
    except (TypeError, ValueError) as e:
        errors.append(GC8ValidationError(
            category="DERIVATION_STEP_EMPTY_STATEMENT" if "empty" in str(e).lower() else "DERIVATION_STEP_STATEMENT_INVALID_TYPE",
            message=str(e),
            step_id=step_wire.get("step_id", "unknown")
        ))
    
    # Validate claim_ids is non-empty (GC-8 structural check)
    # Note: GC-3 owns resolution/ownership, GC-8 only checks non-empty
    claim_ids = step_wire.get("claim_ids")
    if claim_ids is None:
        errors.append(GC8ValidationError(
            category="DERIVATION_STEP_EMPTY_CLAIM_IDS",
            message="claim_ids is None/null (GC-8: structural check)",
            step_id=step_wire.get("step_id", "unknown")
        ))
    elif not isinstance(claim_ids, list):
        errors.append(GC8ValidationError(
            category="DERIVATION_STEP_EMPTY_CLAIM_IDS",
            message=f"claim_ids must be list, got {type(claim_ids).__name__}",
            step_id=step_wire.get("step_id", "unknown")
        ))
    elif len(claim_ids) == 0:
        errors.append(GC8ValidationError(
            category="DERIVATION_STEP_EMPTY_CLAIM_IDS",
            message="claim_ids is empty list (GC-8: structural check)",
            step_id=step_wire.get("step_id", "unknown")
        ))
    else:
        parsed["claim_ids"] = claim_ids
    
    return parsed, errors


def gc8_policy_warnings(step_id: str, statement: str) -> list[GC8PolicyWarning]:
    """
    GC-8 policy warning checks (warning-only, does not block validation).
    
    Detects placeholder phrases and fake-progress patterns.
    These are warnings only - structurally valid steps with vague placeholder text
    will PASS validation but emit warnings.
    
    Args:
        step_id: Step identifier
        statement: Step statement text
    
    Returns:
        List of policy warnings (empty if no warnings)
    """
    warnings = []
    
    # Normalize statement for pattern matching (lowercase, strip)
    normalized = statement.lower().strip()
    
    # Check for placeholder phrases
    for phrase in PLACEHOLDER_PHRASES:
        if phrase in normalized:
            warnings.append(GC8PolicyWarning(
                warning_id="DERIVATION_STEP_FAKE_PLACEHOLDER_WARNING",
                message=f"Step contains placeholder phrase: '{phrase}' (GC-8: warning-only, does not block validation)",
                step_id=step_id
            ))
            # Only report first match to avoid noise
            break
    
    # Additional heuristics (optional, can be extended)
    # Check for very short statements (potential fake progress)
    if len(normalized) < 10:
        warnings.append(GC8PolicyWarning(
            warning_id="DERIVATION_STEP_WEAK_ACTION_SEMANTICS_WARNING",
            message=f"Step statement is very short ({len(normalized)} chars) - may lack semantic content (GC-8: warning-only)",
            step_id=step_id
        ))
    
    return warnings


def validate_and_warn_step(step_wire: dict) -> tuple[dict, list[GC8ValidationError], list[GC8PolicyWarning]]:
    """
    Full GC-8 validation pipeline: hard validation + policy warnings.
    
    Validation layering:
    1) Parse step fields/types
    2) GC-8 hard structural validation (claim_ids non-empty, statement non-empty)
    3) GC-8 policy warning checks (placeholder phrases - warning-only)
    
    Args:
        step_wire: Step object from wire
    
    Returns:
        Tuple of (parsed_step_dict, hard_errors, policy_warnings)
    """
    # Step 1 & 2: Parse and hard validate
    parsed, errors = validate_step_object(step_wire)
    
    # Step 3: Policy warnings (only if hard validation passed)
    warnings = []
    if not errors and "statement" in parsed:
        warnings = gc8_policy_warnings(
            step_id=step_wire.get("step_id", "unknown"),
            statement=parsed["statement"]
        )
    
    return parsed, errors, warnings
