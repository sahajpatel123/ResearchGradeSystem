"""
GC-7 Validators (Computed-Only, Fail-Closed)

Validates step status and coverage metrics with deterministic error categories.
Coverage metrics are computed-only and MUST match recomputation.
"""

from typing import Any, Optional
from src.core.step import DerivationStep, StepStatus
from src.core.coverage_metrics import CoverageMetrics, compute_coverage_metrics, UncheckedStepItem, FailedStepItem
from src.core.gc7_wire_parsers import parse_step_status, parse_status_reason
from src.core.id_parsers import parse_step_id
import math


class GC7ValidationError(Exception):
    """Base exception for GC-7 validation errors."""
    pass


def validate_step_object(step_dict: dict[str, Any]) -> DerivationStep:
    """
    Validate and parse a step object from wire (GC-7).
    
    Validates:
    - step_id (via parse_step_id)
    - step_status (via parse_step_status)
    - status_reason (via parse_status_reason)
    - claim_ids (list of strings)
    - depends_on (optional list of strings)
    
    Args:
        step_dict: Step object from wire
    
    Returns:
        Validated DerivationStep
    
    Raises:
        GC7ValidationError: If validation fails
    """
    try:
        # Parse step_id
        step_id = parse_step_id(step_dict.get("step_id"))
        
        # Parse step_status
        step_status = parse_step_status(step_dict.get("step_status", "unchecked"))
        
        # Parse status_reason (required if indeterminate)
        status_reason_wire = step_dict.get("status_reason")
        if step_status == StepStatus.INDETERMINATE:
            status_reason = parse_status_reason(status_reason_wire, required=True)
        else:
            # Strict policy: reject status_reason for non-indeterminate
            if status_reason_wire is not None:
                raise GC7ValidationError(
                    f"Step {step_id}: status_reason present when step_status is {step_status.value} "
                    f"(GC-7: STATUS_REASON_PRESENT_WHEN_NOT_INDETERMINATE)"
                )
            status_reason = None
        
        # Parse claim_ids
        claim_ids = step_dict.get("claim_ids", [])
        if not isinstance(claim_ids, list):
            raise GC7ValidationError(
                f"Step {step_id}: claim_ids must be list, got {type(claim_ids).__name__}"
            )
        
        # Parse depends_on
        depends_on = step_dict.get("depends_on", [])
        if not isinstance(depends_on, list):
            raise GC7ValidationError(
                f"Step {step_id}: depends_on must be list, got {type(depends_on).__name__}"
            )
        
        # Construct DerivationStep (will run __post_init__ validation)
        return DerivationStep(
            step_id=step_id,
            claim_ids=claim_ids,
            step_status=step_status,
            depends_on=depends_on,
            status_reason=status_reason,
        )
    
    except (ValueError, TypeError) as e:
        raise GC7ValidationError(str(e)) from e


