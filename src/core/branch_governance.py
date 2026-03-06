"""
GC-10 Branch Governance Schemas and Wire-Boundary Parsers.

Defines policy, branch summary, and event log schemas for bounded,
deterministic branch governance.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import math


ALLOWED_PRUNE_STRATEGY = "lowest_score_first"
ALLOWED_MERGE_RULES = ["CAS_EQUIV", "STRONG_NUMERIC_AGREEMENT"]
ALLOWED_TIE_BREAK = ["failed_checks", "cost", "branch_id"]


def _ensure_nonnegative_finite_float(value: Any, field_name: str, error_category: str) -> float:
    """Parse numeric value as finite non-negative float for deterministic validation."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{field_name} must be numeric, got {type(value).__name__} "
            f"(GC-10: {error_category})"
        )
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(
            f"{field_name} must be finite, got {value} "
            f"(GC-10: {error_category})"
        )
    if numeric_value < 0:
        raise ValueError(
            f"{field_name} must be >= 0, got {value} "
            f"(GC-10: {error_category})"
        )
    return numeric_value


def _ensure_positive_finite_float(value: Any, field_name: str, error_category: str) -> float:
    """Parse numeric value as finite positive float for deterministic validation."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{field_name} must be numeric, got {type(value).__name__} "
            f"(GC-10: {error_category})"
        )
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(
            f"{field_name} must be finite, got {value} "
            f"(GC-10: {error_category})"
        )
    if numeric_value <= 0:
        raise ValueError(
            f"{field_name} must be > 0, got {value} "
            f"(GC-10: {error_category})"
        )
    return numeric_value


UNICODE_INVISIBLES = {
    "\u200b",  # ZWSP
    "\u00a0",  # NBSP
    "\ufeff",  # BOM
    "\u2060",  # WJ
    "\u200c",  # ZWNJ
    "\u200d",  # ZWJ
}


def parse_branch_id(wire: Any) -> str:
    """
    Parse branch_id as strict token (reject-only posture, no trimming).

    Rules:
    - Must be string
    - Must be non-empty
    - Must be ASCII-only
    - No leading/trailing whitespace
    - No unicode invisible characters
    """
    if wire is None:
        raise ValueError(
            "Invalid branch_id: None/null (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
        )
    if not isinstance(wire, str):
        raise TypeError(
            f"Invalid branch_id: must be string, got {type(wire).__name__} (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
        )
    if wire == "":
        raise ValueError(
            "Invalid branch_id: empty string (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
        )
    if wire != wire.strip():
        raise ValueError(
            "Invalid branch_id: leading/trailing whitespace not allowed (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
        )
    for invisible in UNICODE_INVISIBLES:
        if invisible in wire:
            raise ValueError(
                "Invalid branch_id: unicode invisible character not allowed "
                f"(GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
            )
    try:
        wire.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "Invalid branch_id: non-ASCII characters not allowed (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
        )
    return wire


@dataclass
class BranchWeights:
    """GC-10 policy weights for normalized score computation."""

    w1: float
    w2: float
    w3: float
    w4: float

    def __post_init__(self) -> None:
        for field_name in ("w1", "w2", "w3", "w4"):
            numeric_value = _ensure_nonnegative_finite_float(
                value=getattr(self, field_name),
                field_name=field_name,
                error_category="BRANCH_POLICY_INVALID_WEIGHT",
            )
            setattr(self, field_name, numeric_value)


@dataclass
class BranchNormalization:
    """GC-10 normalization constants for score stability."""

    K: float  # failed_checks normalization divisor (>0)
    C: float  # cost normalization divisor (>0)

    def __post_init__(self) -> None:
        for field_name in ("K", "C"):
            numeric_value = _ensure_positive_finite_float(
                value=getattr(self, field_name),
                field_name=field_name,
                error_category="BRANCH_POLICY_INVALID_NORMALIZATION",
            )
            setattr(self, field_name, numeric_value)


@dataclass
class BranchPolicy:
    """
    GC-10 governance policy.

    Frozen v0 contract:
    - prune_strategy: lowest_score_first
    - merge_rules: [CAS_EQUIV, STRONG_NUMERIC_AGREEMENT]
    - tie_break: [failed_checks, cost, branch_id]
    """

    max_active_branches: int
    weights: BranchWeights
    normalization: BranchNormalization
    prune_strategy: str
    merge_rules: list[str]
    tie_break: list[str]

    def __post_init__(self) -> None:
        if not isinstance(self.max_active_branches, int) or isinstance(self.max_active_branches, bool):
            raise TypeError(
                "max_active_branches must be int "
                "(GC-10: BRANCH_POLICY_INVALID_MAX_ACTIVE)"
            )
        if self.max_active_branches <= 0:
            raise ValueError(
                f"max_active_branches must be > 0, got {self.max_active_branches} "
                "(GC-10: BRANCH_POLICY_INVALID_MAX_ACTIVE)"
            )

        if not isinstance(self.weights, BranchWeights):
            raise TypeError(
                f"weights must be BranchWeights, got {type(self.weights).__name__} "
                "(GC-10: BRANCH_POLICY_INVALID_WEIGHT)"
            )

        if not isinstance(self.normalization, BranchNormalization):
            raise TypeError(
                "normalization must be BranchNormalization "
                f"(got {type(self.normalization).__name__}) "
                "(GC-10: BRANCH_POLICY_INVALID_NORMALIZATION)"
            )

        if self.prune_strategy != ALLOWED_PRUNE_STRATEGY:
            raise ValueError(
                f"prune_strategy must be '{ALLOWED_PRUNE_STRATEGY}', got '{self.prune_strategy}' "
                "(GC-10: BRANCH_POLICY_INVALID_PRUNE_STRATEGY)"
            )

        if self.merge_rules != ALLOWED_MERGE_RULES:
            raise ValueError(
                f"merge_rules must be exactly {ALLOWED_MERGE_RULES}, got {self.merge_rules} "
                "(GC-10: BRANCH_POLICY_INVALID_MERGE_RULE)"
            )

        if self.tie_break != ALLOWED_TIE_BREAK:
            raise ValueError(
                f"tie_break must be exactly {ALLOWED_TIE_BREAK}, got {self.tie_break} "
                "(GC-10: BRANCH_POLICY_INVALID_TIE_BREAK)"
            )


@dataclass
class BranchStateSummary:
    """
    GC-10 branch state summary.

    Computed-only fields (never trusted from wire):
    - failed_checks_norm
    - cost_norm
    - score
    """

    branch_id: str
    coverage: float
    sanity_pass_rate: float
    failed_checks: int
    cost: float
    created_seq: int
    failed_checks_norm: float = field(init=False, default=0.0)
    cost_norm: float = field(init=False, default=0.0)
    score: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.branch_id = parse_branch_id(self.branch_id)

        for field_name in ("coverage", "sanity_pass_rate"):
            raw_value = getattr(self, field_name)
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise TypeError(
                    f"{field_name} must be numeric, got {type(raw_value).__name__} "
                    "(GC-10: BRANCH_SUMMARY_INVALID_RANGE)"
                )
            numeric_value = float(raw_value)
            if not math.isfinite(numeric_value):
                raise ValueError(
                    f"{field_name} must be finite, got {raw_value} "
                    "(GC-10: BRANCH_SUMMARY_INVALID_RANGE)"
                )
            if not (0.0 <= numeric_value <= 1.0):
                raise ValueError(
                    f"{field_name} must be in [0,1], got {raw_value} "
                    "(GC-10: BRANCH_SUMMARY_INVALID_RANGE)"
                )
            setattr(self, field_name, numeric_value)

        if not isinstance(self.failed_checks, int) or isinstance(self.failed_checks, bool):
            raise TypeError(
                f"failed_checks must be int, got {type(self.failed_checks).__name__} "
                "(GC-10: BRANCH_SUMMARY_INVALID_FAILED_CHECKS)"
            )
        if self.failed_checks < 0:
            raise ValueError(
                f"failed_checks must be >= 0, got {self.failed_checks} "
                "(GC-10: BRANCH_SUMMARY_INVALID_FAILED_CHECKS)"
            )

        self.cost = _ensure_nonnegative_finite_float(
            value=self.cost,
            field_name="cost",
            error_category="BRANCH_SUMMARY_INVALID_COST",
        )

        if not isinstance(self.created_seq, int) or isinstance(self.created_seq, bool):
            raise TypeError(
                "created_seq must be int (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
            )
        if self.created_seq < 0:
            raise ValueError(
                "created_seq must be >= 0 (GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
            )


class BranchEventType(Enum):
    """GC-10 governance event types."""

    BRANCH_CREATED = "BRANCH_CREATED"
    BRANCH_PRUNED = "BRANCH_PRUNED"
    BRANCH_MERGED = "BRANCH_MERGED"


@dataclass
class BranchEventLogEntry:
    """GC-10 governance decision audit log entry."""

    event_id: str
    event_type: BranchEventType
    branch_ids: list[str]
    snapshot: dict[str, Any]
    reason: dict[str, Any]
    created_seq: int

    def __post_init__(self) -> None:
        if self.event_id is None or not isinstance(self.event_id, str) or self.event_id == "":
            raise ValueError("event_id must be non-empty string")
        if not isinstance(self.event_type, BranchEventType):
            raise TypeError("event_type must be BranchEventType")
        if not isinstance(self.branch_ids, list) or len(self.branch_ids) == 0:
            raise ValueError("branch_ids must be non-empty list")
        for branch_id in self.branch_ids:
            parse_branch_id(branch_id)
        if not isinstance(self.snapshot, dict):
            raise TypeError("snapshot must be dict")
        if not isinstance(self.reason, dict):
            raise TypeError("reason must be dict")
        if not isinstance(self.created_seq, int) or isinstance(self.created_seq, bool):
            raise TypeError("created_seq must be int")
        if self.created_seq < 0:
            raise ValueError("created_seq must be >= 0")


def parse_branch_policy(wire: dict[str, Any]) -> BranchPolicy:
    """Parse BranchPolicy at wire boundary with deterministic categories."""
    if not isinstance(wire, dict):
        raise TypeError(
            "BranchPolicy wire payload must be dict "
            "(GC-10: BRANCH_POLICY_INVALID_MAX_ACTIVE)"
        )

    weights_wire = wire.get("weights")
    if not isinstance(weights_wire, dict):
        raise ValueError(
            "weights must be object with w1,w2,w3,w4 "
            "(GC-10: BRANCH_POLICY_INVALID_WEIGHT)"
        )

    normalization_wire = wire.get("normalization")
    if not isinstance(normalization_wire, dict):
        raise ValueError(
            "normalization must be object with K,C "
            "(GC-10: BRANCH_POLICY_INVALID_NORMALIZATION)"
        )

    weights = BranchWeights(
        w1=weights_wire.get("w1"),
        w2=weights_wire.get("w2"),
        w3=weights_wire.get("w3"),
        w4=weights_wire.get("w4"),
    )
    normalization = BranchNormalization(
        K=normalization_wire.get("K"),
        C=normalization_wire.get("C"),
    )

    return BranchPolicy(
        max_active_branches=wire.get("max_active_branches"),
        weights=weights,
        normalization=normalization,
        prune_strategy=wire.get("prune_strategy"),
        merge_rules=wire.get("merge_rules"),
        tie_break=wire.get("tie_break"),
    )


def parse_branch_state_summary(wire: dict[str, Any]) -> BranchStateSummary:
    """Parse BranchStateSummary at wire boundary (computed fields ignored from wire)."""
    if not isinstance(wire, dict):
        raise TypeError(
            "BranchStateSummary wire payload must be dict "
            "(GC-10: BRANCH_SUMMARY_INVALID_BRANCH_ID)"
        )

    return BranchStateSummary(
        branch_id=wire.get("branch_id"),
        coverage=wire.get("coverage"),
        sanity_pass_rate=wire.get("sanity_pass_rate"),
        failed_checks=wire.get("failed_checks"),
        cost=wire.get("cost"),
        created_seq=wire.get("created_seq"),
    )
