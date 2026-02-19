"""
GC-4 Evidence Attachment Validators

Wire-boundary parsing and fail-closed validation for evidence requirements.

Validation Rules:
- NON_SPEC_MISSING_EVIDENCE: Non-SPECULATIVE claims must have ≥1 evidence_id
- SPEC_MISSING_VERIFY_FALSIFY: SPECULATIVE claims must have verify_falsify
- DANGLING_EVIDENCE_ID: evidence_ids must resolve to report.evidence[]
- EVIDENCE_ID_DUP_IN_CLAIM: No duplicate evidence_ids within claim
- EVIDENCE_ID_EMPTY: evidence_ids cannot be empty/whitespace
- EVIDENCE_IDS_WRONG_TYPE: evidence_ids must be list of strings
"""

from typing import Any
from src.core.claim import Claim, ClaimLabel
from src.core.report import ScientificReport


def parse_evidence_id(wire: Any) -> str:
    """
    WIRE BOUNDARY PARSER - Single chokepoint for evidence_id parsing.
    
    This is the ONLY function that should parse individual evidence_ids from
    external sources (JSON, API responses, etc.).
    
    Strict rules (GC-4 wire-boundary hardening):
    - Accept ONLY exact ASCII strings with NO leading/trailing whitespace
    - NO TRIMMING: Reject whitespace variants deterministically
    - Reject: non-string types, empty strings, whitespace-only strings
    - Reject: leading/trailing whitespace (space, tab, newline, etc.)
    - Reject: unicode invisibles (ZWSP, NBSP, etc.)
    - Reject: unicode confusables (non-ASCII characters)
    
    Args:
        wire: Raw value from external source
        
    Returns:
        Validated evidence_id string (exact, no normalization)
        
    Raises:
        TypeError: If wire is not a string
        ValueError: If wire is empty, has whitespace variants, or contains invalid characters
    """
    # Type check: must be string
    if wire is None:
        raise ValueError("Invalid evidence_id: None (GC-4)")
    
    if not isinstance(wire, str):
        type_name = type(wire).__name__
        raise TypeError(
            f"Invalid evidence_id: {repr(wire)} (expected string, got {type_name}) (GC-4)"
        )
    
    # Empty check
    if wire == "":
        raise ValueError("Invalid evidence_id: empty string (GC-4)")
    
    # Check for unicode invisibles FIRST (before whitespace checks)
    # Common invisibles: U+200B (ZWSP), U+00A0 (NBSP), U+FEFF (BOM), U+2060 (WJ)
    # Note: NBSP is both invisible AND whitespace, so check invisibles first
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
                f"Invalid evidence_id: {repr(wire)} contains invisible unicode character (GC-4)"
            )
    
    # Whitespace-only check
    if not wire.strip():
        raise ValueError(
            f"Invalid evidence_id: {repr(wire)} is whitespace-only (GC-4)"
        )
    
    # GC-4 WIRE-BOUNDARY HARDENING: NO TRIMMING
    # Reject any leading/trailing whitespace variants
    if wire != wire.strip():
        raise ValueError(
            f"Invalid evidence_id: {repr(wire)} has leading/trailing whitespace "
            f"(GC-4: whitespace variants rejected at wire boundary)"
        )
    
    # Check for non-ASCII (catches unicode confusables)
    try:
        wire.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(
            f"Invalid evidence_id: {repr(wire)} contains non-ASCII characters (GC-4)"
        )
    
    # Return exact value (NO TRIMMING)
    return wire


