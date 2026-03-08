"""
GC-12 Wire-Boundary Parsers: Citation and Corpus Provenance.

Strict token parsing with reject-only posture (no trimming normalization).
"""

import hashlib
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

# SHA256 hex pattern: exactly 64 lowercase hex chars
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
            f"{field_name} is missing/null (GC-12: {error_category})"
        )
    if not isinstance(wire, str):
        raise TypeError(
            f"{field_name} must be string, got {type(wire).__name__} "
            f"(GC-12: {error_category})"
        )
    if wire == "":
        raise ValueError(
            f"{field_name} must be non-empty (GC-12: {error_category})"
        )
    if wire != wire.strip():
        raise ValueError(
            f"{field_name} has leading/trailing whitespace (GC-12: {error_category})"
        )
    for invisible in UNICODE_INVISIBLES:
        if invisible in wire:
            raise ValueError(
                f"{field_name} contains unicode invisible character "
                f"(GC-12: {error_category})"
            )
    try:
        wire.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            f"{field_name} contains non-ASCII characters (GC-12: {error_category})"
        )
    return wire


def parse_source_id(wire: Any) -> str:
    """
    Parse source_id as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: CORPUS_SOURCE_MISSING_FIELD
    """
    if wire is None:
        raise ValueError(
            "source_id is missing/null (GC-12: CORPUS_SOURCE_MISSING_FIELD)"
        )
    return _check_strict_token(wire, "source_id", "CORPUS_SOURCE_MISSING_FIELD")


def parse_citation_id(wire: Any) -> str:
    """
    Parse citation_id as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: CITATION_ID_INVALID
    """
    if wire is None:
        raise ValueError(
            "citation_id is missing/null (GC-12: CITATION_ID_INVALID)"
        )
    return _check_strict_token(wire, "citation_id", "CITATION_ID_INVALID")


def parse_chunk_id(wire: Any) -> str:
    """
    Parse chunk_id as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: CITATION_LOCATION_INVALID
    """
    if wire is None:
        raise ValueError(
            "chunk_id is missing/null (GC-12: CITATION_LOCATION_INVALID)"
        )
    return _check_strict_token(wire, "chunk_id", "CITATION_LOCATION_INVALID")


def parse_content_hash(wire: Any) -> str:
    """
    Parse content_hash as hex-encoded SHA256 (64 lowercase hex chars).
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Must be exactly 64 characters
    - Must be lowercase hex only (0-9, a-f)
    
    Error category: CORPUS_SOURCE_HASH_INVALID
    """
    if wire is None:
        raise ValueError(
            "content_hash is missing/null (GC-12: CORPUS_SOURCE_HASH_INVALID)"
        )
    
    token = _check_strict_token(wire, "content_hash", "CORPUS_SOURCE_HASH_INVALID")
    
    if token != token.lower():
        raise ValueError(
            f"content_hash must be lowercase hex, got '{token}' "
            "(GC-12: CORPUS_SOURCE_HASH_INVALID)"
        )
    
    if not SHA256_HEX_PATTERN.match(token):
        raise ValueError(
            f"content_hash must be 64 lowercase hex chars (sha256), got '{token}' "
            f"(length={len(token)}) (GC-12: CORPUS_SOURCE_HASH_INVALID)"
        )
    
    return token


def parse_index_hash(wire: Any) -> str:
    """
    Parse index_hash as hex-encoded SHA256 (64 lowercase hex chars).
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Must be exactly 64 characters
    - Must be lowercase hex only (0-9, a-f)
    
    Error category: SNAPSHOT_REF_INVALID
    """
    if wire is None:
        raise ValueError(
            "index_hash is missing/null (GC-12: SNAPSHOT_REF_INVALID)"
        )
    
    token = _check_strict_token(wire, "index_hash", "SNAPSHOT_REF_INVALID")
    
    if token != token.lower():
        raise ValueError(
            f"index_hash must be lowercase hex, got '{token}' "
            "(GC-12: SNAPSHOT_REF_INVALID)"
        )
    
    if not SHA256_HEX_PATTERN.match(token):
        raise ValueError(
            f"index_hash must be 64 lowercase hex chars (sha256), got '{token}' "
            f"(length={len(token)}) (GC-12: SNAPSHOT_REF_INVALID)"
        )
    
    return token


def parse_snippet_hash(wire: Any) -> str:
    """
    Parse snippet_hash as hex-encoded SHA256 (64 lowercase hex chars).
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Must be exactly 64 characters
    - Must be lowercase hex only (0-9, a-f)
    
    Error category: CITATION_SNIPPET_HASH_INVALID
    """
    if wire is None:
        raise ValueError(
            "snippet_hash is missing/null (GC-12: CITATION_SNIPPET_HASH_INVALID)"
        )
    
    token = _check_strict_token(wire, "snippet_hash", "CITATION_SNIPPET_HASH_INVALID")
    
    if token != token.lower():
        raise ValueError(
            f"snippet_hash must be lowercase hex, got '{token}' "
            "(GC-12: CITATION_SNIPPET_HASH_INVALID)"
        )
    
    if not SHA256_HEX_PATTERN.match(token):
        raise ValueError(
            f"snippet_hash must be 64 lowercase hex chars (sha256), got '{token}' "
            f"(length={len(token)}) (GC-12: CITATION_SNIPPET_HASH_INVALID)"
        )
    
    return token


def parse_retrieval_snapshot_id(wire: Any) -> str:
    """
    Parse retrieval_snapshot_id as strict token.
    
    Rules:
    - Strict token validation (no trimming, reject-only)
    - Non-empty string
    
    Error category: SNAPSHOT_REF_INVALID
    """
    if wire is None:
        raise ValueError(
            "retrieval_snapshot_id is missing/null (GC-12: SNAPSHOT_REF_INVALID)"
        )
    return _check_strict_token(wire, "retrieval_snapshot_id", "SNAPSHOT_REF_INVALID")


def compute_snippet_hash(snippet: str) -> str:
    """
    Compute snippet_hash from exact snippet text.
    
    GC-12 FROZEN DEFINITION:
    snippet_hash = sha256(exact snippet bytes encoded as UTF-8)
    
    NO normalization, truncation, or UI rendering.
    The snippet is hashed EXACTLY as provided, byte-for-byte.
    
    Args:
        snippet: The exact snippet text to hash
        
    Returns:
        64-character lowercase hex SHA256 hash
    """
    # Encode snippet as UTF-8 bytes exactly as provided
    snippet_bytes = snippet.encode("utf-8")
    # Compute SHA256 hash
    hash_hex = hashlib.sha256(snippet_bytes).hexdigest()
    return hash_hex
