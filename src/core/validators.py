"""
GC-2 Claim Label Validators

Strict validation for claim labels per GC-2:
- EXACTLY 4 labels: DERIVED, COMPUTED, CITED, SPECULATIVE
- Case-sensitive, exact ASCII strings
- No whitespace variants, no lowercase, no lists
- No unicode invisibles (ZWSP, NBSP, etc.)
- No unicode confusables
"""

from typing import Any
from src.core.claim import ClaimLabel


def parse_claim_label(wire: Any) -> ClaimLabel:
    """
    WIRE BOUNDARY PARSER - Single chokepoint for JSON ingestion.
    
    This is the ONLY function that should be used to parse claim labels from
    external sources (JSON, API responses, etc.).
    
    Enforces strict GC-2 validation:
    - Must be string type
    - Must be one of exactly 4 valid labels (case-sensitive, exact ASCII)
    - Rejects whitespace variants (leading/trailing spaces, tabs, newlines)
    - Rejects unicode invisibles (ZWSP U+200B, NBSP U+00A0, etc.)
    - Rejects unicode confusables (Greek/Cyrillic lookalikes)
    - Rejects any non-ASCII characters
    
    Args:
        wire: Input from wire (JSON, API, etc.)
        
    Returns:
        ClaimLabel enum value
        
    Raises:
        TypeError: If input is not a string
        ValueError: If string is not a valid label (exact ASCII match)
    """
    if wire is None:
        raise ValueError("Invalid ClaimLabel: None (GC-2)")
    
    if isinstance(wire, bool):
        raise TypeError(f"Invalid ClaimLabel: {repr(wire)} (expected string, got bool) (GC-2)")
    
    if isinstance(wire, (int, float)):
        raise TypeError(f"Invalid ClaimLabel: {repr(wire)} (expected string, got number) (GC-2)")
    
    if isinstance(wire, list):
        raise TypeError(f"Invalid ClaimLabel: {repr(wire)} (expected string, got list) (GC-2)")
    
    if isinstance(wire, dict):
        raise TypeError(f"Invalid ClaimLabel: {repr(wire)} (expected string, got dict) (GC-2)")
    
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid ClaimLabel: {repr(wire)} (expected string, got {type(wire).__name__}) (GC-2)"
        )
    
    if wire == "":
        raise ValueError("Invalid ClaimLabel: empty string (GC-2)")
    
    # Check for exact ASCII match (no unicode, no invisibles)
    valid_labels = {"DERIVED", "COMPUTED", "CITED", "SPECULATIVE"}
    
    # First check: exact match (fast path)
    if wire in valid_labels:
        # Additional safety: ensure it's pure ASCII
        try:
            wire.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError(
                f"Invalid ClaimLabel: {repr(wire)} contains non-ASCII characters (GC-2)"
            )
        return ClaimLabel[wire]
    
    # Rejection path: provide specific error messages
    # Order matters: check unicode invisibles BEFORE whitespace, since NBSP is both
    
    # Check for unicode invisibles (ZWSP, NBSP, etc.)
    # Common invisibles: U+200B (ZWSP), U+00A0 (NBSP), U+FEFF (BOM), U+2060 (WJ)
    invisible_chars = [
        '\u200b',  # ZWSP
        '\u00a0',  # NBSP
        '\ufeff',  # BOM
        '\u2060',  # Word Joiner
        '\u200c',  # ZWNJ
        '\u200d',  # ZWJ
    ]
    
    for invisible in invisible_chars:
        if invisible in wire:
            raise ValueError(
                f"Invalid ClaimLabel: {repr(wire)} contains invisible unicode character (GC-2)"
            )
    
    # Check for whitespace variants (regular ASCII whitespace)
    if wire.strip() in valid_labels:
        raise ValueError(
            f"Invalid ClaimLabel: {repr(wire)} has invalid whitespace (GC-2)"
        )
    
    # Check for case variants
    if wire.upper() in valid_labels:
        raise ValueError(
            f"Invalid ClaimLabel: {repr(wire)} must be uppercase (expected {wire.upper()}) (GC-2)"
        )
    
    # Check for non-ASCII (catches unicode confusables)
    try:
        wire.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(
            f"Invalid ClaimLabel: {repr(wire)} contains non-ASCII characters (GC-2)"
        )
    
    # Generic invalid label
    raise ValueError(
        f"Invalid ClaimLabel: {repr(wire)} (must be one of: DERIVED, COMPUTED, CITED, SPECULATIVE) (GC-2)"
    )


def validate_claim_label_string(label_str: Any) -> ClaimLabel:
    """
    Validate and parse a claim label string per GC-2.
    
    Enforces:
    - Must be string type
    - Must be one of exactly 4 valid labels (case-sensitive)
    - No whitespace variants
    - No lowercase variants
    
    Args:
        label_str: Input to validate (should be string)
        
    Returns:
        ClaimLabel enum value
        
    Raises:
        TypeError: If input is not a string
        ValueError: If string is not a valid label (exact match)
    """
    if label_str is None:
        raise ValueError("Claim label cannot be None (GC-2)")
    
    if isinstance(label_str, list):
        raise TypeError("Claim label cannot be a list (GC-2)")
    
    if isinstance(label_str, dict):
        raise TypeError("Claim label cannot be a dict (GC-2)")
    
    if not isinstance(label_str, str):
        raise TypeError(
            f"Claim label must be string, got {type(label_str).__name__} (GC-2)"
        )
    
    if label_str == "":
        raise ValueError("Claim label cannot be empty string (GC-2)")
    
    valid_labels = {"DERIVED", "COMPUTED", "CITED", "SPECULATIVE"}
    
    if label_str not in valid_labels:
        if label_str.strip() in valid_labels:
            raise ValueError(
                f"Claim label has invalid whitespace: '{label_str}'. "
                f"Must be exact: {valid_labels} (GC-2)"
            )
        
        if label_str.upper() in valid_labels:
            raise ValueError(
                f"Claim label must be uppercase: got '{label_str}', "
                f"expected '{label_str.upper()}' (GC-2)"
            )
        
        raise ValueError(
            f"Invalid claim label: '{label_str}'. "
            f"Must be one of: {valid_labels} (GC-2)"
        )
    
    return ClaimLabel[label_str]


def validate_claim_label_from_dict(data: dict) -> ClaimLabel:
    """
    Extract and validate claim label from dict (e.g., JSON fixture).
    
    Uses parse_claim_label() as the wire boundary chokepoint.
    
    Args:
        data: Dictionary containing 'claim_label' key
        
    Returns:
        ClaimLabel enum value
        
    Raises:
        KeyError: If 'claim_label' key missing
        TypeError/ValueError: If label value invalid
    """
    if "claim_label" not in data:
        raise KeyError("Missing required field 'claim_label' (GC-2)")
    
    return parse_claim_label(data["claim_label"])
