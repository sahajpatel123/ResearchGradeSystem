"""
GC-9 Numeric Agreement Contract Tests

Tests for numeric check spec/result/log validation and strong agreement computation.
"""

import pytest
import json
import math
from pathlib import Path
from src.core.numeric_check import (
    NumericCheckSpec,
    NumericCheckResult,
    NumericCheckStatus,
    SamplingStrategy,
    StrongParams,
    LogPayload,
    Point,
)
from src.core.gc9_parsers import (
    parse_float_finite_nonneg,
    parse_int_nonneg,
    parse_payload_ref,
    parse_point,
    parse_seed_if_needed,
    parse_sampling_strategy,
    parse_strong_params,
    parse_numeric_check_spec,
    parse_numeric_check_result,
    parse_log_payload,
)
from src.core.gc9_validators import (
    compute_strong_agreement,
    validate_counts_match_log,
    validate_log_payload,
    validate_strong_agreement,
    validate_numeric_check,
    validate_instability_never_passes,
    get_step_status_from_numeric_result,
)


class TestParseFloatFiniteNonneg:
    """Test parse_float_finite_nonneg wire-boundary parser."""
    
    def test_parse_valid_float(self):
        """GC-9: Valid finite non-negative float passes."""
        assert parse_float_finite_nonneg(0.0, "test") == 0.0
        assert parse_float_finite_nonneg(1e-6, "test") == 1e-6
        assert parse_float_finite_nonneg(100.5, "test") == 100.5
    
    def test_parse_rejects_nan(self):
        """GC-9: Reject NaN."""
        with pytest.raises(ValueError, match="NUMERIC_NONFINITE_TOLERANCE"):
            parse_float_finite_nonneg(float('nan'), "test")
    
    def test_parse_rejects_infinity(self):
        """GC-9: Reject Infinity."""
        with pytest.raises(ValueError, match="NUMERIC_NONFINITE_TOLERANCE"):
            parse_float_finite_nonneg(float('inf'), "test")
        
        with pytest.raises(ValueError, match="NUMERIC_NONFINITE_TOLERANCE"):
            parse_float_finite_nonneg(float('-inf'), "test")
    
    def test_parse_rejects_negative(self):
        """GC-9: Reject negative values."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_TOLERANCE_INVALID"):
            parse_float_finite_nonneg(-1.0, "test")
    
    def test_parse_rejects_wrong_type(self):
        """GC-9: Reject non-numeric types."""
        with pytest.raises(TypeError, match="NUMERIC_WRONG_TYPE"):
            parse_float_finite_nonneg("1.0", "test")


class TestParseIntNonneg:
    """Test parse_int_nonneg wire-boundary parser."""
    
    def test_parse_valid_int(self):
        """GC-9: Valid non-negative int passes."""
        assert parse_int_nonneg(0, "test") == 0
        assert parse_int_nonneg(25, "test") == 25
    
    def test_parse_rejects_float(self):
        """GC-9: Reject float (even if whole number)."""
        with pytest.raises(TypeError, match="NUMERIC_WRONG_TYPE"):
            parse_int_nonneg(25.0, "test")
    
    def test_parse_rejects_negative(self):
        """GC-9: Reject negative int."""
        with pytest.raises(ValueError):
            parse_int_nonneg(-5, "test")


class TestParsePayloadRef:
    """Test parse_payload_ref wire-boundary parser."""
    
    def test_parse_valid_payload_ref(self):
        """GC-9: Valid payload_ref passes."""
        assert parse_payload_ref("logs/check-001.json") == "logs/check-001.json"
    
    def test_parse_rejects_empty(self):
        """GC-9: Reject empty string."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_PAYLOAD_REF_MISSING"):
            parse_payload_ref("")
    
    def test_parse_rejects_none(self):
        """GC-9: Reject None/null."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_PAYLOAD_REF_MISSING"):
            parse_payload_ref(None)
    
    def test_parse_rejects_whitespace_only(self):
        """GC-9: Reject whitespace-only."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_PAYLOAD_REF_MISSING"):
            parse_payload_ref("   ")
    
    def test_parse_rejects_leading_trailing_whitespace(self):
        """GC-9: Reject leading/trailing whitespace (no trimming)."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_PAYLOAD_REF_MISSING"):
            parse_payload_ref("  logs/check.json")


class TestParsePoint:
    """Test parse_point wire-boundary parser."""
    
    def test_parse_valid_point(self):
        """GC-9: Valid point passes."""
        point = parse_point({"x": 1.0, "y": 2.0})
        assert point == {"x": 1.0, "y": 2.0}
    
    def test_parse_rejects_empty_dict(self):
        """GC-9: Reject empty dict."""
        with pytest.raises(ValueError, match="NUMERIC_WRONG_TYPE"):
            parse_point({})
    
    def test_parse_rejects_non_dict(self):
        """GC-9: Reject non-dict."""
        with pytest.raises(TypeError, match="NUMERIC_WRONG_TYPE"):
            parse_point([1.0, 2.0])
    
    def test_parse_rejects_nan_value(self):
        """GC-9: Reject NaN values."""
        with pytest.raises(ValueError, match="NUMERIC_NONFINITE_TOLERANCE"):
            parse_point({"x": float('nan')})


class TestParseSeedIfNeeded:
    """Test parse_seed_if_needed logic."""
    
    def test_seed_required_when_random_count_positive(self):
        """GC-9: seed required when random_points_count > 0."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_RANDOM_REQUIRES_SEED"):
            parse_seed_if_needed(25, None)
    
    def test_seed_valid_when_provided(self):
        """GC-9: Valid seed passes."""
        assert parse_seed_if_needed(25, 42) == 42
    
    def test_seed_not_required_when_random_count_zero(self):
        """GC-9: seed not required when random_points_count == 0."""
        assert parse_seed_if_needed(0, None) is None


