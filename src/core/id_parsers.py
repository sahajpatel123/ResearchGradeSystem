"""
ID Wire-Boundary Parsers (GC-6.1)

Strict parsers for claim_id, step_id, tool_run_id, citation_id.
Reject-only posture (no trimming), matching GC-2/GC-4 wire-boundary hardening.
"""

from typing import Any


# Unicode invisible characters to reject
UNICODE_INVISIBLES = [
    '\u200B',  # ZWSP (Zero Width Space)
    '\u00A0',  # NBSP (Non-Breaking Space)
    '\uFEFF',  # BOM (Byte Order Mark)
    '\u2060',  # WJ (Word Joiner)
    '\u200C',  # ZWNJ (Zero Width Non-Joiner)
    '\u200D',  # ZWJ (Zero Width Joiner)
]


def _check_id_string(wire: Any, id_type: str) -> str:
    """
    Common validation logic for all ID types.
    
    Rules:
    - Must be JSON string
    - Must be ASCII-only
    - Must contain no invisibles (ZWSP/NBSP/BOM/WJ/ZWNJ/ZWJ)
    - Must have NO leading/trailing whitespace (reject, do not trim)
    - Must be non-empty
    
    Args:
        wire: Value from wire (any type)
        id_type: Type of ID for error messages (e.g., "claim_id")
    
    Returns:
        Validated ID string
    
    Raises:
        TypeError: If wire is not a string
        ValueError: If validation fails
    """
    # Type check: must be string
    if wire is None:
        raise ValueError(f"Invalid {id_type}: None")
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid {id_type}: must be string, got {type(wire).__name__}"
        )
    
    # Empty check
    if wire == "":
        raise ValueError(f"Invalid {id_type}: empty string")
    
    # Check for unicode invisibles FIRST (before whitespace check)
    for invisible in UNICODE_INVISIBLES:
        if invisible in wire:
            raise ValueError(
                f"Invalid {id_type}: contains unicode invisible character "
                f"(U+{ord(invisible):04X})"
            )
    
    # Check for leading/trailing whitespace (REJECT, do not trim)
    if wire != wire.strip():
        raise ValueError(
            f"Invalid {id_type}: has leading/trailing whitespace (no trimming)"
        )
    
    # Check for non-ASCII characters
    try:
        wire.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(
            f"Invalid {id_type}: contains non-ASCII characters"
        )
    
    return wire


def parse_claim_id(wire: Any) -> str:
    """
    Parse claim_id at wire boundary (GC-6.1).
    
    Strict validation:
    - Must be ASCII string
    - No invisibles (ZWSP/NBSP/BOM/WJ/ZWNJ/ZWJ)
    - No leading/trailing whitespace (reject, do not trim)
    - Non-empty
    
    Args:
        wire: Value from wire
    
    Returns:
        Validated claim_id string
    
    Raises:
        TypeError: If not a string
        ValueError: If validation fails
    """
    return _check_id_string(wire, "claim_id")


def parse_step_id(wire: Any) -> str:
    """
    Parse step_id at wire boundary (GC-6.1).
    
    Strict validation:
    - Must be ASCII string
    - No invisibles (ZWSP/NBSP/BOM/WJ/ZWNJ/ZWJ)
    - No leading/trailing whitespace (reject, do not trim)
    - Non-empty
    
    Args:
        wire: Value from wire
    
    Returns:
        Validated step_id string
    
    Raises:
        TypeError: If not a string
        ValueError: If validation fails
    """
    return _check_id_string(wire, "step_id")


def parse_tool_run_id(wire: Any) -> str:
    """
    Parse tool_run_id at wire boundary (GC-6.1).
    
    Strict validation:
    - Must be ASCII string
    - No invisibles (ZWSP/NBSP/BOM/WJ/ZWNJ/ZWJ)
    - No leading/trailing whitespace (reject, do not trim)
    - Non-empty
    
    Args:
        wire: Value from wire
    
    Returns:
        Validated tool_run_id string
    
    Raises:
        TypeError: If not a string
        ValueError: If validation fails
    """
    return _check_id_string(wire, "tool_run_id")


def parse_citation_id(wire: Any) -> str:
    """
    Parse citation_id at wire boundary (GC-6.1).
    
    Strict validation:
    - Must be ASCII string
    - No invisibles (ZWSP/NBSP/BOM/WJ/ZWNJ/ZWJ)
    - No leading/trailing whitespace (reject, do not trim)
    - Non-empty
    
    Args:
        wire: Value from wire
    
    Returns:
        Validated citation_id string
    
    Raises:
        TypeError: If not a string
        ValueError: If validation fails
    """
    return _check_id_string(wire, "citation_id")
