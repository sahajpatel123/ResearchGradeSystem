"""
GC-9 Numeric Agreement Contract - Wire Boundary Parsers

Strict parsers for numeric check spec/result with fail-closed validation.
No trimming, reject NaN/Infinity, strict types, strict enums.
"""

from typing import Any, Optional
import math
from src.core.numeric_check import (
    NumericCheckSpec,
    NumericCheckResult,
    NumericCheckStatus,
    SamplingStrategy,
    StrongParams,
    LogPayload,
    Point,
)


def parse_float_finite_nonneg(wire: Any, field_name: str) -> float:
    """
    Parse a finite non-negative float at wire boundary.
    
    Rejects:
    - Non-numeric types
    - NaN
    - Infinity
    - Negative values
    
    Args:
        wire: Value from wire
        field_name: Field name for error messages
    
    Returns:
        Validated float
    
    Raises:
        TypeError: If not numeric
        ValueError: If NaN, Infinity, or negative
    """
    if not isinstance(wire, (int, float)):
        raise TypeError(
            f"Invalid {field_name}: must be numeric, got {type(wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    if not math.isfinite(wire):
        raise ValueError(
            f"Invalid {field_name}: must be finite, got {wire} (GC-9: NUMERIC_NONFINITE_TOLERANCE)"
        )
    
    if wire < 0:
        raise ValueError(
            f"Invalid {field_name}: must be >= 0, got {wire} (GC-9: NUMERIC_SPEC_TOLERANCE_INVALID)"
        )
    
    return float(wire)


def parse_int_nonneg(wire: Any, field_name: str) -> int:
    """
    Parse a non-negative integer at wire boundary.
    
    Rejects:
    - Non-integer types (including floats)
    - Negative values
    
    Args:
        wire: Value from wire
        field_name: Field name for error messages
    
    Returns:
        Validated int
    
    Raises:
        TypeError: If not int
        ValueError: If negative
    """
    if not isinstance(wire, int) or isinstance(wire, bool):
        raise TypeError(
            f"Invalid {field_name}: must be int, got {type(wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    if wire < 0:
        raise ValueError(
            f"Invalid {field_name}: must be >= 0, got {wire}"
        )
    
    return wire


def parse_payload_ref(wire: Any) -> str:
    """
    Parse payload_ref at wire boundary (strict token, no trimming).
    
    Rejects:
    - None/null
    - Non-string
    - Empty string
    - Whitespace-only
    - Leading/trailing whitespace
    
    Args:
        wire: Value from wire
    
    Returns:
        Validated payload_ref string
    
    Raises:
        TypeError: If not string
        ValueError: If empty or has whitespace variants
    """
    if wire is None:
        raise ValueError(
            "Invalid payload_ref: None/null (GC-9: NUMERIC_SPEC_PAYLOAD_REF_MISSING)"
        )
    
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid payload_ref: must be string, got {type(wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    if wire == "":
        raise ValueError(
            "Invalid payload_ref: empty string (GC-9: NUMERIC_SPEC_PAYLOAD_REF_MISSING)"
        )
    
    # Reject whitespace-only
    if not wire.strip():
        raise ValueError(
            "Invalid payload_ref: whitespace-only (GC-9: NUMERIC_SPEC_PAYLOAD_REF_MISSING)"
        )
    
    # Reject leading/trailing whitespace (no trimming)
    if wire != wire.strip():
        raise ValueError(
            "Invalid payload_ref: has leading/trailing whitespace (GC-9: NUMERIC_SPEC_PAYLOAD_REF_MISSING)"
        )
    
    return wire


def parse_point(wire: Any) -> Point:
    """
    Parse a Point (dict[str, float]) at wire boundary.
    
    Rejects:
    - Non-dict
    - Empty dict
    - Non-string keys
    - Non-numeric values
    - NaN/Infinity values
    
    Args:
        wire: Value from wire
    
    Returns:
        Validated Point
    
    Raises:
        TypeError: If not dict or wrong value types
        ValueError: If empty or has NaN/Infinity
    """
    if not isinstance(wire, dict):
        raise TypeError(
            f"Invalid point: must be dict, got {type(wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    if not wire:
        raise ValueError(
            "Invalid point: empty dict (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    point: Point = {}
    for key, value in wire.items():
        if not isinstance(key, str):
            raise TypeError(
                f"Invalid point key: must be string, got {type(key).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
            )
        
        if not isinstance(value, (int, float)):
            raise TypeError(
                f"Invalid point value for '{key}': must be numeric, got {type(value).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
            )
        
        if not math.isfinite(value):
            raise ValueError(
                f"Invalid point value for '{key}': must be finite, got {value} (GC-9: NUMERIC_NONFINITE_TOLERANCE)"
            )
        
        point[key] = float(value)
    
    return point


def parse_seed_if_needed(random_points_count: int, seed_wire: Any) -> Optional[int]:
    """
    Parse seed if random_points_count > 0.
    
    Args:
        random_points_count: Number of random points
        seed_wire: Seed value from wire
    
    Returns:
        Validated seed or None
    
    Raises:
        ValueError: If seed required but missing
        TypeError: If seed wrong type
    """
    if random_points_count > 0:
        if seed_wire is None:
            raise ValueError(
                "seed is required when random_points_count > 0 (GC-9: NUMERIC_SPEC_RANDOM_REQUIRES_SEED)"
            )
        
        if not isinstance(seed_wire, int) or isinstance(seed_wire, bool):
            raise TypeError(
                f"Invalid seed: must be int, got {type(seed_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
            )
        
        return seed_wire
    
    return None


def parse_sampling_strategy(wire: dict) -> SamplingStrategy:
    """
    Parse SamplingStrategy at wire boundary.
    
    Args:
        wire: Sampling strategy dict from wire
    
    Returns:
        Validated SamplingStrategy
    
    Raises:
        Various errors for invalid data
    """
    # Parse deterministic_points (REQUIRED NON-EMPTY)
    deterministic_wire = wire.get("deterministic_points")
    if deterministic_wire is None:
        raise ValueError(
            "deterministic_points is required (GC-9: NUMERIC_SPEC_DETERMINISTIC_POINTS_EMPTY)"
        )
    
    if not isinstance(deterministic_wire, list):
        raise TypeError(
            f"deterministic_points must be list, got {type(deterministic_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    if len(deterministic_wire) == 0:
        raise ValueError(
            "deterministic_points cannot be empty (GC-9: NUMERIC_SPEC_DETERMINISTIC_POINTS_EMPTY)"
        )
    
    deterministic_points = [parse_point(p) for p in deterministic_wire]
    
    # Parse edge_case_points (optional)
    edge_case_wire = wire.get("edge_case_points", [])
    if not isinstance(edge_case_wire, list):
        raise TypeError(
            f"edge_case_points must be list, got {type(edge_case_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    edge_case_points = [parse_point(p) for p in edge_case_wire]
    
    # Parse random_points_count
    random_points_count = parse_int_nonneg(wire.get("random_points_count", 0), "random_points_count")
    
    # Parse seed if needed
    seed = parse_seed_if_needed(random_points_count, wire.get("seed"))
    
    return SamplingStrategy(
        deterministic_points=deterministic_points,
        edge_case_points=edge_case_points,
        random_points_count=random_points_count,
        seed=seed
    )


def parse_strong_params(wire: dict) -> StrongParams:
    """
    Parse StrongParams at wire boundary.
    
    Args:
        wire: Strong params dict from wire
    
    Returns:
        Validated StrongParams with defaults N=20, M=0
    
    Raises:
        TypeError/ValueError for invalid data
    """
    N = wire.get("N", 20)
    M = wire.get("M", 0)
    
    if not isinstance(N, int) or isinstance(N, bool):
        raise TypeError(
            f"Invalid strong_params.N: must be int, got {type(N).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    if not isinstance(M, int) or isinstance(M, bool):
        raise TypeError(
            f"Invalid strong_params.M: must be int, got {type(M).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    return StrongParams(N=N, M=M)


def parse_numeric_check_spec(wire: dict) -> NumericCheckSpec:
    """
    Parse NumericCheckSpec at wire boundary.
    
    Strict validation:
    - All required fields must be present
    - No trimming normalization
    - Reject NaN/Infinity tolerances
    - Reject wrong types
    - deterministic_points must be non-empty
    
    Args:
        wire: Spec dict from wire
    
    Returns:
        Validated NumericCheckSpec
    
    Raises:
        Various errors for invalid data
    """
    # Parse check_id
    check_id = wire.get("check_id")
    if not check_id or not isinstance(check_id, str):
        raise ValueError("check_id is required and must be non-empty string")
    
    # Parse property_tested (REQUIRED)
    property_tested = wire.get("property_tested")
    if not property_tested or not isinstance(property_tested, str):
        raise ValueError(
            "property_tested is required and must be non-empty string (GC-9: NUMERIC_SPEC_MISSING_PROPERTY)"
        )
    
    # Parse domain_constraints (REQUIRED)
    domain_constraints = wire.get("domain_constraints")
    if not domain_constraints or not isinstance(domain_constraints, str):
        raise ValueError(
            "domain_constraints is required and must be non-empty string (GC-9: NUMERIC_SPEC_MISSING_DOMAIN)"
        )
    
    # Parse sampling_strategy
    sampling_strategy_wire = wire.get("sampling_strategy")
    if not isinstance(sampling_strategy_wire, dict):
        raise TypeError(
            f"sampling_strategy must be dict, got {type(sampling_strategy_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    sampling_strategy = parse_sampling_strategy(sampling_strategy_wire)
    
    # Parse tolerances
    tolerance_abs = parse_float_finite_nonneg(wire.get("tolerance_abs"), "tolerance_abs")
    tolerance_rel = parse_float_finite_nonneg(wire.get("tolerance_rel"), "tolerance_rel")
    
    # Parse strong_params
    strong_params_wire = wire.get("strong_params", {})
    if not isinstance(strong_params_wire, dict):
        raise TypeError(
            f"strong_params must be dict, got {type(strong_params_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    strong_params = parse_strong_params(strong_params_wire)
    
    # Parse solver_settings (REQUIRED, may be empty dict)
    solver_settings = wire.get("solver_settings")
    if solver_settings is None:
        raise ValueError(
            "solver_settings is required (GC-9: NUMERIC_SPEC_SOLVER_SETTINGS_MISSING)"
        )
    if not isinstance(solver_settings, dict):
        raise TypeError(
            f"solver_settings must be dict, got {type(solver_settings).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    # Parse payload_ref
    payload_ref = parse_payload_ref(wire.get("payload_ref"))
    
    return NumericCheckSpec(
        check_id=check_id,
        property_tested=property_tested,
        domain_constraints=domain_constraints,
        sampling_strategy=sampling_strategy,
        tolerance_abs=tolerance_abs,
        tolerance_rel=tolerance_rel,
        strong_params=strong_params,
        solver_settings=solver_settings,
        payload_ref=payload_ref
    )


def parse_numeric_check_result(wire: dict) -> NumericCheckResult:
    """
    Parse NumericCheckResult at wire boundary.
    
    Note: strong_agreement from wire is IGNORED and will be recomputed.
    
    Args:
        wire: Result dict from wire
    
    Returns:
        NumericCheckResult (strong_agreement will be recomputed by validator)
    
    Raises:
        Various errors for invalid data
    """
    # Parse status (strict enum)
    status_wire = wire.get("status")
    if not isinstance(status_wire, str):
        raise TypeError(
            f"Invalid status: must be string, got {type(status_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    try:
        status = NumericCheckStatus(status_wire)
    except ValueError:
        raise ValueError(
            f"Invalid status: must be 'pass', 'fail', or 'indeterminate', got '{status_wire}' (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    # Parse counts
    pass_count = parse_int_nonneg(wire.get("pass_count"), "pass_count")
    fail_count = parse_int_nonneg(wire.get("fail_count"), "fail_count")
    indeterminate_count = parse_int_nonneg(wire.get("indeterminate_count"), "indeterminate_count")
    
    # Parse strong_agreement (will be recomputed, but validate type)
    strong_agreement_wire = wire.get("strong_agreement")
    if not isinstance(strong_agreement_wire, bool):
        raise TypeError(
            f"Invalid strong_agreement: must be bool, got {type(strong_agreement_wire).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    # Note: We accept the wire value here but validators will recompute and verify
    return NumericCheckResult(
        status=status,
        pass_count=pass_count,
        fail_count=fail_count,
        indeterminate_count=indeterminate_count,
        strong_agreement=strong_agreement_wire  # Will be verified/recomputed
    )


def parse_log_payload(wire: dict) -> LogPayload:
    """
    Parse LogPayload at wire boundary.
    
    GC-9.1: Also parses point_kind field for robust random_pass_count computation.
    
    Args:
        wire: Log payload dict from wire
    
    Returns:
        Validated LogPayload
    
    Raises:
        Various errors for invalid data
    """
    # Parse points
    points_wire = wire.get("points")
    if not isinstance(points_wire, list):
        raise TypeError(
            f"Invalid points: must be list, got {type(points_wire).__name__} (GC-9: NUMERIC_LOG_MISSING_FIELDS)"
        )
    points = [parse_point(p) for p in points_wire]
    
    # Parse outputs (type depends on property, accept any list)
    outputs = wire.get("outputs")
    if not isinstance(outputs, list):
        raise TypeError(
            f"Invalid outputs: must be list, got {type(outputs).__name__} (GC-9: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    # Parse per_point_status
    per_point_status = wire.get("per_point_status")
    if not isinstance(per_point_status, list):
        raise TypeError(
            f"Invalid per_point_status: must be list, got {type(per_point_status).__name__} (GC-9: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    # GC-9.1: Parse point_kind
    point_kind = wire.get("point_kind")
    if point_kind is None:
        raise ValueError(
            "point_kind is required (GC-9.1: NUMERIC_LOG_MISSING_FIELDS)"
        )
    if not isinstance(point_kind, list):
        raise TypeError(
            f"Invalid point_kind: must be list, got {type(point_kind).__name__} (GC-9.1: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    # Validate point_kind values
    valid_kinds = {"deterministic", "edge", "random"}
    for i, kind in enumerate(point_kind):
        if not isinstance(kind, str):
            raise TypeError(
                f"Invalid point_kind[{i}]: must be string, got {type(kind).__name__} (GC-9.1: NUMERIC_WRONG_TYPE)"
            )
        if kind not in valid_kinds:
            raise ValueError(
                f"Invalid point_kind[{i}]: must be 'deterministic', 'edge', or 'random', got '{kind}' (GC-9.1: NUMERIC_WRONG_TYPE)"
            )
    
    # Parse seed (optional)
    seed = wire.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise TypeError(
            f"Invalid seed: must be int, got {type(seed).__name__} (GC-9: NUMERIC_WRONG_TYPE)"
        )
    
    # Parse solver_settings
    solver_settings = wire.get("solver_settings")
    if not isinstance(solver_settings, dict):
        raise TypeError(
            f"Invalid solver_settings: must be dict, got {type(solver_settings).__name__} (GC-9: NUMERIC_LOG_MISSING_FIELDS)"
        )
    
    # Parse tolerances
    tolerance_abs = parse_float_finite_nonneg(wire.get("tolerance_abs"), "tolerance_abs")
    tolerance_rel = parse_float_finite_nonneg(wire.get("tolerance_rel"), "tolerance_rel")
    
    # Parse runtime_notes (optional)
    runtime_notes = wire.get("runtime_notes")
    
    return LogPayload(
        points=points,
        outputs=outputs,
        per_point_status=per_point_status,
        point_kind=point_kind,
        seed=seed,
        solver_settings=solver_settings,
        tolerance_abs=tolerance_abs,
        tolerance_rel=tolerance_rel,
        runtime_notes=runtime_notes
    )
