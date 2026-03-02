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
    
    GC-9.1: Uses point_kind for robust random_pass_count computation (Option A).
    
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
        log: Log payload with per-point statuses and point_kind
    
    Returns:
        True if strong agreement satisfied, False otherwise
    """
    # Get strong params
    N = spec.strong_params.N
    M = spec.strong_params.M
    
    # GC-9.1: Use point_kind for robust computation (Option A)
    deterministic_passed_all = True
    random_pass_count = 0
    
    for i, (status, kind) in enumerate(zip(log.per_point_status, log.point_kind)):
        if kind == "deterministic":
            if status != "pass":
                deterministic_passed_all = False
        elif kind == "random":
            if status == "pass":
                random_pass_count += 1
        # edge points don't affect strong agreement computation
    
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


def validate_instability_never_passes(log: LogPayload) -> None:
    """
    GC-9.1: Instability never maps to pass (FREEZE BLOCKER #2).
    
    Enforces that unstable outputs cannot be marked as pass:
    - NaN output => per_point_status MUST NOT be "pass"
    - Infinity output => per_point_status MUST NOT be "pass"
    - Missing/null output => per_point_status MUST NOT be "pass"
    - Timeout/tool_error in runtime_notes => per_point_status MUST NOT be "pass"
    
    Args:
        log: Log payload to validate
    
    Raises:
        ValueError: If instability is treated as pass
    """
    import math
    
    for i, (output, status) in enumerate(zip(log.outputs, log.per_point_status)):
        # Check for NaN output
        if isinstance(output, (int, float)) and math.isnan(output):
            if status == "pass":
                raise ValueError(
                    f"Log output[{i}] is NaN but per_point_status is 'pass' (GC-9.1: INSTABILITY_TREATED_AS_PASS)"
                )
        
        # Check for Infinity output
        if isinstance(output, (int, float)) and math.isinf(output):
            if status == "pass":
                raise ValueError(
                    f"Log output[{i}] is Infinity but per_point_status is 'pass' (GC-9.1: INSTABILITY_TREATED_AS_PASS)"
                )
        
        # Check for missing/null output
        if output is None:
            if status == "pass":
                raise ValueError(
                    f"Log output[{i}] is missing/null but per_point_status is 'pass' (GC-9.1: INSTABILITY_TREATED_AS_PASS)"
                )
    
    # Check runtime_notes for timeout/tool_error
    if log.runtime_notes:
        runtime_lower = log.runtime_notes.lower()
        if any(keyword in runtime_lower for keyword in ["timeout", "tool_error", "error", "failed"]):
            # If runtime notes indicate problems, check if any points are marked pass
            if any(status == "pass" for status in log.per_point_status):
                raise ValueError(
                    f"Log runtime_notes indicate instability but some points marked 'pass' (GC-9.1: INSTABILITY_TREATED_AS_PASS)"
                )


def validate_log_payload(spec: NumericCheckSpec, log: LogPayload) -> None:
    """
    Validate log payload against spec.
    
    GC-9.1: Also validates point_kind and enforces instability never maps to pass.
    
    Checks:
    - Aligned lengths (points, outputs, per_point_status, point_kind)
    - Total points match spec (deterministic + edge + random)
    - Seed present if random_points_count > 0
    - point_kind values are valid and match spec structure
    - Instability never maps to pass (GC-9.1 freeze blocker #2)
    
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
    
    # GC-9.1: Validate point_kind matches spec structure
    expected_deterministic = len(spec.sampling_strategy.deterministic_points)
    expected_edge = len(spec.sampling_strategy.edge_case_points)
    expected_random = spec.sampling_strategy.random_points_count
    
    actual_deterministic = sum(1 for kind in log.point_kind if kind == "deterministic")
    actual_edge = sum(1 for kind in log.point_kind if kind == "edge")
    actual_random = sum(1 for kind in log.point_kind if kind == "random")
    
    if actual_deterministic != expected_deterministic:
        raise ValueError(
            f"point_kind deterministic count mismatch: expected {expected_deterministic}, got {actual_deterministic} (GC-9.1: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    if actual_edge != expected_edge:
        raise ValueError(
            f"point_kind edge count mismatch: expected {expected_edge}, got {actual_edge} (GC-9.1: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    if actual_random != expected_random:
        raise ValueError(
            f"point_kind random count mismatch: expected {expected_random}, got {actual_random} (GC-9.1: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    # GC-9.1: Enforce instability never maps to pass
    validate_instability_never_passes(log)


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