class TestSamplingStrategy:
    """Test SamplingStrategy schema validation."""
    
    def test_deterministic_points_required_non_empty(self):
        """GC-9: deterministic_points REQUIRED and NON-EMPTY (teacher correction)."""
        # Empty list rejected
        with pytest.raises(ValueError, match="NUMERIC_SPEC_DETERMINISTIC_POINTS_EMPTY"):
            SamplingStrategy(
                deterministic_points=[],
                random_points_count=0
            )
    
    def test_random_requires_seed(self):
        """GC-9: seed REQUIRED iff random_points_count > 0."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_RANDOM_REQUIRES_SEED"):
            SamplingStrategy(
                deterministic_points=[{"x": 0.5}],
                random_points_count=25,
                seed=None
            )
    
    def test_valid_sampling_strategy(self):
        """GC-9: Valid sampling strategy passes."""
        strategy = SamplingStrategy(
            deterministic_points=[{"x": 0.0}, {"x": 1.0}],
            edge_case_points=[{"x": -1.0}],
            random_points_count=20,
            seed=42
        )
        assert len(strategy.deterministic_points) == 2
        assert strategy.seed == 42


class TestStrongParams:
    """Test StrongParams schema validation."""
    
    def test_n_must_be_at_least_one(self):
        """GC-9: N must be >= 1."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_STRONG_PARAMS_INVALID"):
            StrongParams(N=0, M=0)
    
    def test_m_must_be_nonnegative(self):
        """GC-9: M must be >= 0."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_STRONG_PARAMS_INVALID"):
            StrongParams(N=20, M=-1)
    
    def test_valid_strong_params(self):
        """GC-9: Valid strong params with defaults."""
        params = StrongParams()
        assert params.N == 20
        assert params.M == 0


class TestNumericCheckSpec:
    """Test NumericCheckSpec schema validation."""
    
    def test_spec_requires_property_domain(self):
        """GC-9: property_tested and domain_constraints REQUIRED non-empty."""
        # Missing property_tested
        with pytest.raises(ValueError, match="NUMERIC_SPEC_MISSING_PROPERTY"):
            NumericCheckSpec(
                check_id="check-001",
                property_tested="",
                domain_constraints="x in [0, 1]",
                sampling_strategy=SamplingStrategy(deterministic_points=[{"x": 0.5}]),
                tolerance_abs=1e-6,
                tolerance_rel=1e-6,
                strong_params=StrongParams(),
                solver_settings={},
                payload_ref="logs/check.json"
            )
        
        # Missing domain_constraints
        with pytest.raises(ValueError, match="NUMERIC_SPEC_MISSING_DOMAIN"):
            NumericCheckSpec(
                check_id="check-001",
                property_tested="Test property",
                domain_constraints="",
                sampling_strategy=SamplingStrategy(deterministic_points=[{"x": 0.5}]),
                tolerance_abs=1e-6,
                tolerance_rel=1e-6,
                strong_params=StrongParams(),
                solver_settings={},
                payload_ref="logs/check.json"
            )
    
    def test_tolerances_finite_and_nonnegative(self):
        """GC-9: Tolerances must be finite and >= 0."""
        # NaN tolerance
        with pytest.raises(ValueError, match="NUMERIC_NONFINITE_TOLERANCE"):
            NumericCheckSpec(
                check_id="check-001",
                property_tested="Test",
                domain_constraints="x in [0, 1]",
                sampling_strategy=SamplingStrategy(deterministic_points=[{"x": 0.5}]),
                tolerance_abs=float('nan'),
                tolerance_rel=1e-6,
                strong_params=StrongParams(),
                solver_settings={},
                payload_ref="logs/check.json"
            )
        
        # Negative tolerance
        with pytest.raises(ValueError, match="NUMERIC_SPEC_TOLERANCE_INVALID"):
            NumericCheckSpec(
                check_id="check-001",
                property_tested="Test",
                domain_constraints="x in [0, 1]",
                sampling_strategy=SamplingStrategy(deterministic_points=[{"x": 0.5}]),
                tolerance_abs=-1e-6,
                tolerance_rel=1e-6,
                strong_params=StrongParams(),
                solver_settings={},
                payload_ref="logs/check.json"
            )
    
    def test_solver_settings_required(self):
        """GC-9: solver_settings REQUIRED (may be empty dict)."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_SOLVER_SETTINGS_MISSING"):
            NumericCheckSpec(
                check_id="check-001",
                property_tested="Test",
                domain_constraints="x in [0, 1]",
                sampling_strategy=SamplingStrategy(deterministic_points=[{"x": 0.5}]),
                tolerance_abs=1e-6,
                tolerance_rel=1e-6,
                strong_params=StrongParams(),
                solver_settings=None,
                payload_ref="logs/check.json"
            )
    
    def test_payload_ref_required(self):
        """GC-9: payload_ref REQUIRED non-empty."""
        with pytest.raises(ValueError, match="NUMERIC_SPEC_PAYLOAD_REF_MISSING"):
            NumericCheckSpec(
                check_id="check-001",
                property_tested="Test",
                domain_constraints="x in [0, 1]",
                sampling_strategy=SamplingStrategy(deterministic_points=[{"x": 0.5}]),
                tolerance_abs=1e-6,
                tolerance_rel=1e-6,
                strong_params=StrongParams(),
                solver_settings={},
                payload_ref=""
            )