def validate_coverage_metrics_match(
    report_steps: list[DerivationStep],
    wire_coverage: Optional[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """
    Validate wire-provided coverage metrics match recomputation (GC-7).
    
    Computed-only enforcement: If wire provides coverage metrics, recompute and FAIL on mismatch.
    
    Args:
        report_steps: List of DerivationStep objects
        wire_coverage: Coverage metrics from wire (or None if not provided)
    
    Returns:
        Tuple of (is_valid, errors)
        - is_valid: True if no wire coverage or matches recomputation
        - errors: List of error messages (empty if valid)
    """
    errors = []
    
    # If no wire coverage provided, compute and return (valid)
    if wire_coverage is None:
        return True, []
    
    # Recompute coverage from steps
    computed = compute_coverage_metrics(report_steps)
    
    # Validate wire coverage structure and types
    try:
        # Check required fields exist
        required_fields = [
            "checked_steps", "unchecked_steps", "failed_steps",
            "checked_count", "unchecked_count", "failed_count", "total_steps",
            "verification_progress_ratio", "verified_work_pct"
        ]
        for field in required_fields:
            if field not in wire_coverage:
                errors.append(f"Coverage metrics missing required field: {field} (GC-7: COVERAGE_WRONG_TYPE)")
        
        if errors:
            return False, errors
        
        # Type checks
        if not isinstance(wire_coverage["checked_steps"], list):
            errors.append("Coverage metrics: checked_steps must be list (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["unchecked_steps"], list):
            errors.append("Coverage metrics: unchecked_steps must be list (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["failed_steps"], list):
            errors.append("Coverage metrics: failed_steps must be list (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["checked_count"], int):
            errors.append("Coverage metrics: checked_count must be int (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["unchecked_count"], int):
            errors.append("Coverage metrics: unchecked_count must be int (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["failed_count"], int):
            errors.append("Coverage metrics: failed_count must be int (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["total_steps"], int):
            errors.append("Coverage metrics: total_steps must be int (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["verification_progress_ratio"], (int, float)):
            errors.append("Coverage metrics: verification_progress_ratio must be number (GC-7: COVERAGE_WRONG_TYPE)")
        if not isinstance(wire_coverage["verified_work_pct"], (int, float)):
            errors.append("Coverage metrics: verified_work_pct must be number (GC-7: COVERAGE_WRONG_TYPE)")
        
        if errors:
            return False, errors
        
        # NaN/Infinity checks
        if math.isnan(wire_coverage["verification_progress_ratio"]) or math.isinf(wire_coverage["verification_progress_ratio"]):
            errors.append("Coverage metrics: verification_progress_ratio is NaN/Infinity (GC-7: COVERAGE_INVALID_NUMBER)")
        if math.isnan(wire_coverage["verified_work_pct"]) or math.isinf(wire_coverage["verified_work_pct"]):
            errors.append("Coverage metrics: verified_work_pct is NaN/Infinity (GC-7: COVERAGE_INVALID_NUMBER)")
        
        if errors:
            return False, errors
        
        # Compare counts
        if wire_coverage["checked_count"] != computed.checked_count:
            errors.append(
                f"Coverage metrics: checked_count mismatch (wire={wire_coverage['checked_count']}, "
                f"computed={computed.checked_count}) (GC-7: COVERAGE_COUNT_MISMATCH)"
            )
        if wire_coverage["unchecked_count"] != computed.unchecked_count:
            errors.append(
                f"Coverage metrics: unchecked_count mismatch (wire={wire_coverage['unchecked_count']}, "
                f"computed={computed.unchecked_count}) (GC-7: COVERAGE_COUNT_MISMATCH)"
            )
        if wire_coverage["failed_count"] != computed.failed_count:
            errors.append(
                f"Coverage metrics: failed_count mismatch (wire={wire_coverage['failed_count']}, "
                f"computed={computed.failed_count}) (GC-7: COVERAGE_COUNT_MISMATCH)"
            )
        if wire_coverage["total_steps"] != computed.total_steps:
            errors.append(
                f"Coverage metrics: total_steps mismatch (wire={wire_coverage['total_steps']}, "
                f"computed={computed.total_steps}) (GC-7: COVERAGE_COUNT_MISMATCH)"
            )
        
        # Compare ratios (with epsilon for float comparison)
        epsilon = 1e-9
        if abs(wire_coverage["verification_progress_ratio"] - computed.verification_progress_ratio) > epsilon:
            errors.append(
                f"Coverage metrics: verification_progress_ratio mismatch (wire={wire_coverage['verification_progress_ratio']}, "
                f"computed={computed.verification_progress_ratio}) (GC-7: COVERAGE_RATIO_MISMATCH)"
            )
        if abs(wire_coverage["verified_work_pct"] - computed.verified_work_pct) > epsilon:
            errors.append(
                f"Coverage metrics: verified_work_pct mismatch (wire={wire_coverage['verified_work_pct']}, "
                f"computed={computed.verified_work_pct}) (GC-7: COVERAGE_RATIO_MISMATCH)"
            )
        
        # Compare buckets (checked_steps)
        wire_checked = sorted(wire_coverage["checked_steps"])
        if wire_checked != computed.checked_steps:
            errors.append(
                f"Coverage metrics: checked_steps mismatch (GC-7: COVERAGE_METRICS_MISMATCH)"
            )
        
        # Compare unchecked_steps (extract step_ids)
        wire_unchecked_ids = []
        for item in wire_coverage["unchecked_steps"]:
            if isinstance(item, dict):
                wire_unchecked_ids.append(item.get("step_id", ""))
            elif isinstance(item, str):
                wire_unchecked_ids.append(item)
        wire_unchecked_ids.sort()
        computed_unchecked_ids = sorted([item.step_id for item in computed.unchecked_steps])
        if wire_unchecked_ids != computed_unchecked_ids:
            errors.append(
                f"Coverage metrics: unchecked_steps mismatch (GC-7: COVERAGE_METRICS_MISMATCH)"
            )
        
        # Compare failed_steps (extract step_ids)
        wire_failed_ids = []
        for item in wire_coverage["failed_steps"]:
            if isinstance(item, dict):
                wire_failed_ids.append(item.get("step_id", ""))
            elif isinstance(item, str):
                wire_failed_ids.append(item)
        wire_failed_ids.sort()
        computed_failed_ids = sorted([item.step_id for item in computed.failed_steps])
        if wire_failed_ids != computed_failed_ids:
            errors.append(
                f"Coverage metrics: failed_steps mismatch (GC-7: COVERAGE_METRICS_MISMATCH)"
            )
        
        # Zero-step edge case: coverage_note check
        if computed.total_steps == 0:
            if "coverage_note" not in wire_coverage or not wire_coverage["coverage_note"]:
                errors.append(
                    "Coverage metrics: coverage_note missing when total_steps == 0 (GC-7: COVERAGE_NOTE_MISSING_ZERO_STEPS)"
                )
        
        # Validate partition consistency (all step_ids accounted for, no duplicates, no overlaps)
        all_step_ids = {step.step_id for step in report_steps}
        
        # Check for ghost step_ids (in buckets but not in report.steps)
        for step_id in wire_checked:
            if step_id not in all_step_ids:
                errors.append(
                    f"Coverage metrics: checked_steps contains ghost step_id '{step_id}' not in report.steps (GC-7: COVERAGE_BUCKET_GHOST_STEP_ID)"
                )
        for step_id in wire_unchecked_ids:
            if step_id not in all_step_ids:
                errors.append(
                    f"Coverage metrics: unchecked_steps contains ghost step_id '{step_id}' not in report.steps (GC-7: COVERAGE_BUCKET_GHOST_STEP_ID)"
                )
        for step_id in wire_failed_ids:
            if step_id not in all_step_ids:
                errors.append(
                    f"Coverage metrics: failed_steps contains ghost step_id '{step_id}' not in report.steps (GC-7: COVERAGE_BUCKET_GHOST_STEP_ID)"
                )
        
        # Check for duplicates within buckets
        if len(wire_checked) != len(set(wire_checked)):
            duplicates = [sid for sid in wire_checked if wire_checked.count(sid) > 1]
            errors.append(
                f"Coverage metrics: checked_steps contains duplicates: {set(duplicates)} (GC-7: COVERAGE_BUCKET_DUPLICATE_STEP_ID)"
            )
        if len(wire_unchecked_ids) != len(set(wire_unchecked_ids)):
            duplicates = [sid for sid in wire_unchecked_ids if wire_unchecked_ids.count(sid) > 1]
            errors.append(
                f"Coverage metrics: unchecked_steps contains duplicates: {set(duplicates)} (GC-7: COVERAGE_BUCKET_DUPLICATE_STEP_ID)"
            )
        if len(wire_failed_ids) != len(set(wire_failed_ids)):
            duplicates = [sid for sid in wire_failed_ids if wire_failed_ids.count(sid) > 1]
            errors.append(
                f"Coverage metrics: failed_steps contains duplicates: {set(duplicates)} (GC-7: COVERAGE_BUCKET_DUPLICATE_STEP_ID)"
            )
        
        # Check partition consistency (all steps accounted for, no overlaps)
        wire_all_bucket_ids = set(wire_checked) | set(wire_unchecked_ids) | set(wire_failed_ids)
        if wire_all_bucket_ids != all_step_ids:
            missing = all_step_ids - wire_all_bucket_ids
            extra = wire_all_bucket_ids - all_step_ids
            if missing:
                errors.append(
                    f"Coverage metrics: partition mismatch - steps missing from buckets: {missing} (GC-7: COVERAGE_PARTITION_MISMATCH)"
                )
            if extra:
                errors.append(
                    f"Coverage metrics: partition mismatch - extra steps in buckets: {extra} (GC-7: COVERAGE_PARTITION_MISMATCH)"
                )
        
        # Check for overlaps (step in multiple buckets)
        checked_set = set(wire_checked)
        unchecked_set = set(wire_unchecked_ids)
        failed_set = set(wire_failed_ids)
        
        overlap_checked_unchecked = checked_set & unchecked_set
        overlap_checked_failed = checked_set & failed_set
        overlap_unchecked_failed = unchecked_set & failed_set
        
        if overlap_checked_unchecked:
            errors.append(
                f"Coverage metrics: partition mismatch - steps in both checked and unchecked: {overlap_checked_unchecked} (GC-7: COVERAGE_PARTITION_MISMATCH)"
            )
        if overlap_checked_failed:
            errors.append(
                f"Coverage metrics: partition mismatch - steps in both checked and failed: {overlap_checked_failed} (GC-7: COVERAGE_PARTITION_MISMATCH)"
            )
        if overlap_unchecked_failed:
            errors.append(
                f"Coverage metrics: partition mismatch - steps in both unchecked and failed: {overlap_unchecked_failed} (GC-7: COVERAGE_PARTITION_MISMATCH)"
            )
    
    except Exception as e:
        errors.append(f"Coverage metrics validation error: {str(e)}")
    
    return len(errors) == 0, errors


def validate_and_compute_coverage_metrics(
    report_steps: list[DerivationStep],
    wire_coverage: Optional[dict[str, Any]] = None
) -> tuple[CoverageMetrics, list[str]]:
    """
    Validate and compute coverage metrics (GC-7).
    
    If wire_coverage provided, validates it matches recomputation (fail-closed).
    Always returns computed metrics (single source of truth).
    
    Args:
        report_steps: List of DerivationStep objects
        wire_coverage: Optional coverage metrics from wire
    
    Returns:
        Tuple of (computed_metrics, errors)
        - computed_metrics: Computed CoverageMetrics
        - errors: List of validation errors (empty if valid)
    """
    # Compute coverage from steps (single source of truth)
    computed_metrics = compute_coverage_metrics(report_steps)
    
    # If wire coverage provided, validate it matches
    errors = []
    if wire_coverage is not None:
        is_valid, validation_errors = validate_coverage_metrics_match(report_steps, wire_coverage)
        if not is_valid:
            errors.extend(validation_errors)
    
    return computed_metrics, errors
