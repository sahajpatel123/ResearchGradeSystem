"""
GC-9 Numeric Agreement Contract - Validators

Validates numeric check spec/result/log with strong agreement computation.
Strong agreement is COMPUTED ONLY, never trusted from wire.
"""

from typing import Optional
from src.core.numeric_check import (
    NumericCheckSpec,
    NumericCheckResult,
    LogPayload,
    NumericCheckStatus,
)


def compute_strong_agreement(
    spec: NumericCheckSpec,
    result: NumericCheckResult,
    log: LogPayload
) -> bool:
    """
    Compute strong agreement (COMPUTED ONLY, never trust wire).
    
    Strong agreement requires:
    1. All deterministic points pass (deterministic_passed_all == True)
    2. At least N random points pass (random_pass_count >= N)
    3. Zero failures (fail_count == 0)
    4. At most M indeterminate results (indeterminate_count <= M)
    
    Teacher correction: deterministic_points must be non-empty (hard rule).
    Random-only checks are FORBIDDEN.
    
    Args:
        spec: Numeric check specification
        result: Numeric check result
        log: Log payload with per-point statuses
    
    Returns:
        True if strong agreement satisfied, False otherwise
    """
    # Get strong params
    N = spec.strong_params.N
    M = spec.strong_params.M
    
    # Count deterministic points
    num_deterministic = len(spec.sampling_strategy.deterministic_points)
    
    # Identify which points are deterministic (first num_deterministic points in log)
    deterministic_statuses = log.per_point_status[:num_deterministic]
    
    # Check if all deterministic points passed
    deterministic_passed_all = all(status == "pass" for status in deterministic_statuses)
    
    # Count random passes (points after deterministic + edge cases)
    num_edge = len(spec.sampling_strategy.edge_case_points)
    random_start_idx = num_deterministic + num_edge
    random_statuses = log.per_point_status[random_start_idx:]
    random_pass_count = sum(1 for status in random_statuses if status == "pass")
    
    # Strong agreement formula
    strong_agreement = (
        deterministic_passed_all and
        random_pass_count >= N and
        result.fail_count == 0 and
        result.indeterminate_count <= M
    )
    
    return strong_agreement


def validate_counts_match_log(result: NumericCheckResult, log: LogPayload) -> None:
    """
    Validate that result counts match per_point_status tallies in log.
    
    Args:
        result: Numeric check result
        log: Log payload
    
    Raises:
        ValueError: If counts don't match
    """
    # Tally per_point_status
    actual_pass_count = sum(1 for status in log.per_point_status if status == "pass")
    actual_fail_count = sum(1 for status in log.per_point_status if status == "fail")
    actual_indeterminate_count = sum(1 for status in log.per_point_status if status == "indeterminate")
    
    # Verify counts match
    if result.pass_count != actual_pass_count:
        raise ValueError(
            f"pass_count mismatch: result claims {result.pass_count}, log has {actual_pass_count} (GC-9: NUMERIC_RESULT_COUNT_MISMATCH)"
        )
    
    if result.fail_count != actual_fail_count:
        raise ValueError(
            f"fail_count mismatch: result claims {result.fail_count}, log has {actual_fail_count} (GC-9: NUMERIC_RESULT_COUNT_MISMATCH)"
        )
    
    if result.indeterminate_count != actual_indeterminate_count:
        raise ValueError(
            f"indeterminate_count mismatch: result claims {result.indeterminate_count}, log has {actual_indeterminate_count} (GC-9: NUMERIC_RESULT_COUNT_MISMATCH)"
        )


def validate_log_payload(spec: NumericCheckSpec, log: LogPayload) -> None:
    """
    Validate log payload against spec.
    
    Checks:
    - Aligned lengths (points, outputs, per_point_status)
    - Total points match spec (deterministic + edge + random)
    - Seed present if random_points_count > 0
    
    Args:
        spec: Numeric check specification
        log: Log payload
    
    Raises:
        ValueError: If validation fails
    """
    # Check aligned lengths (already validated in LogPayload.__post_init__)
    # But verify total count matches spec
    expected_total = (
        len(spec.sampling_strategy.deterministic_points) +
        len(spec.sampling_strategy.edge_case_points) +
        spec.sampling_strategy.random_points_count
    )
    
    actual_total = len(log.points)
    
    if actual_total != expected_total:
        raise ValueError(
            f"Log point count mismatch: expected {expected_total} (deterministic + edge + random), got {actual_total} (GC-9: NUMERIC_LOG_LENGTH_MISMATCH)"
        )
    
    # Verify seed present if random_points_count > 0
    if spec.sampling_strategy.random_points_count > 0 and log.seed is None:
        raise ValueError(
            "Log missing seed when random_points_count > 0 (GC-9: NUMERIC_LOG_MISSING_FIELDS)"
        )


def validate_strong_agreement(
    spec: NumericCheckSpec,
    result: NumericCheckResult,
    log: LogPayload
) -> None:
    """
    Validate strong_agreement is correctly computed (NEVER trust wire).
    
    Recomputes strong_agreement and verifies it matches result.
    If mismatch, raises error.
    
    Args:
        spec: Numeric check specification
        result: Numeric check result
        log: Log payload
    
    Raises:
        ValueError: If strong_agreement mismatch
    """
    # Compute expected strong_agreement
    expected_strong_agreement = compute_strong_agreement(spec, result, log)
    
    # Verify matches result
    if result.strong_agreement != expected_strong_agreement:
        raise ValueError(
            f"strong_agreement mismatch: result claims {result.strong_agreement}, computed {expected_strong_agreement} (GC-9: NUMERIC_STRONG_AGREEMENT_MISMATCH)"
        )


def validate_numeric_check(
    spec: NumericCheckSpec,
    result: NumericCheckResult,
    log: LogPayload
) -> None:
    """
    Full GC-9 validation pipeline.
    
    Validates:
    1. Spec is valid (already validated in __post_init__)
    2. Log payload is valid and matches spec
    3. Result counts match log per_point_status
    4. strong_agreement is correctly computed
    
    Args:
        spec: Numeric check specification
        result: Numeric check result
        log: Log payload
    
    Raises:
        ValueError: If any validation fails
    """
    # Validate log payload
    validate_log_payload(spec, log)
    
    # Validate counts match
    validate_counts_match_log(result, log)
    
    # Validate strong_agreement (computed-only)
    validate_strong_agreement(spec, result, log)


def get_step_status_from_numeric_result(result: NumericCheckResult) -> str:
    """
    Map NumericCheckResult status to step_status.
    
    Mapping:
    - pass -> "checked"
    - fail -> "failed"
    - indeterminate -> "indeterminate"
    
    Args:
        result: Numeric check result
    
    Returns:
        Step status string
    """
    if result.status == NumericCheckStatus.PASS:
        return "checked"
    elif result.status == NumericCheckStatus.FAIL:
        return "failed"
    else:  # INDETERMINATE
        return "indeterminate"
