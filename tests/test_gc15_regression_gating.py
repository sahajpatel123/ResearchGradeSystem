"""
GC-15 Regression Gating Tests.

Tests prove:
- Pre-threshold gate uses absolute fail counts
- Pre-threshold gate blocks unsupported claim rate increase
- Post-threshold gate blocks absolute drop above 0.5pp
- Post-threshold gate blocks any unsupported claim rate increase
- Regression exception requires ADR
- Unsupported claim rate cannot be waived by default
- Gate compares against declared baseline artifact
- Metric registry requires direction and unit
- Phase uses current eval_case_count
- Gate result explains failures
"""

import json
from pathlib import Path

import pytest

from src.core.gc15_validators import (
    GC15ErrorCategory,
    GC15ValidationError,
    evaluate_regression_gate,
    validate_baseline,
    validate_current_metrics,
    validate_gate_result,
    validate_metric_registry,
)
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


def _load_fixture(name: str) -> dict:
    """Load a GC-15 fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / name
    with open(fixture_path, "r") as f:
        return json.load(f)


def _build_baseline_from_fixture(data: dict) -> RegressionBaseline:
    """Build RegressionBaseline from fixture data."""
    b = data["baseline"]
    return RegressionBaseline(
        baseline_id=b["baseline_id"],
        baseline_commit_hash=b["baseline_commit_hash"],
        eval_case_count=b["eval_case_count"],
        fail_count=b["fail_count"],
        metrics=b["metrics"],
        created_at=b["created_at"],
    )


def _build_current_from_fixture(data: dict) -> CurrentMetrics:
    """Build CurrentMetrics from fixture data."""
    c = data["current"]
    return CurrentMetrics(
        eval_case_count=c["eval_case_count"],
        fail_count=c["fail_count"],
        metrics=c["metrics"],
        commit_hash=c.get("commit_hash"),
    )


def _build_gate_input_from_fixture(data: dict) -> RegressionGateInput:
    """Build RegressionGateInput from fixture data."""
    baseline = _build_baseline_from_fixture(data)
    current = _build_current_from_fixture(data)
    return RegressionGateInput(
        baseline=baseline,
        current=current,
        adr_present=data.get("adr_present", False),
        adr_id=data.get("adr_id"),
    )


class TestPreThresholdGateUsesAbsoluteFailCounts:
    """Test pre-threshold gate uses absolute fail counts."""

    def test_pre_threshold_gate_uses_absolute_fail_counts(self):
        """Pre-threshold: fail_count must not increase."""
        data = _load_fixture("gc15_fail_pre_threshold_fail_count_increase.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.PRE_THRESHOLD
        assert result.passed is False
        assert GC15ErrorCategory.PRE_THRESHOLD_FAIL_COUNT_INCREASED in result.failed_rules

    def test_pre_threshold_pass_when_fail_count_unchanged(self):
        """Pre-threshold: passes when fail_count unchanged or lower."""
        data = _load_fixture("gc15_pass_pre_threshold.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.PRE_THRESHOLD
        assert result.passed is True
        assert len(result.failed_rules) == 0


class TestPreThresholdGateBlocksUnsupportedClaimRateIncrease:
    """Test pre-threshold gate blocks unsupported claim rate increase."""

    def test_pre_threshold_gate_blocks_unsupported_claim_rate_increase(self):
        """Pre-threshold: unsupported_claim_rate must not increase."""
        data = _load_fixture("gc15_fail_pre_threshold_ucr_increase.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.PRE_THRESHOLD
        assert result.passed is False
        assert GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in result.failed_rules


class TestPostThresholdGateBlocksAbsoluteDropAbovePointFive:
    """Test post-threshold gate blocks absolute drop above 0.5pp."""

    def test_post_threshold_gate_blocks_absolute_drop_above_point_five(self):
        """Post-threshold: metric drop > 0.5pp fails."""
        data = _load_fixture("gc15_fail_post_threshold_metric_drop.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.POST_THRESHOLD
        assert result.passed is False
        assert GC15ErrorCategory.REGRESSION_METRIC_DROP_EXCEEDED in result.failed_rules

    def test_post_threshold_pass_when_drop_within_limit(self):
        """Post-threshold: passes when drop <= 0.5pp."""
        data = _load_fixture("gc15_pass_post_threshold.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.POST_THRESHOLD
        assert result.passed is True


class TestPostThresholdGateBlocksAnyUnsupportedClaimRateIncrease:
    """Test post-threshold gate blocks any unsupported claim rate increase."""

    def test_post_threshold_gate_blocks_any_unsupported_claim_rate_increase(self):
        """Post-threshold: any unsupported_claim_rate increase fails."""
        data = _load_fixture("gc15_fail_post_threshold_ucr_increase.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.POST_THRESHOLD
        assert result.passed is False
        assert GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in result.failed_rules


class TestRegressionExceptionRequiresAdr:
    """Test regression exception requires ADR."""

    def test_regression_exception_requires_adr(self):
        """Metric drop failure requires ADR to pass."""
        data = _load_fixture("gc15_pass_adr_waiver.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is True
        assert result.adr_used is True
        assert result.adr_required is True

    def test_adr_missing_id_fails(self):
        """ADR present but missing adr_id fails."""
        data = _load_fixture("gc15_fail_adr_missing.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.ADR_REQUIRED_MISSING in result.failed_rules


class TestUnsupportedClaimRateCannotBeWaivedByDefault:
    """Test unsupported claim rate cannot be waived by default."""

    def test_unsupported_claim_rate_cannot_be_waived_by_default(self):
        """ADR cannot waive unsupported_claim_rate increase by default."""
        data = _load_fixture("gc15_fail_adr_cannot_waive_ucr.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        policy = RegressionGatingPolicy()
        assert policy.allow_adr_override_for_unsupported_claim_rate is False
        
        result = evaluate_regression_gate(gate_input, policy)
        
        assert result.passed is False
        assert GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in result.failed_rules
        assert GC15ErrorCategory.ADR_OVERRIDE_NOT_ALLOWED_FOR_UNSUPPORTED_CLAIM_RATE in result.failed_rules


class TestGateComparesAgainstDeclaredBaselineArtifact:
    """Test gate compares against declared baseline artifact."""

    def test_gate_compares_against_declared_baseline_artifact(self):
        """Gate uses RegressionBaseline artifact, not ad hoc metrics."""
        data = _load_fixture("gc15_pass_pre_threshold.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        # Result includes baseline_id from the declared artifact
        assert result.baseline_id == data["baseline"]["baseline_id"]
        
        # Metric deltas are computed from baseline artifact
        assert len(result.metric_deltas) > 0
        for delta in result.metric_deltas:
            assert delta.baseline_value == data["baseline"]["metrics"].get(delta.metric_name, 0.0)

    def test_baseline_missing_fails_validation(self):
        """Missing baseline artifact fails validation."""
        errors = validate_baseline(None)
        
        assert len(errors) == 1
        assert errors[0].category == GC15ErrorCategory.REGRESSION_BASELINE_MISSING


class TestMetricRegistryRequiresDirectionAndUnit:
    """Test metric registry requires direction and unit."""

    def test_metric_registry_requires_direction_and_unit(self):
        """All tracked metrics have direction and unit."""
        errors = validate_metric_registry()
        
        # Registry should be valid
        assert len(errors) == 0
        
        # All metrics have direction and unit
        for metric_name, metric in TRACKED_METRIC_REGISTRY.items():
            assert isinstance(metric.direction, MetricDirection)
            assert isinstance(metric.unit, MetricUnit)

    def test_unsupported_claim_rate_is_protected(self):
        """unsupported_claim_rate is in protected metrics."""
        assert is_metric_protected("unsupported_claim_rate")
        assert "unsupported_claim_rate" in PROTECTED_METRICS


class TestPhaseUsesCurrentEvalCaseCount:
    """Test phase uses current eval_case_count."""

    def test_phase_uses_current_eval_case_count(self):
        """Phase computed from CURRENT eval_case_count, not baseline."""
        data = _load_fixture("gc15_fail_phase_wrong_source.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        # Baseline has 150 cases (PRE_THRESHOLD if used)
        # Current has 250 cases (POST_THRESHOLD)
        policy = RegressionGatingPolicy(min_eval_cases=200)
        
        phase = compute_regression_phase(
            gate_input.current.eval_case_count,
            policy,
        )
        
        # Must use current (250), not baseline (150)
        assert phase == RegressionPhase.POST_THRESHOLD
        
        # Wrong if using baseline
        wrong_phase = compute_regression_phase(
            gate_input.baseline.eval_case_count,
            policy,
        )
        assert wrong_phase == RegressionPhase.PRE_THRESHOLD

    def test_threshold_boundary_200_is_post_threshold(self):
        """Exactly 200 cases triggers POST_THRESHOLD."""
        data = _load_fixture("gc15_pass_threshold_boundary.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        assert gate_input.current.eval_case_count == 200
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.phase == RegressionPhase.POST_THRESHOLD


class TestGateResultExplainsFailures:
    """Test gate result explains failures."""

    def test_gate_result_explains_failures(self):
        """Failed gate result includes failed_rules and metric_deltas."""
        data = _load_fixture("gc15_fail_post_threshold_metric_drop.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert len(result.failed_rules) > 0
        assert len(result.metric_deltas) > 0
        
        # Find the metric that caused the failure
        symbolic_delta = next(
            (d for d in result.metric_deltas if d.metric_name == "symbolic_correctness"),
            None
        )
        assert symbolic_delta is not None
        assert symbolic_delta.delta < -0.5  # Dropped by more than 0.5

    def test_passed_gate_has_empty_failed_rules(self):
        """Passed gate result has empty failed_rules."""
        data = _load_fixture("gc15_pass_post_threshold.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is True
        assert len(result.failed_rules) == 0


class TestTrackedMetricRegistry:
    """Test tracked metric registry."""

    def test_registry_has_required_metrics(self):
        """Registry has all required metrics."""
        required = [
            "symbolic_correctness",
            "derivation_correctness",
            "unit_consistency_pass_rate",
            "limit_special_case_pass_rate",
            "numeric_agreement_pass_rate",
            "reproducibility_rerun_success",
            "proof_check_success_rate",
            "unsupported_claim_rate",
        ]
        
        for metric_name in required:
            assert is_metric_tracked(metric_name), f"Missing: {metric_name}"

    def test_get_tracked_metric(self):
        """get_tracked_metric returns correct metric info."""
        metric = get_tracked_metric("symbolic_correctness")
        
        assert metric is not None
        assert metric.direction == MetricDirection.HIGHER_IS_BETTER
        assert metric.unit == MetricUnit.PERCENTAGE_POINTS

    def test_unsupported_claim_rate_is_lower_is_better(self):
        """unsupported_claim_rate is lower_is_better."""
        metric = get_tracked_metric("unsupported_claim_rate")
        
        assert metric is not None
        assert metric.direction == MetricDirection.LOWER_IS_BETTER
        assert metric.unit == MetricUnit.RATIO


class TestRegressionGatingPolicy:
    """Test RegressionGatingPolicy defaults."""

    def test_default_policy_values(self):
        """Default policy has correct values."""
        policy = RegressionGatingPolicy()
        
        assert policy.min_eval_cases == 200
        assert policy.pre_threshold.absolute_fail_count_must_not_increase is True
        assert policy.pre_threshold.unsupported_claim_rate_must_not_increase is True
        assert policy.post_threshold.max_absolute_metric_drop == 0.5
        assert policy.post_threshold.unsupported_claim_rate_must_not_increase is True
        assert policy.exceptions_require_adr is True
        assert policy.allow_adr_override_for_unsupported_claim_rate is False

    def test_min_eval_cases_must_be_positive(self):
        """min_eval_cases must be > 0."""
        with pytest.raises(ValueError, match="min_eval_cases must be > 0"):
            RegressionGatingPolicy(min_eval_cases=0)

    def test_max_absolute_metric_drop_must_be_non_negative(self):
        """max_absolute_metric_drop must be >= 0."""
        from src.core.regression_gating import PostThresholdPolicy
        
        with pytest.raises(ValueError, match="max_absolute_metric_drop must be >= 0"):
            PostThresholdPolicy(max_absolute_metric_drop=-0.1)


class TestMetricDelta:
    """Test MetricDelta."""

    def test_metric_delta_is_regression_higher_is_better(self):
        """MetricDelta.is_regression for higher_is_better."""
        delta = MetricDelta(
            metric_name="symbolic_correctness",
            baseline_value=92.0,
            current_value=91.0,
            delta=-1.0,
            unit=MetricUnit.PERCENTAGE_POINTS,
            direction=MetricDirection.HIGHER_IS_BETTER,
        )
        
        # Drop of 1.0 exceeds 0.5 max
        assert delta.is_regression(max_drop=0.5) is True
        
        # Drop of 1.0 does not exceed 1.5 max
        assert delta.is_regression(max_drop=1.5) is False

    def test_metric_delta_is_regression_lower_is_better(self):
        """MetricDelta.is_regression for lower_is_better."""
        delta = MetricDelta(
            metric_name="unsupported_claim_rate",
            baseline_value=0.05,
            current_value=0.06,
            delta=0.01,
            unit=MetricUnit.RATIO,
            direction=MetricDirection.LOWER_IS_BETTER,
        )
        
        # Any increase is regression for lower_is_better
        assert delta.is_regression() is True


class TestValidateCurrentMetrics:
    """Test validate_current_metrics."""

    def test_missing_metric_fails_validation(self):
        """Missing tracked metric fails validation."""
        data = _load_fixture("gc15_fail_missing_metric.json")
        current = _build_current_from_fixture(data)
        
        errors = validate_current_metrics(current)
        
        assert len(errors) > 0
        assert any(
            e.category == GC15ErrorCategory.TRACKED_METRIC_REGISTRY_INVALID
            for e in errors
        )


class TestPassFixtures:
    """Test all PASS fixtures."""

    def test_fixture_pass_pre_threshold(self):
        """PASS fixture: pre-threshold pass."""
        data = _load_fixture("gc15_pass_pre_threshold.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is True
        assert result.phase == RegressionPhase.PRE_THRESHOLD

    def test_fixture_pass_post_threshold(self):
        """PASS fixture: post-threshold pass."""
        data = _load_fixture("gc15_pass_post_threshold.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is True
        assert result.phase == RegressionPhase.POST_THRESHOLD

    def test_fixture_pass_adr_waiver(self):
        """PASS fixture: ADR waiver."""
        data = _load_fixture("gc15_pass_adr_waiver.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is True
        assert result.adr_used is True

    def test_fixture_pass_threshold_boundary(self):
        """PASS fixture: threshold boundary."""
        data = _load_fixture("gc15_pass_threshold_boundary.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is True
        assert result.phase == RegressionPhase.POST_THRESHOLD


class TestFailFixtures:
    """Test all FAIL fixtures."""

    def test_fixture_fail_pre_threshold_fail_count_increase(self):
        """FAIL fixture: pre-threshold fail count increase."""
        data = _load_fixture("gc15_fail_pre_threshold_fail_count_increase.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.PRE_THRESHOLD_FAIL_COUNT_INCREASED in result.failed_rules

    def test_fixture_fail_pre_threshold_ucr_increase(self):
        """FAIL fixture: pre-threshold UCR increase."""
        data = _load_fixture("gc15_fail_pre_threshold_ucr_increase.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in result.failed_rules

    def test_fixture_fail_post_threshold_metric_drop(self):
        """FAIL fixture: post-threshold metric drop."""
        data = _load_fixture("gc15_fail_post_threshold_metric_drop.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.REGRESSION_METRIC_DROP_EXCEEDED in result.failed_rules

    def test_fixture_fail_post_threshold_ucr_increase(self):
        """FAIL fixture: post-threshold UCR increase."""
        data = _load_fixture("gc15_fail_post_threshold_ucr_increase.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in result.failed_rules

    def test_fixture_fail_adr_missing(self):
        """FAIL fixture: ADR missing."""
        data = _load_fixture("gc15_fail_adr_missing.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.ADR_REQUIRED_MISSING in result.failed_rules

    def test_fixture_fail_adr_cannot_waive_ucr(self):
        """FAIL fixture: ADR cannot waive UCR."""
        data = _load_fixture("gc15_fail_adr_cannot_waive_ucr.json")
        gate_input = _build_gate_input_from_fixture(data)
        
        result = evaluate_regression_gate(gate_input)
        
        assert result.passed is False
        assert GC15ErrorCategory.UNSUPPORTED_CLAIM_RATE_INCREASED in result.failed_rules
