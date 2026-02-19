"""
GC-5 Evidence Object Validators

Fail-closed validation for EvidenceObject with deterministic error categories.

Validation rules:
- All required fields present
- Strict enum validation
- Tagged union validation
- evidence_type ↔ source.kind alignment
- Indeterminate must have reason
- Payload ref required
- Notes if present must be non-empty
- Evidence ID collision detection in report
"""

from typing import List, Tuple
from src.core.evidence import EvidenceObject, EvidenceType
from src.core.report import ScientificReport


class GC5ValidationError:
    """Structured validation error for GC-5"""
    
    def __init__(self, category: str, message: str):
        self.category = category
        self.message = message
    
    def __str__(self) -> str:
        return f"{self.category}: {self.message}"
    
    def __repr__(self) -> str:
        return f"GC5ValidationError(category={self.category!r}, message={self.message!r})"


def validate_evidence_object(evidence: EvidenceObject) -> Tuple[bool, List[str]]:
    """
    Validate a single EvidenceObject.
    
    Note: Most validation happens in EvidenceObject.__post_init__().
    This function is for additional validation that requires context.
    
    Args:
        evidence: EvidenceObject to validate
        
    Returns:
        Tuple of (is_valid, errors)
        - is_valid: True if no errors, False otherwise
        - errors: List of error messages
    """
    errors = []
    
    # Most validation is already done in __post_init__
    # This is a placeholder for any additional context-dependent validation
    
    return (len(errors) == 0, errors)


def validate_report_evidence(report: ScientificReport) -> Tuple[bool, List[str]]:
    """
    Validate all evidence objects in a report (GC-5).
    
    Validation rules:
    - All EvidenceObjects must be valid (checked via construction)
    - No duplicate evidence_ids (EVIDENCE_ID_COLLISION)
    
    Args:
        report: ScientificReport with evidence list
        
    Returns:
        Tuple of (is_valid, errors)
        - is_valid: True if no errors, False otherwise
        - errors: List of error messages with deterministic categories
    """
    errors = []
    
    # Check for evidence_id collisions (already done in ScientificReport.__post_init__)
    # But we can add additional validation here if needed
    
    # Validate each evidence object
    for evidence in report.evidence:
        is_valid, evidence_errors = validate_evidence_object(evidence)
        if not is_valid:
            errors.extend(evidence_errors)
    
    return (len(errors) == 0, errors)


def validate_evidence_type_source_alignment(
    evidence_type: EvidenceType, 
    source_kind: str
) -> Tuple[bool, str]:
    """
    Validate evidence_type ↔ source.kind alignment.
    
    Alignment rules (GC-5):
    - derivation -> step_id
    - computation -> tool_run_id
    - citation -> citation_id
    
    Args:
        evidence_type: EvidenceType enum
        source_kind: Source kind string
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if aligned, False otherwise
        - error_message: Empty string if valid, error message otherwise
    """
    alignment = {
        EvidenceType.DERIVATION: "step_id",
        EvidenceType.COMPUTATION: "tool_run_id",
        EvidenceType.CITATION: "citation_id",
    }
    
    expected_kind = alignment[evidence_type]
    if source_kind != expected_kind:
        error_msg = (
            f"EVIDENCE_SOURCE_KIND_MISMATCH: evidence_type={evidence_type.value} "
            f"requires source.kind={expected_kind}, got {source_kind}"
        )
        return (False, error_msg)
    
    return (True, "")