class TestLogPayload:
    """Test LogPayload schema validation."""
    
    def test_log_requires_aligned_lengths(self):
        """GC-9: points, outputs, per_point_status must have aligned lengths."""
        with pytest.raises(ValueError, match="NUMERIC_LOG_LENGTH_MISMATCH"):
            LogPayload(
                points=[{"x": 0.5}, {"x": 1.0}],
                outputs=[0.25],  # Mismatched length
                per_point_status=["pass", "pass"],
                point_kind=["deterministic", "deterministic"],
                seed=None,
                solver_settings={},
                tolerance_abs=1e-6,
                tolerance_rel=1e-6
            )
    
    def test_log_validates_per_point_status_enum(self):
        """GC-9: per_point_status must be strict enum values."""
        with pytest.raises(ValueError, match="must be 'pass', 'fail', or 'indeterminate'"):
            LogPayload(
                points=[{"x": 0.5}],
                outputs=[0.25],
                per_point_status=["PASS"],  # Wrong case
                point_kind=["deterministic"],
                seed=None,
                solver_settings={},
                tolerance_abs=1e-6,
                tolerance_rel=1e-6
            )


class TestStrongAgreementComputation:
    """Test strong agreement computation (computed-only)."""
    
    def test_strong_agreement_computed_and_enforced(self):
        """GC-9: strong_agreement is COMPUTED, never trusted from wire."""
        spec = NumericCheckSpec(
            check_id="check-001",
            property_tested="Test",
            domain_constraints="x in [0, 1]",
            sampling_strategy=SamplingStrategy(
                deterministic_points=[{"x": 0.0}, {"x": 0.5}, {"x": 1.0}],
                random_points_count=25,
                seed=42
            ),
            tolerance_abs=1e-6,
            tolerance_rel=1e-6,
            strong_params=StrongParams(N=20, M=0),
            solver_settings={},
            payload_ref="logs/check.json"
        )
        
        # All pass (3 deterministic + 25 random)
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=28,
            fail_count=0,
            indeterminate_count=0,
            strong_agreement=True
        )
        
        log = LogPayload(
            points=[{"x": i/10} for i in range(28)],
            outputs=[i/10 for i in range(28)],
            per_point_status=["pass"] * 28,
            point_kind=["deterministic"] * 3 + ["edge"] * 2 + ["random"] * 23,
            seed=42,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        # Compute strong agreement
        computed = compute_strong_agreement(spec, result, log)
        assert computed == True
    
    def test_strong_agreement_rejects_random_count_below_n(self):
        """GC-9: strong_agreement requires random_pass_count >= N."""
        spec = NumericCheckSpec(
            check_id="check-001",
            property_tested="Test",
            domain_constraints="x in [0, 1]",
            sampling_strategy=SamplingStrategy(
                deterministic_points=[{"x": 0.5}],
                random_points_count=10,
                seed=42
            ),
            tolerance_abs=1e-6,
            tolerance_rel=1e-6,
            strong_params=StrongParams(N=20, M=0),
            solver_settings={},
            payload_ref="logs/check.json"
        )
        
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=11,
            fail_count=0,
            indeterminate_count=0,
            strong_agreement=False
        )
        
        log = LogPayload(
            points=[{"x": i/10} for i in range(11)],
            outputs=[i/10 for i in range(11)],
            per_point_status=["pass"] * 11,
            point_kind=["deterministic"] + ["random"] * 10,
            seed=42,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        # Compute strong agreement (should be False: random_count=10 < N=20)
        computed = compute_strong_agreement(spec, result, log)
        assert computed == False
    
    def test_indeterminate_respects_m(self):
        """GC-9: strong_agreement requires indeterminate_count <= M."""
        spec = NumericCheckSpec(
            check_id="check-001",
            property_tested="Test",
            domain_constraints="x in [0, 1]",
            sampling_strategy=SamplingStrategy(
                deterministic_points=[{"x": 0.5}],
                random_points_count=25,
                seed=42
            ),
            tolerance_abs=1e-6,
            tolerance_rel=1e-6,
            strong_params=StrongParams(N=20, M=0),
            solver_settings={},
            payload_ref="logs/check.json"
        )
        
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=24,
            fail_count=0,
            indeterminate_count=2,  # > M=0
            strong_agreement=False
        )
        
        log = LogPayload(
            points=[{"x": i/10} for i in range(26)],
            outputs=[i/10 for i in range(26)],
            per_point_status=["pass"] * 24 + ["indeterminate"] * 2,
            point_kind=["deterministic"] + ["random"] * 25,
            seed=42,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        # Compute strong agreement (should be False: indeterminate_count=2 > M=0)
        computed = compute_strong_agreement(spec, result, log)
        assert computed == False


class TestCountsMatchLog:
    """Test counts match per_point_status validation."""
    
    def test_counts_match_per_point_status(self):
        """GC-9: Result counts must match log per_point_status tallies."""
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=5,
            fail_count=2,
            indeterminate_count=1,
            strong_agreement=False
        )
        
        log = LogPayload(
            points=[{"x": i/10} for i in range(8)],
            outputs=[i/10 for i in range(8)],
            per_point_status=["pass"] * 5 + ["fail"] * 2 + ["indeterminate"],
            point_kind=["deterministic"] * 8,
            seed=None,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        # Should not raise
        validate_counts_match_log(result, log)
    
    def test_counts_mismatch_raises_error(self):
        """GC-9: Count mismatch raises error."""
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=10,  # Claims 10
            fail_count=0,
            indeterminate_count=0,
            strong_agreement=False
        )
        
        log = LogPayload(
            points=[{"x": i/10} for i in range(5)],
            outputs=[i/10 for i in range(5)],
            per_point_status=["pass"] * 5,  # Actually 5
            point_kind=["deterministic"] * 5,
            seed=None,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        with pytest.raises(ValueError, match="NUMERIC_RESULT_COUNT_MISMATCH"):
            validate_counts_match_log(result, log)


class TestGC91FreezeBlockers:
    """Test GC-9.1 freeze blockers."""
    
    def test_point_kind_enables_robust_random_pass_count(self):
        """GC-9.1: point_kind enables robust random_pass_count computation (Option A)."""
        spec = NumericCheckSpec(
            check_id="check-001",
            property_tested="Test",
            domain_constraints="x in [0, 1]",
            sampling_strategy=SamplingStrategy(
                deterministic_points=[{"x": 0.0}, {"x": 0.5}, {"x": 1.0}],
                random_points_count=10,
                seed=42
            ),
            tolerance_abs=1e-6,
            tolerance_rel=1e-6,
            strong_params=StrongParams(N=20, M=0),
            solver_settings={},
            payload_ref="logs/check.json"
        )
        
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=13,  # 3 deterministic + 10 random
            fail_count=0,
            indeterminate_count=0,
            strong_agreement=True  # Claims strong agreement
        )
        
        log = LogPayload(
            points=[{"x": i/10} for i in range(13)],
            outputs=[i/10 for i in range(13)],
            per_point_status=["pass"] * 13,
            point_kind=["deterministic", "deterministic", "deterministic"] + ["random"] * 10,
            seed=42,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        # Should raise strong agreement mismatch (random_pass_count=10 < N=20)
        with pytest.raises(ValueError, match="NUMERIC_STRONG_AGREEMENT_MISMATCH"):
            validate_strong_agreement(spec, result, log)
    
    def test_instability_nan_never_passes(self):
        """GC-9.1: NaN output cannot be marked as pass."""
        log = LogPayload(
            points=[{"x": 0.5}],
            outputs=[float('nan')],
            per_point_status=["pass"],  # Invalid: NaN should not be pass
            point_kind=["deterministic"],
            seed=None,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_instability_never_passes(log)
    
    def test_instability_inf_never_passes(self):
        """GC-9.1: Infinity output cannot be marked as pass."""
        log = LogPayload(
            points=[{"x": 0.5}],
            outputs=[float('inf')],
            per_point_status=["pass"],  # Invalid: Infinity should not be pass
            point_kind=["deterministic"],
            seed=None,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_instability_never_passes(log)
    
    def test_instability_missing_never_passes(self):
        """GC-9.1: Missing/null output cannot be marked as pass."""
        log = LogPayload(
            points=[{"x": 0.5}],
            outputs=[None],  # Missing output
            per_point_status=["pass"],  # Invalid: missing should not be pass
            point_kind=["deterministic"],
            seed=None,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_instability_never_passes(log)
    
    def test_instability_runtime_notes_timeout(self):
        """GC-9.1: Runtime notes timeout prevents pass status."""
        log = LogPayload(
            points=[{"x": 0.5}, {"x": 0.6}],
            outputs=[0.25, 0.36],
            per_point_status=["pass", "pass"],  # Invalid: timeout should not be pass
            point_kind=["deterministic", "deterministic"],
            seed=None,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6,
            runtime_notes="Solver timeout occurred during evaluation"
        )
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_instability_never_passes(log)
    
    def test_point_kind_validation(self):
        """GC-9.1: point_kind must be valid and match spec structure."""
        spec = NumericCheckSpec(
            check_id="check-001",
            property_tested="Test",
            domain_constraints="x in [0, 1]",
            sampling_strategy=SamplingStrategy(
                deterministic_points=[{"x": 0.5}],
                random_points_count=5,
                seed=42
            ),
            tolerance_abs=1e-6,
            tolerance_rel=1e-6,
            strong_params=StrongParams(),
            solver_settings={},
            payload_ref="logs/check.json"
        )
        
        # Mismatch point_kind counts
        log = LogPayload(
            points=[{"x": i/10} for i in range(6)],
            outputs=[i/10 for i in range(6)],
            per_point_status=["pass"] * 6,
            point_kind=["deterministic"] * 2 + ["random"] * 4,  # Wrong: should be 1 deterministic, 5 random
            seed=42,
            solver_settings={},
            tolerance_abs=1e-6,
            tolerance_rel=1e-6
        )
        
        with pytest.raises(ValueError, match="point_kind deterministic count mismatch"):
            validate_log_payload(spec, log)


class TestGC9Fixtures:
    """Test GC-9 fixtures."""
    
    def test_fixture_pass_strong_agreement(self):
        """PASS fixture: Strong agreement satisfied."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_pass_strong_agreement.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        log = parse_log_payload(data["log"])
        
        # Should not raise
        validate_numeric_check(spec, result, log)
        
        # Verify strong agreement
        assert result.strong_agreement == True
    
    def test_fixture_pass_non_strong(self):
        """PASS fixture: Non-strong pass (random_count < N)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_pass_non_strong.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        log = parse_log_payload(data["log"])
        
        # Should not raise
        validate_numeric_check(spec, result, log)
        
        # Verify NOT strong agreement
        assert result.strong_agreement == False
    
    def test_fixture_fail_missing_property(self):
        """FAIL fixture: Missing property_tested."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_missing_property.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_MISSING_PROPERTY"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_missing_domain(self):
        """FAIL fixture: Missing domain_constraints."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_missing_domain.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_MISSING_DOMAIN"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_deterministic_empty(self):
        """FAIL fixture: deterministic_points empty (FORBIDDEN)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_deterministic_empty.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_DETERMINISTIC_POINTS_EMPTY"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_random_missing_seed(self):
        """FAIL fixture: random_points_count > 0 but seed missing."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_random_missing_seed.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_RANDOM_REQUIRES_SEED"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_negative_tolerance(self):
        """FAIL fixture: Negative tolerance."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_negative_tolerance.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_TOLERANCE_INVALID"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_strong_mismatch(self):
        """FAIL fixture: strong_agreement mismatch."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_strong_mismatch.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        log = parse_log_payload(data["log"])
        
        with pytest.raises(ValueError, match="NUMERIC_STRONG_AGREEMENT_MISMATCH"):
            validate_numeric_check(spec, result, log)
    
    def test_fixture_fail_count_mismatch(self):
        """FAIL fixture: Count mismatch."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_count_mismatch.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        log = parse_log_payload(data["log"])
        
        with pytest.raises(ValueError, match="NUMERIC_RESULT_COUNT_MISMATCH"):
            validate_numeric_check(spec, result, log)
    
    def test_fixture_fail_missing_payload_ref(self):
        """FAIL fixture: Missing payload_ref."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_missing_payload_ref.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_PAYLOAD_REF_MISSING"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_missing_solver_settings(self):
        """FAIL fixture: Missing solver_settings."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_missing_solver_settings.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        with pytest.raises(ValueError, match="NUMERIC_SPEC_SOLVER_SETTINGS_MISSING"):
            parse_numeric_check_spec(data["spec"])
    
    def test_fixture_fail_instability_nan_pass(self):
        """FAIL fixture: NaN output marked as pass."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_instability_nan_pass.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        
        # Manually construct log with actual NaN (JSON doesn't support NaN)
        log = LogPayload(
            points=data["log"]["points"],
            outputs=[float('nan')],  # Actual NaN value
            per_point_status=data["log"]["per_point_status"],
            point_kind=data["log"]["point_kind"],
            seed=data["log"]["seed"],
            solver_settings=data["log"]["solver_settings"],
            tolerance_abs=data["log"]["tolerance_abs"],
            tolerance_rel=data["log"]["tolerance_rel"],
            runtime_notes=data["log"]["runtime_notes"]
        )
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_numeric_check(spec, result, log)
    
    def test_fixture_fail_instability_inf_pass(self):
        """FAIL fixture: Infinity output marked as pass."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_instability_inf_pass.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        
        # Manually construct log with actual Infinity (JSON doesn't support Infinity)
        log = LogPayload(
            points=data["log"]["points"],
            outputs=[float('inf')],  # Actual Infinity value
            per_point_status=data["log"]["per_point_status"],
            point_kind=data["log"]["point_kind"],
            seed=data["log"]["seed"],
            solver_settings=data["log"]["solver_settings"],
            tolerance_abs=data["log"]["tolerance_abs"],
            tolerance_rel=data["log"]["tolerance_rel"],
            runtime_notes=data["log"]["runtime_notes"]
        )
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_numeric_check(spec, result, log)
    
    def test_fixture_fail_instability_missing_pass(self):
        """FAIL fixture: Missing/null output marked as pass."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_instability_missing_pass.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        log = parse_log_payload(data["log"])
        
        with pytest.raises(ValueError, match="INSTABILITY_TREATED_AS_PASS"):
            validate_numeric_check(spec, result, log)
    
    def test_fixture_fail_random_pass_conflation(self):
        """FAIL fixture: strong_agreement claims true but random_pass_count < N."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc9_fail_random_pass_conflation.json"
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        spec = parse_numeric_check_spec(data["spec"])
        result = parse_numeric_check_result(data["result"])
        log = parse_log_payload(data["log"])
        
        with pytest.raises(ValueError, match="NUMERIC_STRONG_AGREEMENT_MISMATCH"):
            validate_numeric_check(spec, result, log)


class TestStepStatusMapping:
    """Test NumericCheckResult status to step_status mapping."""
    
    def test_pass_maps_to_checked(self):
        """GC-9: pass -> checked."""
        result = NumericCheckResult(
            status=NumericCheckStatus.PASS,
            pass_count=10,
            fail_count=0,
            indeterminate_count=0,
            strong_agreement=False
        )
        assert get_step_status_from_numeric_result(result) == "checked"
    
    def test_fail_maps_to_failed(self):
        """GC-9: fail -> failed."""
        result = NumericCheckResult(
            status=NumericCheckStatus.FAIL,
            pass_count=5,
            fail_count=5,
            indeterminate_count=0,
            strong_agreement=False
        )
        assert get_step_status_from_numeric_result(result) == "failed"
    
    def test_indeterminate_maps_to_indeterminate(self):
        """GC-9: indeterminate -> indeterminate."""
        result = NumericCheckResult(
            status=NumericCheckStatus.INDETERMINATE,
            pass_count=5,
            fail_count=0,
            indeterminate_count=5,
            strong_agreement=False
        )
        assert get_step_status_from_numeric_result(result) == "indeterminate"
