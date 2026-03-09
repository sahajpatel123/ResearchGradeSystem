"""
GC-15 Validators: Regression Gate Logic and Validation.

Implements gate evaluation logic for GC-15 regression gating.
Single source of truth for gate decisions.
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.regression_gating import (
    CurrentMetrics,
    MetricDelta,
    MetricDirection,
    MetricUnit,
    PROTECTED_METRICS,
    RegressionBaseline,
    RegressionGateInput,
    RegressionGateResult,
    RegressionGatingPolicy,
    RegressionPhase,
    TRACKED_METRIC_REGISTRY,
    TrackedMetric,
    compute_regression_phase,
    get_tracked_metric,
    is_metric_protected,
    is_metric_tracked,
)


@dataclass
class GC15ValidationError:
    """GC-15 validation error with category and message."""
    category: str
    message: str
    field: Optional[str] = None
    is_warning: bool = False


# =============================================================================
# ERROR CATEGORIES
# =============================================================================

class GC15ErrorCategory:
    """GC-15 error categories (frozen boring exact names)."""
    REGRESSION_BASELINE_MISSING = "REGRESSION_BASELINE_MISSING"
    REGRESSION_BASELINE_INVALID = "REGRESSION_BASELINE_INVALID"
    REGRESSION_PHASE_MISCOMPUTED = "REGRESSION_PHASE_MISCOMPUTED"
    REGRESSION_METRIC_DROP_EXCEEDED = "REGRESSION_METRIC_DROP_EXCEEDED"
    UNSUPPORTED_CLAIM_RATE_INCREASED = "UNSUPPORTED_CLAIM_RATE_INCREASED"
    ADR_REQUIRED_MISSING = "ADR_REQUIRED_MISSING"
    ADR_OVERRIDE_NOT_ALLOWED_FOR_UNSUPPORTED_CLAIM_RATE = "ADR_OVERRIDE_NOT_ALLOWED_FOR_UNSUPPORTED_CLAIM_RATE"
    TRACKED_METRIC_REGISTRY_INVALID = "TRACKED_METRIC_REGISTRY_INVALID"
    REGRESSION_GATE_OUTPUT_INVALID = "REGRESSION_GATE_OUTPUT_INVALID"
    PRE_THRESHOLD_FAIL_COUNT_INCREASED = "PRE_THRESHOLD_FAIL_COUNT_INCREASED"


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_baseline(baseline: Optional[RegressionBaseline]) -> list[GC15ValidationError]:
    """Validate that baseline artifact is present and valid."""
    errors = []
    
    if baseline is None:
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.REGRESSION_BASELINE_MISSING,
            message="Regression baseline artifact is missing "
                    "(GC-15: REGRESSION_BASELINE_MISSING)",
            field="baseline",
        ))
        return errors
    
    if not isinstance(baseline, RegressionBaseline):
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.REGRESSION_BASELINE_INVALID,
            message="Regression baseline must be RegressionBaseline type "
                    "(GC-15: REGRESSION_BASELINE_INVALID)",
            field="baseline",
        ))
        return errors
    
    # Check that baseline has all required tracked metrics
    for metric_name in TRACKED_METRIC_REGISTRY:
        if metric_name not in baseline.metrics:
            errors.append(GC15ValidationError(
                category=GC15ErrorCategory.REGRESSION_BASELINE_INVALID,
                message=f"Baseline missing required tracked metric: {metric_name} "
                        "(GC-15: REGRESSION_BASELINE_INVALID)",
                field=f"baseline.metrics.{metric_name}",
            ))
    
    return errors


def validate_current_metrics(current: Optional[CurrentMetrics]) -> list[GC15ValidationError]:
    """Validate that current metrics are present and valid."""
    errors = []
    
    if current is None:
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.REGRESSION_BASELINE_INVALID,
            message="Current metrics are missing "
                    "(GC-15: REGRESSION_BASELINE_INVALID)",
            field="current",
        ))
        return errors
    
    # Check that current has all required tracked metrics
    for metric_name in TRACKED_METRIC_REGISTRY:
        if metric_name not in current.metrics:
            errors.append(GC15ValidationError(
                category=GC15ErrorCategory.TRACKED_METRIC_REGISTRY_INVALID,
                message=f"Current metrics missing required tracked metric: {metric_name} "
                        "(GC-15: TRACKED_METRIC_REGISTRY_INVALID)",
                field=f"current.metrics.{metric_name}",
            ))
    
    return errors


def validate_metric_registry() -> list[GC15ValidationError]:
    """Validate that metric registry is properly configured."""
    errors = []
    
    # Check that unsupported_claim_rate is present and protected
    if "unsupported_claim_rate" not in TRACKED_METRIC_REGISTRY:
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.TRACKED_METRIC_REGISTRY_INVALID,
            message="unsupported_claim_rate must be in tracked metric registry "
                    "(GC-15: TRACKED_METRIC_REGISTRY_INVALID)",
            field="registry.unsupported_claim_rate",
        ))
    
    if "unsupported_claim_rate" not in PROTECTED_METRICS:
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.TRACKED_METRIC_REGISTRY_INVALID,
            message="unsupported_claim_rate must be protected "
                    "(GC-15: TRACKED_METRIC_REGISTRY_INVALID)",
            field="registry.unsupported_claim_rate",
        ))
    
    # Check all metrics have direction and unit
    for metric_name, metric in TRACKED_METRIC_REGISTRY.items():
        if not isinstance(metric.direction, MetricDirection):
            errors.append(GC15ValidationError(
                category=GC15ErrorCategory.TRACKED_METRIC_REGISTRY_INVALID,
                message=f"Metric {metric_name} missing valid direction "
                        "(GC-15: TRACKED_METRIC_REGISTRY_INVALID)",
                field=f"registry.{metric_name}.direction",
            ))
        if not isinstance(metric.unit, MetricUnit):
            errors.append(GC15ValidationError(
                category=GC15ErrorCategory.TRACKED_METRIC_REGISTRY_INVALID,
                message=f"Metric {metric_name} missing valid unit "
                        "(GC-15: TRACKED_METRIC_REGISTRY_INVALID)",
                field=f"registry.{metric_name}.unit",
            ))
    
    return errors


# =============================================================================
# GATE EVALUATION LOGIC (single source of truth)
# =============================================================================

def _compute_metric_deltas(
    baseline: RegressionBaseline,
    current: CurrentMetrics,
) -> list[MetricDelta]:
    """Compute metric deltas for all tracked metrics."""
    deltas = []
    
    for metric_name, metric_info in TRACKED_METRIC_REGISTRY.items():
        baseline_value = baseline.metrics.get(metric_name, 0.0)
        current_value = current.metrics.get(metric_name, 0.0)
        delta = current_value - baseline_value
        
        deltas.append(MetricDelta(
            metric_name=metric_name,
            baseline_value=baseline_value,
            current_value=current_value,
            delta=delta,
            unit=metric_info.unit,
            direction=metric_info.direction,
        ))
    
    return deltas


def _evaluate_pre_threshold(
    gate_input: RegressionGateInput,
    policy: RegressionGatingPolicy,
    metric_deltas: list[MetricDelta],
) -> list[str]:
    """
    Evaluate PRE_THRESHOLD rules.
    
    PRE_THRESHOLD rules:
    - current.fail_count <= baseline.fail_count
    - current.unsupported_claim_rate <= baseline.unsupported_claim_rate
    """
    failed_rules = []
    
    # Rule: fail_count must not increase
    if policy.pre_threshold.absolute_fail_count_must_not_increase:
        if gate_input.current.fail_count > gate_input.baseline.fail_count:
            failed_rules.append(GC15ErrorCategory.PRE_THRESHOLD_FAIL_COUNT_INCREASED)
    
    # Rule: unsupported_claim_rate must not increase
    if policy.pre_threshold.unsupported_claim_rate_must_not_increase:
        baseline_ucr = gate_input.baseline.metrics.get("unsupported_claim_rate", 0.0)
        current_ucr = gate_input.current.metrics.get("unsupported_claim_rate", 0.0)
        if current_ucr > baseline_ucr:
            failed_rules.append(GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED)
    
    return failed_rules


def _evaluate_post_threshold(
    gate_input: RegressionGateInput,
    policy: RegressionGatingPolicy,
    metric_deltas: list[MetricDelta],
) -> list[str]:
    """
    Evaluate POST_THRESHOLD rules.
    
    POST_THRESHOLD rules:
    - For higher_is_better percentage_points metrics:
        current >= baseline - max_absolute_metric_drop
    - For unsupported_claim_rate (lower_is_better):
        current <= baseline (strict non-increase)
    """
    failed_rules = []
    max_drop = policy.post_threshold.max_absolute_metric_drop
    
    for delta in metric_deltas:
        metric_info = get_tracked_metric(delta.metric_name)
        if metric_info is None:
            continue
        
        if delta.metric_name == "unsupported_claim_rate":
            # Special handling: strict non-increase
            if policy.post_threshold.unsupported_claim_rate_must_not_increase:
                if delta.current_value > delta.baseline_value:
                    if GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED not in failed_rules:
                        failed_rules.append(GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED)
        elif metric_info.direction == MetricDirection.HIGHER_IS_BETTER:
            # Check if drop exceeds max allowed
            if metric_info.unit == MetricUnit.PERCENTAGE_POINTS:
                if delta.current_value < delta.baseline_value - max_drop:
                    if GC15ErrorCategory.REGRESSION_METRIC_DROP_EXCEEDED not in failed_rules:
                        failed_rules.append(GC15ErrorCategory.REGRESSION_METRIC_DROP_EXCEEDED)
    
    return failed_rules


def _apply_adr_rules(
    failed_rules: list[str],
    gate_input: RegressionGateInput,
    policy: RegressionGatingPolicy,
) -> tuple[list[str], bool, bool]:
    """
    Apply ADR rules to failed rules.
    
    ADR rules:
    - If blocking metric-drop failures exist and ADR present with valid adr_id, gate may pass
    - If unsupported_claim_rate increased and allow_adr_override_for_unsupported_claim_rate=false:
        gate FAILS regardless of ADR
    - If ADR required but adr_present=false or adr_id missing:
        FAIL ADR_REQUIRED_MISSING
    
    Returns:
        (remaining_failed_rules, adr_required, adr_used)
    """
    adr_required = False
    adr_used = False
    remaining_rules = failed_rules.copy()
    
    if len(failed_rules) == 0:
        return remaining_rules, adr_required, adr_used
    
    # Check if unsupported_claim_rate increased (non-waivable by default)
    ucr_increased = GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in failed_rules
    
    if ucr_increased and not policy.allow_adr_override_for_unsupported_claim_rate:
        # Cannot waive unsupported_claim_rate increase
        # Add explicit error if ADR was attempted
        if gate_input.adr_present:
            if GC15ErrorCategory.ADR_OVERRIDE_NOT_ALLOWED_FOR_UNSUPPORTED_CLAIM_RATE not in remaining_rules:
                remaining_rules.append(GC15ErrorCategory.ADR_OVERRIDE_NOT_ALLOWED_FOR_UNSUPPORTED_CLAIM_RATE)
        return remaining_rules, adr_required, adr_used
    
    # Check if ADR can waive other failures
    waivable_failures = [
        r for r in failed_rules
        if r not in [GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED]
        or policy.allow_adr_override_for_unsupported_claim_rate
    ]
    
    if len(waivable_failures) > 0 and policy.exceptions_require_adr:
        adr_required = True
        
        if gate_input.adr_present and gate_input.adr_id:
            # ADR present and valid - waive waivable failures
            adr_used = True
            remaining_rules = [
                r for r in remaining_rules
                if r not in waivable_failures
            ]
        elif gate_input.adr_present and not gate_input.adr_id:
            # ADR present but missing adr_id
            if GC15ErrorCategory.ADR_REQUIRED_MISSING not in remaining_rules:
                remaining_rules.append(GC15ErrorCategory.ADR_REQUIRED_MISSING)
    
    return remaining_rules, adr_required, adr_used


def evaluate_regression_gate(
    gate_input: RegressionGateInput,
    policy: Optional[RegressionGatingPolicy] = None,
) -> RegressionGateResult:
    """
    Evaluate regression gate (single source of truth).
    
    GC-15: Gate compares against DECLARED baseline artifact.
    Phase uses CURRENT eval_case_count, not baseline count.
    
    Args:
        gate_input: RegressionGateInput with baseline and current metrics
        policy: Optional policy (uses default if not provided)
        
    Returns:
        RegressionGateResult with explainable pass/fail decision
    """
    if policy is None:
        policy = RegressionGatingPolicy()
    
    # Compute phase from CURRENT eval_case_count
    phase = compute_regression_phase(
        gate_input.current.eval_case_count,
        policy,
    )
    
    # Compute metric deltas
    metric_deltas = _compute_metric_deltas(
        gate_input.baseline,
        gate_input.current,
    )
    
    # Evaluate rules based on phase
    if phase == RegressionPhase.PRE_THRESHOLD:
        failed_rules = _evaluate_pre_threshold(gate_input, policy, metric_deltas)
    else:
        failed_rules = _evaluate_post_threshold(gate_input, policy, metric_deltas)
    
    # Apply ADR rules
    remaining_rules, adr_required, adr_used = _apply_adr_rules(
        failed_rules,
        gate_input,
        policy,
    )
    
    # Determine pass/fail
    passed = len(remaining_rules) == 0
    
    return RegressionGateResult(
        passed=passed,
        phase=phase,
        failed_rules=remaining_rules,
        metric_deltas=metric_deltas,
        adr_required=adr_required,
        adr_used=adr_used,
        baseline_id=gate_input.baseline.baseline_id,
        current_commit_hash=gate_input.current.commit_hash,
    )


def validate_gate_result(result: RegressionGateResult) -> list[GC15ValidationError]:
    """Validate gate result is properly formed."""
    errors = []
    
    # If failed, must have failed_rules
    if not result.passed and len(result.failed_rules) == 0:
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.REGRESSION_GATE_OUTPUT_INVALID,
            message="Gate result failed but failed_rules is empty "
                    "(GC-15: REGRESSION_GATE_OUTPUT_INVALID)",
            field="failed_rules",
        ))
    
    # If passed with blocking failures, invalid
    if result.passed and len(result.failed_rules) > 0:
        errors.append(GC15ValidationError(
            category=GC15ErrorCategory.REGRESSION_GATE_OUTPUT_INVALID,
            message="Gate result passed but has failed_rules "
                    "(GC-15: REGRESSION_GATE_OUTPUT_INVALID)",
            field="passed",
        ))
    
    return errors
