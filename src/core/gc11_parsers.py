"""
GC-11 Wire-Boundary Parsers: run_id and input_hash.

Strict token parsing with reject-only posture (no trimming normalization).
"""

import re
from typing import Any


UNICODE_INVISIBLES = {
    "\u200b",  # ZWSP
    "\u00a0",  # NBSP
    "\ufeff",  # BOM
    "\u2060",  # WJ
    "\u200c",  # ZWNJ
    "\u200d",  # ZWJ
}

# UUID v4 pattern: 8-4-4-4-12 hex chars with hyphens
# Example: 550e8400-e29b-41d4-a716-446655440000
UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE
)

# Hex-encoded SHA256 pattern: exactly 64 lowercase hex chars
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _check_strict_token(wire: Any, field_name: str, error_category: str) -> str:
    """
    Common strict token validation (no trimming, reject-only).
    
    Rules:
    - Must be string
    - Must be non-empty
    - No leading/trailing whitespace
    - No unicode invisible characters
    - Must be ASCII-only
    """
    if wire is None:
        raise ValueError(
            f"{field_name} is missing/null (GC-11: {error_category})"
        )
    if not isinstance(wire, str):
        raise TypeError(
            f"{field_name} must be string, got {type(wire).__name__} "
            f"(GC-11: {error_category})"
        )
    if wire == "":
        raise ValueError(
            f"{field_name} must be non-empty (GC-11: {error_category})"
        )
    if wire != wire.strip():
        raise ValueError(
            f"{field_name} has leading/trailing whitespace (GC-11: {error_category})"
        )
    for invisible in UNICODE_INVISIBLES:
        if invisible in wire:
            raise ValueError(
                f"{field_name} contains unicode invisible character "
                f"(GC-11: {error_category})"
            )
    try:
        wire.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            f"{field_name} contains non-ASCII characters (GC-11: {error_category})"
        )
    return wire


def parse_run_id(wire: Any) -> str:
    """
    Parse run_id as strict UUID v4 token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Must match UUID v4 pattern: 8-4-4-4-12 hex with hyphens
    - Version nibble must be 4
    - Variant nibble must be 8, 9, a, or b
    
    Error category: RUN_ID_INVALID or RUN_ID_MISSING
    """
    if wire is None:
        raise ValueError(
            "run_id is missing/null (GC-11: RUN_ID_MISSING)"
        )
    
    token = _check_strict_token(wire, "run_id", "RUN_ID_INVALID")
    
    if not UUID_V4_PATTERN.match(token):
        raise ValueError(
            f"run_id must be UUID v4 format (8-4-4-4-12 hex), got '{token}' "
            "(GC-11: RUN_ID_INVALID)"
        )
    
    return token.lower()


def parse_input_hash(wire: Any) -> str:
    """
    Parse input_hash as hex-encoded SHA256 (64 lowercase hex chars).
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Must be exactly 64 characters
    - Must be lowercase hex only (0-9, a-f)
    
    Error category: INPUT_HASH_INVALID or INPUT_HASH_MISSING
    """
    if wire is None:
        raise ValueError(
            "input_hash is missing/null (GC-11: INPUT_HASH_MISSING)"
        )
    
    token = _check_strict_token(wire, "input_hash", "INPUT_HASH_INVALID")
    
    # Enforce lowercase
    if token != token.lower():
        raise ValueError(
            f"input_hash must be lowercase hex, got '{token}' "
            "(GC-11: INPUT_HASH_INVALID)"
        )
    
    if not SHA256_HEX_PATTERN.match(token):
        raise ValueError(
            f"input_hash must be 64 lowercase hex chars (sha256), got '{token}' "
            f"(length={len(token)}) (GC-11: INPUT_HASH_INVALID)"
        )
    
    return token


def parse_commit_hash(wire: Any) -> str:
    """
    Parse commit_hash as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    - No specific format enforced (git short/long hash both allowed)
    
    Error category: COMMIT_HASH_MISSING
    """
    if wire is None:
        raise ValueError(
            "commit_hash is missing/null (GC-11: COMMIT_HASH_MISSING)"
        )
    
    return _check_strict_token(wire, "commit_hash", "COMMIT_HASH_MISSING")


def parse_dependency_lock_hash(wire: Any) -> str:
    """
    Parse dependency_lock_hash as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: LOCK_HASH_MISSING
    """
    if wire is None:
        raise ValueError(
            "dependency_lock_hash is missing/null (GC-11: LOCK_HASH_MISSING)"
        )
    
    return _check_strict_token(wire, "dependency_lock_hash", "LOCK_HASH_MISSING")


def parse_payload_ref(wire: Any) -> str:
    """
    Parse payload_ref as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: LOG_REFERENCE_INVALID
    """
    if wire is None:
        raise ValueError(
            "payload_ref is missing/null (GC-11: LOG_REFERENCE_INVALID)"
        )
    
    return _check_strict_token(wire, "payload_ref", "LOG_REFERENCE_INVALID")


def parse_log_id(wire: Any) -> str:
    """
    Parse log_id as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: LOG_REFERENCE_INVALID
    """
    if wire is None:
        raise ValueError(
            "log_id is missing/null (GC-11: LOG_REFERENCE_INVALID)"
        )
    
    return _check_strict_token(wire, "log_id", "LOG_REFERENCE_INVALID")