def parse_evidence_ids(wire: Any) -> list[str]:
    """
    WIRE BOUNDARY PARSER - Parse list of evidence_ids.
    
    Strict rules (GC-4):
    - Accept ONLY a list of strings
    - Each entry must pass parse_evidence_id()
    - Reject duplicates within the list
    
    Args:
        wire: Raw value from external source
        
    Returns:
        Validated list of evidence_id strings
        
    Raises:
        TypeError: If wire is not a list or contains non-strings
        ValueError: If any evidence_id is invalid or duplicates exist
    """
    # Type check: must be list
    if not isinstance(wire, list):
        type_name = type(wire).__name__
        raise TypeError(
            f"Invalid evidence_ids: {repr(wire)} (expected list, got {type_name}) (GC-4)"
        )
    
    # Parse each evidence_id
    parsed_ids = []
    for idx, item in enumerate(wire):
        try:
            parsed_id = parse_evidence_id(item)
            parsed_ids.append(parsed_id)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid evidence_ids[{idx}]: {str(e)}"
            ) from e
    
    # Check for duplicates
    if len(parsed_ids) != len(set(parsed_ids)):
        duplicates = [eid for eid in parsed_ids if parsed_ids.count(eid) > 1]
        raise ValueError(
            f"Invalid evidence_ids: duplicate entries found: {set(duplicates)} "
            f"(GC-4: EVIDENCE_ID_DUP_IN_CLAIM)"
        )
    
    return parsed_ids


class EvidenceValidator:
    """
    GC-4 evidence attachment validator.
    
    Enforces fail-closed validation of evidence requirements.
    """
    
    @staticmethod
    def validate_claim_evidence(claim: Claim, report: ScientificReport) -> tuple[bool, list[str]]:
        """
        Validate evidence requirements for a single claim.
        
        Returns:
            (is_valid, errors) where errors are error category strings
        """
        errors = []
        
        # Rule: NON_SPEC_MISSING_EVIDENCE
        if claim.claim_label != ClaimLabel.SPECULATIVE:
            if not claim.evidence_ids or len(claim.evidence_ids) == 0:
                errors.append(
                    f"NON_SPEC_MISSING_EVIDENCE: Claim {claim.claim_id} "
                    f"(label={claim.claim_label.value}) must have ≥1 evidence_id (GC-4)"
                )
        
        # Rule: SPEC_MISSING_VERIFY_FALSIFY
        if claim.claim_label == ClaimLabel.SPECULATIVE:
            if claim.verify_falsify is None or not claim.verify_falsify.strip():
                errors.append(
                    f"SPEC_MISSING_VERIFY_FALSIFY: Claim {claim.claim_id} "
                    f"(label=SPECULATIVE) must have non-empty verify_falsify (GC-4)"
                )
        
        # Rule: EVIDENCE_ID_EMPTY (check each evidence_id)
        for idx, eid in enumerate(claim.evidence_ids):
            if not eid or not eid.strip():
                errors.append(
                    f"EVIDENCE_ID_EMPTY: Claim {claim.claim_id} evidence_ids[{idx}] "
                    f"is empty or whitespace-only (GC-4)"
                )
        
        # Rule: EVIDENCE_ID_DUP_IN_CLAIM
        if len(claim.evidence_ids) != len(set(claim.evidence_ids)):
            duplicates = [eid for eid in claim.evidence_ids if claim.evidence_ids.count(eid) > 1]
            errors.append(
                f"EVIDENCE_ID_DUP_IN_CLAIM: Claim {claim.claim_id} has duplicate evidence_ids: "
                f"{set(duplicates)} (GC-4)"
            )
        
        # Rule: DANGLING_EVIDENCE_ID
        existing_evidence_ids = {e.evidence_id for e in report.evidence}
        for eid in claim.evidence_ids:
            if eid and eid.strip() and eid not in existing_evidence_ids:
                errors.append(
                    f"DANGLING_EVIDENCE_ID: Claim {claim.claim_id} references non-existent "
                    f"evidence_id: {eid} (GC-4)"
                )
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def validate_report_evidence(report: ScientificReport) -> tuple[bool, list[str]]:
        """
        Validate evidence requirements for entire report.
        
        Returns:
            (is_valid, errors) where errors are error category strings
        """
        all_errors = []
        
        for claim in report.claims:
            is_valid, errors = EvidenceValidator.validate_claim_evidence(claim, report)
            all_errors.extend(errors)
        
        return (len(all_errors) == 0, all_errors)


def validate_evidence_attachment(report: ScientificReport) -> tuple[bool, list[str]]:
    """
    Convenience function for validating evidence attachment.
    
    Returns:
        (is_valid, errors) where is_valid is True if no errors, False otherwise
    """
    return EvidenceValidator.validate_report_evidence(report)
