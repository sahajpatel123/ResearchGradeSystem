"""
GC-13 Validators: Completion Gate Validation.

Implements all validation rules for GC-13 Completion Gate.
GC-13 runs AFTER GC-1..GC-12 validations as the single final gate.
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.gc13_computation import (
    ReportArtifacts,
    compute_missing_artifacts,
    compute_report_status,
)
from src.core.report_checks import (
    CheckResult,
    CheckStatus,
    ReportChecks,
    ReportStatus,
    REQUIRED_CHECK_FIELDS,
)


@dataclass
class GC13ValidationError:
    """GC-13 validation error with category and message."""
    category: str
    message: str
    field: Optional[str] = None
    is_warning: bool = False


def validate_check_status(status_str: str) -> tuple[bool, Optional[CheckStatus]]:
    """
    Validate check status string.
    
    Returns:
        (is_valid, CheckStatus or None)
    """
    try:
        return True, CheckStatus(status_str)
    except ValueError:
        return False, None


def validate_check_result(
    check_name: str,
    check_result: CheckResult
) -> list[GC13ValidationError]:
    """
    Validate a single CheckResult.
    
    Rules:
    - status must be valid CheckStatus
    - NOT_APPLICABLE requires non-empty reason
    """
    errors = []
    
    # Status validation is done in CheckResult.__post_init__
    # Here we validate additional rules
    
    if check_result.status == CheckStatus.NOT_APPLICABLE:
        if check_result.reason is None:
            errors.append(GC13ValidationError(
                category="CHECK_NOT_APPLICABLE_MISSING_REASON",
                message=f"{check_name} has status NOT_APPLICABLE but no reason provided "
                        "(GC-13: CHECK_NOT_APPLICABLE_MISSING_REASON)",
                field=f"checks.{check_name}.reason"
            ))
        elif not isinstance(check_result.reason, str):
            errors.append(GC13ValidationError(
                category="CHECK_NOT_APPLICABLE_MISSING_REASON",
                message=f"{check_name} reason must be string "
                        "(GC-13: CHECK_NOT_APPLICABLE_MISSING_REASON)",
                field=f"checks.{check_name}.reason"
            ))
        elif check_result.reason.strip() == "":
            errors.append(GC13ValidationError(
                category="CHECK_NOT_APPLICABLE_MISSING_REASON",
                message=f"{check_name} reason must be non-empty (not whitespace-only) "
                        "(GC-13: CHECK_NOT_APPLICABLE_MISSING_REASON)",
                field=f"checks.{check_name}.reason"
            ))
    
    return errors


def validate_report_checks(checks: ReportChecks) -> list[GC13ValidationError]:
    """
    Validate ReportChecks (closed v0 registry).
    
    Rules:
    - All 5 check fields must be present
    - Each check must have valid status
    - NOT_APPLICABLE requires reason
    """
    errors = []
    
    all_checks = checks.get_all_checks()
    
    # Validate each check
    for check_name, check_result in all_checks.items():
        check_errors = validate_check_result(check_name, check_result)
        errors.extend(check_errors)
    
    return errors


def validate_checks_from_wire(wire_checks: dict) -> list[GC13ValidationError]:
    """
    Validate checks from wire data (before conversion to ReportChecks).
    
    Rules:
    - All required check fields must be present
    - No extra fields allowed (warning only)
    """
    errors = []
    
    # Check for missing required fields
    for field_name in REQUIRED_CHECK_FIELDS:
        if field_name not in wire_checks:
            errors.append(GC13ValidationError(
                category="CHECK_STATUS_MISSING",
                message=f"Required check field '{field_name}' is missing "
                        "(GC-13: CHECK_STATUS_MISSING)",
                field=f"checks.{field_name}"
            ))
    
    # Check for invalid status values
    for field_name in REQUIRED_CHECK_FIELDS:
        if field_name in wire_checks:
            check_data = wire_checks[field_name]
            if isinstance(check_data, dict):
                status_str = check_data.get("status")
                if status_str is not None:
                    is_valid, _ = validate_check_status(status_str)
                    if not is_valid:
                        errors.append(GC13ValidationError(
                            category="CHECK_STATUS_INVALID",
                            message=f"Invalid check status '{status_str}' for {field_name} "
                                    "(GC-13: CHECK_STATUS_INVALID)",
                            field=f"checks.{field_name}.status"
                        ))
    
    return errors


def validate_status_mismatch(
    wire_status: Optional[str],
    computed_status: ReportStatus
) -> list[GC13ValidationError]:
    """
    Validate that wire status matches computed status.
    
    GC-13: status is computed-only; mismatch is failure.
    """
    errors = []
    
    if wire_status is None:
        return errors
    
    if wire_status != computed_status.value:
        errors.append(GC13ValidationError(
            category="REPORT_STATUS_MISMATCH",
            message=f"Wire status '{wire_status}' does not match computed status '{computed_status.value}' "
                    "(GC-13: REPORT_STATUS_MISMATCH)",
            field="status"
        ))
    
    return errors


def validate_missing_artifacts_mismatch(
    wire_missing: Optional[list[str]],
    computed_missing: list[str]
) -> list[GC13ValidationError]:
    """
    Validate that wire missing_artifacts matches computed missing_artifacts.
    
    GC-13: missing_artifacts is computed-only; mismatch is failure.
    """
    errors = []
    
    if wire_missing is None:
        return errors
    
    # Sort both for comparison
    wire_sorted = sorted(wire_missing)
    computed_sorted = sorted(computed_missing)
    
    if wire_sorted != computed_sorted:
        errors.append(GC13ValidationError(
            category="MISSING_ARTIFACTS_MISMATCH",
            message=f"Wire missing_artifacts {wire_sorted} does not match computed {computed_sorted} "
                    "(GC-13: MISSING_ARTIFACTS_MISMATCH)",
            field="missing_artifacts"
        ))
    
    return errors


def validate_incomplete_has_missing_artifacts(
    computed_status: ReportStatus,
    computed_missing: list[str]
) -> list[GC13ValidationError]:
    """
    Validate that INCOMPLETE status has non-empty missing_artifacts.
    
    GC-13: If computed status == INCOMPLETE, computed missing_artifacts MUST be non-empty.
    """
    errors = []
    
    if computed_status == ReportStatus.INCOMPLETE:
        if len(computed_missing) == 0:
            errors.append(GC13ValidationError(
                category="INCOMPLETE_MISSING_ARTIFACTS_EMPTY",
                message="Status is INCOMPLETE but missing_artifacts is empty "
                        "(GC-13: INCOMPLETE_MISSING_ARTIFACTS_EMPTY)",
                field="missing_artifacts"
            ))
    
    return errors


def validate_final_requirements(
    artifacts: ReportArtifacts,
    computed_status: ReportStatus,
    computed_missing: list[str]
) -> list[GC13ValidationError]:
    """
    Validate FINAL requirements.
    
    If computed status is FINAL but there are missing artifacts,
    this indicates a bug in compute_missing_artifacts.
    """
    errors = []
    
    if computed_status == ReportStatus.FINAL and len(computed_missing) > 0:
        errors.append(GC13ValidationError(
            category="FINAL_MISSING_REQUIRED_ARTIFACT",
            message=f"Status is FINAL but missing artifacts: {computed_missing} "
                    "(GC-13: FINAL_MISSING_REQUIRED_ARTIFACT)",
            field="status"
        ))
    
    return errors


def validate_derivation_for_final(
    artifacts: ReportArtifacts,
    computed_status: ReportStatus
) -> list[GC13ValidationError]:
    """
    Validate derivation requirement for FINAL.
    
    GC-13 DERIVATION SEMANTICS:
    - FINAL requires at least one valid derivation step for derivational tasks
    - "no derivation possible yet" is INCOMPLETE, not FINAL
    """
    errors = []
    
    if computed_status != ReportStatus.FINAL:
        return errors
    
    # For derivational tasks, check that derivation exists
    if artifacts.task_kind != "non_derivational":
        if artifacts.derivation_steps is None or len(artifacts.derivation_steps) == 0:
            errors.append(GC13ValidationError(
                category="FINAL_REQUIRES_DERIVATION",
                message="FINAL status requires at least one derivation step for derivational tasks "
                        "(GC-13: FINAL_REQUIRES_DERIVATION)",
                field="derivation_steps"
            ))
    
    return errors


def validate_rag_citations(
    artifacts: ReportArtifacts
) -> list[GC13ValidationError]:
    """
    Validate RAG citations requirement.
    
    If used_rag=true:
    - citations must be present
    - citations must satisfy GC-12 provenance (validated by GC-12)
    """
    errors = []
    
    if not artifacts.used_rag:
        return errors
    
    if artifacts.citations is None:
        errors.append(GC13ValidationError(
            category="RAG_USED_CITATIONS_MISSING",
            message="used_rag is true but citations are missing "
                    "(GC-13: RAG_USED_CITATIONS_MISSING)",
            field="citations"
        ))
    elif not isinstance(artifacts.citations, list):
        errors.append(GC13ValidationError(
            category="RAG_USED_CITATIONS_MISSING",
            message="used_rag is true but citations is not a list "
                    "(GC-13: RAG_USED_CITATIONS_MISSING)",
            field="citations"
        ))
    elif len(artifacts.citations) == 0:
        errors.append(GC13ValidationError(
            category="RAG_USED_CITATIONS_MISSING",
            message="used_rag is true but citations list is empty "
                    "(GC-13: RAG_USED_CITATIONS_MISSING)",
            field="citations"
        ))
    
    return errors


def validate_run_manifest_linkage(
    artifacts: ReportArtifacts,
    computed_status: ReportStatus
) -> list[GC13ValidationError]:
    """
    Validate RunManifest linkage.
    
    v0 stance: WARNING only (not hard fail) if run_manifest_ref is missing for FINAL.
    """
    errors = []
    
    if computed_status != ReportStatus.FINAL:
        return errors
    
    if artifacts.run_manifest_ref is None:
        errors.append(GC13ValidationError(
            category="RUNMANIFEST_REF_MISSING_WARNING",
            message="FINAL report should have run_manifest_ref "
                    "(GC-13: RUNMANIFEST_REF_MISSING_WARNING)",
            field="run_manifest_ref",
            is_warning=True
        ))
    
    return errors


def validate_completion_gate(
    artifacts: ReportArtifacts,
    wire_status: Optional[str] = None,
    wire_missing_artifacts: Optional[list[str]] = None,
    wire_checks: Optional[dict] = None
) -> tuple[ReportStatus, list[str], list[GC13ValidationError]]:
    """
    GC-13 Completion Gate validation.
    
    This is the SINGLE FINAL GATE after GC-1..GC-12 validations.
    
    Validation order:
    1. Validate wire checks (if provided)
    2. Compute missing_artifacts
    3. Compute status
    4. Validate wire status/missing_artifacts mismatch
    5. Validate INCOMPLETE has non-empty missing_artifacts
    6. Validate FINAL requirements
    7. Validate derivation for FINAL
    8. Validate RAG citations
    9. Validate RunManifest linkage (warning only)
    
    Args:
        artifacts: ReportArtifacts container
        wire_status: Optional status from wire (for mismatch check)
        wire_missing_artifacts: Optional missing_artifacts from wire (for mismatch check)
        wire_checks: Optional checks dict from wire (for validation)
        
    Returns:
        (computed_status, computed_missing_artifacts, list of validation errors)
    """
    errors = []
    
    # 1. Validate wire checks if provided
    if wire_checks is not None:
        errors.extend(validate_checks_from_wire(wire_checks))
    
    # 2. Validate ReportChecks if present
    if artifacts.checks is not None:
        errors.extend(validate_report_checks(artifacts.checks))
    
    # 3. Compute missing_artifacts
    computed_missing = compute_missing_artifacts(artifacts)
    
    # 4. Compute status
    computed_status = compute_report_status(artifacts)
    
    # 5. Validate wire status mismatch
    errors.extend(validate_status_mismatch(wire_status, computed_status))
    
    # 6. Validate wire missing_artifacts mismatch
    errors.extend(validate_missing_artifacts_mismatch(wire_missing_artifacts, computed_missing))
    
    # 7. Validate INCOMPLETE has non-empty missing_artifacts
    errors.extend(validate_incomplete_has_missing_artifacts(computed_status, computed_missing))
    
    # 8. Validate FINAL requirements
    errors.extend(validate_final_requirements(artifacts, computed_status, computed_missing))
    
    # 9. Validate derivation for FINAL
    errors.extend(validate_derivation_for_final(artifacts, computed_status))
    
    # 10. Validate RAG citations
    errors.extend(validate_rag_citations(artifacts))
    
    # 11. Validate RunManifest linkage (warning only)
    errors.extend(validate_run_manifest_linkage(artifacts, computed_status))
    
    return computed_status, computed_missing, errors
