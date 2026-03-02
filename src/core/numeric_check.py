"""
GC-9 Numeric Agreement Contract

Schema for numeric checks with deterministic + random sampling, strong agreement computation,
and replayable log payloads. Prevents "lucky passes" through required deterministic points.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NumericCheckStatus(Enum):
    """
    GC-9: Numeric check result status.
    
    - pass: All checks passed within tolerances
    - fail: One or more checks failed
    - indeterminate: Unable to determine (timeout, NaN, etc.)
    """
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


# Point type: dict[str, float] for named parameters (v0)
# Example: {"x": 1.0, "y": 2.0} or {"t": 0.5}
Point = dict[str, float]


@dataclass
class StrongParams:
    """
    GC-9: Strong agreement parameters.
    
    Strong agreement requires:
    - All deterministic points pass
    - At least N random points pass
    - Zero failures
    - At most M indeterminate results
    
    Defaults: N=20, M=0 (strict)
    """
    N: int = 20  # Minimum random passes required (must be >= 1)
    M: int = 0   # Maximum indeterminate allowed (must be >= 0)
    
    def __post_init__(self):
        if not isinstance(self.N, int):
            raise TypeError(f"StrongParams.N must be int, got {type(self.N).__name__}")
        if not isinstance(self.M, int):
            raise TypeError(f"StrongParams.M must be int, got {type(self.M).__name__}")
        if self.N < 1:
            raise ValueError(f"StrongParams.N must be >= 1, got {self.N} (GC-9: NUMERIC_SPEC_STRONG_PARAMS_INVALID)")
        if self.M < 0:
            raise ValueError(f"StrongParams.M must be >= 0, got {self.M} (GC-9: NUMERIC_SPEC_STRONG_PARAMS_INVALID)")


@dataclass
class SamplingStrategy:
    """
    GC-9: Sampling strategy for numeric checks.
    
    REQUIRED: deterministic_points must be non-empty (hard rule).
    OPTIONAL: edge_case_points, random sampling with seed.
    
    Teacher correction: Random-only checks are FORBIDDEN.
    Deterministic points prevent "lucky passes" and ensure repeatability.
    """
    deterministic_points: list[Point]
    edge_case_points: list[Point] = field(default_factory=list)
    random_points_count: int = 0
    seed: Optional[int] = None
    
    def __post_init__(self):
        # GC-9: deterministic_points REQUIRED and NON-EMPTY (hard rule)
        if not self.deterministic_points:
            raise ValueError(
                "SamplingStrategy.deterministic_points cannot be empty (GC-9: NUMERIC_SPEC_DETERMINISTIC_POINTS_EMPTY)"
            )
        
        # Validate deterministic_points is a list
        if not isinstance(self.deterministic_points, list):
            raise TypeError(
                f"SamplingStrategy.deterministic_points must be list, got {type(self.deterministic_points).__name__}"
            )
        
        # Validate random_points_count
        if not isinstance(self.random_points_count, int):
            raise TypeError(
                f"SamplingStrategy.random_points_count must be int, got {type(self.random_points_count).__name__}"
            )
        if self.random_points_count < 0:
            raise ValueError(
                f"SamplingStrategy.random_points_count must be >= 0, got {self.random_points_count}"
            )
        
        # GC-9: seed REQUIRED iff random_points_count > 0
        if self.random_points_count > 0 and self.seed is None:
            raise ValueError(
                "SamplingStrategy.seed is required when random_points_count > 0 (GC-9: NUMERIC_SPEC_RANDOM_REQUIRES_SEED)"
            )
        
        # Validate seed type if provided
        if self.seed is not None and not isinstance(self.seed, int):
            raise TypeError(
                f"SamplingStrategy.seed must be int, got {type(self.seed).__name__}"
            )


@dataclass
class NumericCheckSpec:
    """
    GC-9: Numeric check specification.
    
    Defines a numeric property check with:
    - Property being tested and domain constraints
    - Sampling strategy (deterministic + optional random/edge)
    - Tolerances for comparison
    - Strong agreement parameters
    - Solver settings for evaluation
    - Payload reference to log data
    
    All fields are REQUIRED except edge_case_points.
    """
    check_id: str
    property_tested: str
    domain_constraints: str
    sampling_strategy: SamplingStrategy
    tolerance_abs: float
    tolerance_rel: float
    strong_params: StrongParams
    solver_settings: dict
    payload_ref: str
    
    def __post_init__(self):
        # Validate check_id
        if not self.check_id or not isinstance(self.check_id, str):
            raise ValueError("NumericCheckSpec.check_id must be non-empty string")
        
        # GC-9: property_tested REQUIRED non-empty
        if not self.property_tested or not isinstance(self.property_tested, str):
            raise ValueError(
                "NumericCheckSpec.property_tested must be non-empty string (GC-9: NUMERIC_SPEC_MISSING_PROPERTY)"
            )
        
        # GC-9: domain_constraints REQUIRED non-empty
        if not self.domain_constraints or not isinstance(self.domain_constraints, str):
            raise ValueError(
                "NumericCheckSpec.domain_constraints must be non-empty string (GC-9: NUMERIC_SPEC_MISSING_DOMAIN)"
            )
        
        # GC-9: tolerances must be finite and >= 0
        import math
        if not isinstance(self.tolerance_abs, (int, float)):
            raise TypeError(
                f"NumericCheckSpec.tolerance_abs must be numeric, got {type(self.tolerance_abs).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
            )
        if not isinstance(self.tolerance_rel, (int, float)):
            raise TypeError(
                f"NumericCheckSpec.tolerance_rel must be numeric, got {type(self.tolerance_rel).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
            )
        
        if not math.isfinite(self.tolerance_abs):
            raise ValueError(
                f"NumericCheckSpec.tolerance_abs must be finite, got {self.tolerance_abs} (GC-9: NUMERIC_NONFINITE_TOLERANCE)"
            )
        if not math.isfinite(self.tolerance_rel):
            raise ValueError(
                f"NumericCheckSpec.tolerance_rel must be finite, got {self.tolerance_rel} (GC-9: NUMERIC_NONFINITE_TOLERANCE)"
            )
        if self.tolerance_abs < 0:
            raise ValueError(
                f"NumericCheckSpec.tolerance_abs must be >= 0, got {self.tolerance_abs} (GC-9: NUMERIC_SPEC_TOLERANCE_INVALID)"
            )
        if self.tolerance_rel < 0:
            raise ValueError(
                f"NumericCheckSpec.tolerance_rel must be >= 0, got {self.tolerance_rel} (GC-9: NUMERIC_SPEC_TOLERANCE_INVALID)"
            )
        
        # GC-9: solver_settings REQUIRED (dict, may be empty)
        if self.solver_settings is None:
            raise ValueError(
                "NumericCheckSpec.solver_settings is required (GC-9: NUMERIC_SPEC_SOLVER_SETTINGS_MISSING)"
            )
        if not isinstance(self.solver_settings, dict):
            raise TypeError(
                f"NumericCheckSpec.solver_settings must be dict, got {type(self.solver_settings).__name__}"
            )
        
        # GC-9: payload_ref REQUIRED non-empty
        if not self.payload_ref or not isinstance(self.payload_ref, str):
            raise ValueError(
                "NumericCheckSpec.payload_ref must be non-empty string (GC-9: NUMERIC_SPEC_PAYLOAD_REF_MISSING)"
            )


@dataclass
class NumericCheckResult:
    """
    GC-9: Numeric check result.
    
    Contains:
    - status: pass/fail/indeterminate
    - counts: pass_count, fail_count, indeterminate_count
    - strong_agreement: COMPUTED ONLY (never trusted from wire)
    
    Counts must match per_point_status tallies in log payload.
    strong_agreement is computed based on deterministic + random passes and strong_params.
    """
    status: NumericCheckStatus
    pass_count: int
    fail_count: int
    indeterminate_count: int
    strong_agreement: bool
    
    def __post_init__(self):
        # Validate status is enum
        if not isinstance(self.status, NumericCheckStatus):
            raise TypeError(
                f"NumericCheckResult.status must be NumericCheckStatus enum, got {type(self.status).__name__}"
            )
        
        # Validate counts are non-negative integers
        for field_name in ['pass_count', 'fail_count', 'indeterminate_count']:
            value = getattr(self, field_name)
            if not isinstance(value, int):
                raise TypeError(
                    f"NumericCheckResult.{field_name} must be int, got {type(value).__name__}"
                )
            if value < 0:
                raise ValueError(
                    f"NumericCheckResult.{field_name} must be >= 0, got {value}"
                )
        
        # Validate strong_agreement is bool
        if not isinstance(self.strong_agreement, bool):
            raise TypeError(
                f"NumericCheckResult.strong_agreement must be bool, got {type(self.strong_agreement).__name__}"
            )


@dataclass
class LogPayload:
    """
    GC-9: Log payload referenced by payload_ref.
    
    Contains replayable data:
    - points: all sampled points (deterministic + edge + random)
    - outputs: evaluation results aligned with points
    - per_point_status: pass/fail/indeterminate for each point
    - point_kind: "deterministic", "edge", or "random" for each point (GC-9.1)
    - seed: random seed if random_points_count > 0
    - solver_settings: solver configuration used
    - tolerances: abs/rel tolerances used
    - runtime_notes: optional notes for NaN/timeout/etc.
    
    All lists must have aligned lengths.
    point_kind allows robust random_pass_count computation (GC-9.1 freeze patch).
    """
    points: list[Point]
    outputs: list  # Type depends on property (float, vector, etc.)
    per_point_status: list[str]  # "pass", "fail", or "indeterminate"
    point_kind: list[str]  # "deterministic", "edge", or "random" (GC-9.1)
    seed: Optional[int]
    solver_settings: dict
    tolerance_abs: float
    tolerance_rel: float
    runtime_notes: Optional[str] = None
    
    def __post_init__(self):
        # Validate aligned lengths (including point_kind)
        if len(self.points) != len(self.outputs):
            raise ValueError(
                f"LogPayload: points and outputs must have same length, got {len(self.points)} vs {len(self.outputs)} (GC-9: NUMERIC_LOG_LENGTH_MISMATCH)"
            )
        if len(self.points) != len(self.per_point_status):
            raise ValueError(
                f"LogPayload: points and per_point_status must have same length, got {len(self.points)} vs {len(self.per_point_status)} (GC-9: NUMERIC_LOG_LENGTH_MISMATCH)"
            )
        if len(self.points) != len(self.point_kind):
            raise ValueError(
                f"LogPayload: points and point_kind must have same length, got {len(self.points)} vs {len(self.point_kind)} (GC-9.2: NUMERIC_LOG_KIND_LENGTH_MISMATCH)"
            )
        
        # GC-9.2: Validate outputs are numeric (reject string "NaN"/"Inf")
        for i, output in enumerate(self.outputs):
            if isinstance(output, str):
                # Reject string outputs (especially "NaN", "Inf", etc.)
                raise TypeError(
                    f"LogPayload.outputs[{i}] must be numeric, got string '{output}' (GC-9.2: NUMERIC_OUTPUT_WRONG_TYPE)"
                )
        
        # Validate per_point_status values are strict enum
        valid_statuses = {"pass", "fail", "indeterminate"}
        for i, status in enumerate(self.per_point_status):
            if status not in valid_statuses:
                raise ValueError(
                    f"LogPayload.per_point_status[{i}] must be 'pass', 'fail', or 'indeterminate', got '{status}'"
                )
        
        # Validate point_kind values are strict enum (GC-9.1)
        valid_kinds = {"deterministic", "edge", "random"}
        for i, kind in enumerate(self.point_kind):
            if kind not in valid_kinds:
                raise ValueError(
                    f"LogPayload.point_kind[{i}] must be 'deterministic', 'edge', or 'random', got '{kind}' (GC-9.1: NUMERIC_LOG_MISSING_FIELDS)"
                )
