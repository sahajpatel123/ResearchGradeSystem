"""
GC-15 Regression Gating: Policy, Registry, Baseline, and Gate Schemas.

Prevents silent quality decay while keeping gate decisions explainable.

Teacher corrections enforced:
1) Gate compares against a DECLARED RegressionBaseline artifact, not ad hoc "previous metrics"
2) Tracked metrics come from a CLOSED MetricRegistry with direction and unit
3) Unsupported-claim-rate increase is NON-WAIVABLE by default
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# =============================================================================
# METRIC REGISTRY (closed set)
# =============================================================================

class MetricDirection(Enum):
    """Direction for metric comparison."""
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class MetricUnit(Enum):
    """Unit for metric values."""
    PERCENTAGE_POINTS = "percentage_points"
    COUNT = "count"
    RATIO = "ratio"


@dataclass
class TrackedMetric:
    """
    A tracked metric in the registry.
    
    Each metric has:
    - metric_name: Unique identifier
    - direction: higher_is_better or lower_is_better
    - unit: percentage_points, count, or ratio
    """
    metric_name: str
    direction: MetricDirection
    unit: MetricUnit

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or self.metric_name.strip() == "":
            raise ValueError("metric_name must be non-empty string")
        if not isinstance(self.direction, MetricDirection):
            raise TypeError("direction must be MetricDirection")
        if not isinstance(self.unit, MetricUnit):
            raise TypeError("unit must be MetricUnit")


# GC-15 CLOSED METRIC REGISTRY (v0)
# This is the authoritative set of tracked metrics
TRACKED_METRIC_REGISTRY: dict[str, TrackedMetric] = {
    "symbolic_correctness": TrackedMetric(
        metric_name="symbolic_correctness",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    "derivation_correctness": TrackedMetric(
        metric_name="derivation_correctness",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    "unit_consistency_pass_rate": TrackedMetric(
        metric_name="unit_consistency_pass_rate",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    "limit_special_case_pass_rate": TrackedMetric(
        metric_name="limit_special_case_pass_rate",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    "numeric_agreement_pass_rate": TrackedMetric(
        metric_name="numeric_agreement_pass_rate",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    "reproducibility_rerun_success": TrackedMetric(
        metric_name="reproducibility_rerun_success",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    "proof_check_success_rate": TrackedMetric(
        metric_name="proof_check_success_rate",
        direction=MetricDirection.HIGHER_IS_BETTER,
        unit=MetricUnit.PERCENTAGE_POINTS,
    ),
    # PROTECTED: unsupported_claim_rate is non-waivable by default
    "unsupported_claim_rate": TrackedMetric(
        metric_name="unsupported_claim_rate",
        direction=MetricDirection.LOWER_IS_BETTER,
        unit=MetricUnit.RATIO,
    ),
}

# Protected metrics that cannot be waived by ADR by default
PROTECTED_METRICS = frozenset(["unsupported_claim_rate"])


def get_tracked_metric(metric_name: str) -> Optional[TrackedMetric]:
    """Get a tracked metric from the registry."""
    return TRACKED_METRIC_REGISTRY.get(metric_name)


def is_metric_tracked(metric_name: str) -> bool:
    """Check if a metric is in the tracked registry."""
    return metric_name in TRACKED_METRIC_REGISTRY


def is_metric_protected(metric_name: str) -> bool:
    """Check if a metric is protected (non-waivable by default)."""
    return metric_name in PROTECTED_METRICS


# =============================================================================
# POLICY CONFIG
# =============================================================================

@dataclass
class PreThresholdPolicy:
    """
    Pre-threshold policy (eval_case_count < min_eval_cases).
    
    Uses absolute counts, not percentage drops.
    """
    absolute_fail_count_must_not_increase: bool = True
    unsupported_claim_rate_must_not_increase: bool = True


@dataclass
class PostThresholdPolicy:
    """
    Post-threshold policy (eval_case_count >= min_eval_cases).
    
    Uses percentage point drops with configurable max.
    """
    max_absolute_metric_drop: float = 0.5  # percentage points
    unsupported_claim_rate_must_not_increase: bool = True

    def __post_init__(self) -> None:
        if self.max_absolute_metric_drop < 0:
            raise ValueError("max_absolute_metric_drop must be >= 0")


@dataclass
class RegressionGatingPolicy:
    """
    GC-15 regression gating policy.
    
    Controls gate behavior for pre-threshold and post-threshold phases.
    """
    min_eval_cases: int = 200
    pre_threshold: PreThresholdPolicy = field(default_factory=PreThresholdPolicy)
    post_threshold: PostThresholdPolicy = field(default_factory=PostThresholdPolicy)
    exceptions_require_adr: bool = True
    allow_adr_override_for_unsupported_claim_rate: bool = False  # NON-WAIVABLE by default

    def __post_init__(self) -> None:
        if self.min_eval_cases <= 0:
            raise ValueError("min_eval_cases must be > 0")
        if not isinstance(self.pre_threshold, PreThresholdPolicy):
            raise TypeError("pre_threshold must be PreThresholdPolicy")
        if not isinstance(self.post_threshold, PostThresholdPolicy):
            raise TypeError("post_threshold must be PostThresholdPolicy")


# =============================================================================
# BASELINE ARTIFACT
# =============================================================================

@dataclass
class RegressionBaseline:
    """
    GC-15 regression baseline artifact.
    
    This is the DECLARED baseline that the gate compares against.
    NOT ad hoc "previous metrics" from UI or cache.
    """
    baseline_id: str
    baseline_commit_hash: str
    eval_case_count: int
    fail_count: int
    metrics: dict[str, float]
    created_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.baseline_id, str) or self.baseline_id.strip() == "":
            raise ValueError("baseline_id must be non-empty string")
        if not isinstance(self.baseline_commit_hash, str) or self.baseline_commit_hash.strip() == "":
            raise ValueError("baseline_commit_hash must be non-empty string")
        if not isinstance(self.eval_case_count, int) or self.eval_case_count < 0:
            raise ValueError("eval_case_count must be non-negative integer")
        if not isinstance(self.fail_count, int) or self.fail_count < 0:
            raise ValueError("fail_count must be non-negative integer")
        if not isinstance(self.metrics, dict):
            raise TypeError("metrics must be dict")
        if not isinstance(self.created_at, str) or self.created_at.strip() == "":
            raise ValueError("created_at must be non-empty string")


@dataclass
class CurrentMetrics:
    """
    Current validated metrics from report/artifact objects.
    
    NOT from UI/cached/manual summaries.
    """
    eval_case_count: int
    fail_count: int
    metrics: dict[str, float]
    commit_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.eval_case_count, int) or self.eval_case_count < 0:
            raise ValueError("eval_case_count must be non-negative integer")
        if not isinstance(self.fail_count, int) or self.fail_count < 0:
            raise ValueError("fail_count must be non-negative integer")
        if not isinstance(self.metrics, dict):
            raise TypeError("metrics must be dict")


@dataclass
class RegressionGateInput:
    """
    GC-15 regression gate input.
    
    Contains baseline artifact, current metrics, and ADR info.
    """
    baseline: RegressionBaseline
    current: CurrentMetrics
    adr_present: bool = False
    adr_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, RegressionBaseline):
            raise TypeError("baseline must be RegressionBaseline")
        if not isinstance(self.current, CurrentMetrics):
            raise TypeError("current must be CurrentMetrics")


# =============================================================================
# GATE OUTPUT (explainable)
# =============================================================================

class RegressionPhase(Enum):
    """Regression gate phase."""
    PRE_THRESHOLD = "PRE_THRESHOLD"
    POST_THRESHOLD = "POST_THRESHOLD"


@dataclass
class MetricDelta:
    """
    Metric delta for explainable gate output.
    
    Shows baseline vs current values and the delta.
    """
    metric_name: str
    baseline_value: float
    current_value: float
    delta: float
    unit: MetricUnit
    direction: MetricDirection

    def is_regression(self, max_drop: float = 0.5) -> bool:
        """Check if this delta represents a regression."""
        if self.direction == MetricDirection.HIGHER_IS_BETTER:
            # For higher-is-better, current should not drop below baseline - max_drop
            return self.current_value < self.baseline_value - max_drop
        else:
            # For lower-is-better, current should not exceed baseline
            return self.current_value > self.baseline_value


@dataclass
class RegressionGateResult:
    """
    GC-15 regression gate result (explainable).
    
    Contains pass/fail decision with full explanation.
    """
    passed: bool
    phase: RegressionPhase
    failed_rules: list[str]
    metric_deltas: list[MetricDelta]
    adr_required: bool
    adr_used: bool
    baseline_id: str
    current_commit_hash: Optional[str] = None

    def __post_init__(self) -> None:
        # If failed, must have failed_rules
        if not self.passed and len(self.failed_rules) == 0:
            raise ValueError(
                "failed_rules must be non-empty when passed=false "
                "(GC-15: REGRESSION_GATE_OUTPUT_INVALID)"
            )


# =============================================================================
# PHASE COMPUTATION
# =============================================================================

def compute_regression_phase(
    current_eval_case_count: int,
    policy: RegressionGatingPolicy
) -> RegressionPhase:
    """
    Compute regression phase from CURRENT eval_case_count.
    
    GC-15: Phase uses CURRENT eval_case_count, not baseline count.
    
    Args:
        current_eval_case_count: Current evaluation case count
        policy: Regression gating policy
        
    Returns:
        PRE_THRESHOLD if current_eval_case_count < min_eval_cases
        POST_THRESHOLD if current_eval_case_count >= min_eval_cases
    """
    if current_eval_case_count < policy.min_eval_cases:
        return RegressionPhase.PRE_THRESHOLD
    else:
        return RegressionPhase.POST_THRESHOLD
