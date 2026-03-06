"""
GC-10 Branch Governance Computation and Validation.

Implements deterministic branch score computation, prune ranking,
cap enforcement, merge eligibility under objective proofs, and
audit event logging.
"""

from dataclasses import dataclass, field
from typing import Any

from src.core.branch_governance import (
    ALLOWED_MERGE_RULES,
    ALLOWED_PRUNE_STRATEGY,
    BranchEventLogEntry,
    BranchEventType,
    BranchPolicy,
    BranchStateSummary,
    parse_branch_id,
)


def compute_branch_score(summary: BranchStateSummary, policy: BranchPolicy) -> float:
    """
    Compute GC-10 normalized branch score (computed-only, never trusted from wire).

    Frozen formula:
      score = w1*coverage + w2*sanity_pass_rate - w3*failed_checks_norm - w4*cost_norm

      failed_checks_norm = min(1, failed_checks / K), K > 0
      cost_norm = min(1, cost / C), C > 0

    coverage and sanity_pass_rate are validated in [0,1] by BranchStateSummary.
    """
    failed_checks_norm = min(1.0, summary.failed_checks / policy.normalization.K)
    cost_norm = min(1.0, summary.cost / policy.normalization.C)

    score = (
        policy.weights.w1 * summary.coverage
        + policy.weights.w2 * summary.sanity_pass_rate
        - policy.weights.w3 * failed_checks_norm
        - policy.weights.w4 * cost_norm
    )

    summary.failed_checks_norm = failed_checks_norm
    summary.cost_norm = cost_norm
    summary.score = float(score)

    return summary.score


def _branch_id_desc_sort_key(branch_id: str) -> tuple[int, ...]:
    """
    Deterministic descending sort key for lexicographic branch_id ordering.

    Winner prefers smaller branch_id. Therefore prune prefers larger branch_id
    when all prior criteria tie.
    """
    return tuple(-ord(ch) for ch in branch_id)


def _prune_sort_key(summary: BranchStateSummary) -> tuple[float, int, float, tuple[int, ...]]:
    """
    Frozen prune key (ascending, lowest pruned first):
      (score, -failed_checks, -cost, branch_id_desc)

    Why this key:
    - Prune lowest score first
    - If scores tie, prune MORE failed_checks first (winner prefers fewer)
    - If still tied, prune HIGHER cost first (winner prefers lower)
    - If still tied, prune LARGER branch_id first (winner prefers smaller)
    """
    return (
        summary.score,
        -summary.failed_checks,
        -summary.cost,
        _branch_id_desc_sort_key(summary.branch_id),
    )


def rank_branches_for_prune(
    branches: list[BranchStateSummary],
    policy: BranchPolicy,
) -> list[BranchStateSummary]:
    """
    Rank branches for pruning deterministically.

    Returns branches ordered from worst -> best for prune decisions.
    """
    if policy.prune_strategy != ALLOWED_PRUNE_STRATEGY:
        raise ValueError(
            f"Unsupported prune_strategy '{policy.prune_strategy}' "
            "(GC-10: BRANCH_POLICY_INVALID_PRUNE_STRATEGY)"
        )

    for branch in branches:
        compute_branch_score(branch, policy)

    return sorted(branches, key=_prune_sort_key)


def select_prune_candidates(
    active_branches: list[BranchStateSummary],
    incoming_branch: BranchStateSummary,
    policy: BranchPolicy,
) -> list[str]:
    """
    Enforce max_active_branches cap by deterministically selecting prune candidates.

    Behavior:
    - Consider active + incoming
    - If count <= cap, no pruning
    - Else prune exactly count-cap branches by frozen prune order
    """
    candidates = list(active_branches) + [incoming_branch]
    overflow = len(candidates) - policy.max_active_branches
    if overflow <= 0:
        return []

    ranked = rank_branches_for_prune(candidates, policy)
    to_prune = ranked[:overflow]
    return [branch.branch_id for branch in to_prune]


def can_merge(
    branch_a: BranchStateSummary | str,
    branch_b: BranchStateSummary | str,
    proof_type: str,
    proof_ref: str,
) -> bool:
    """
    Determine merge eligibility under GC-10 objective proof rules.

    Merge is allowed ONLY if:
    - proof_type in {CAS_EQUIV, STRONG_NUMERIC_AGREEMENT}
    - proof_ref is present (non-empty string)

    Never trust wire booleans such as merge=true.
    """
    if isinstance(branch_a, BranchStateSummary):
        parse_branch_id(branch_a.branch_id)
    else:
        parse_branch_id(branch_a)

    if isinstance(branch_b, BranchStateSummary):
        parse_branch_id(branch_b.branch_id)
    else:
        parse_branch_id(branch_b)

    if proof_type not in ALLOWED_MERGE_RULES:
        raise ValueError(
            f"Unsupported proof_type '{proof_type}' "
            "(GC-10: BRANCH_MERGE_PROOF_TYPE_INVALID)"
        )

    if proof_ref is None or not isinstance(proof_ref, str) or proof_ref == "":
        raise ValueError(
            "proof_ref is required for merge "
            "(GC-10: BRANCH_MERGE_PROOF_REF_MISSING)"
        )

    if proof_ref != proof_ref.strip():
        raise ValueError(
            "proof_ref cannot have leading/trailing whitespace "
            "(GC-10: BRANCH_MERGE_PROOF_REF_MISSING)"
        )

    return True


def _branch_snapshot(branch: BranchStateSummary) -> dict[str, Any]:
    """Create deterministic snapshot payload for audit logs."""
    return {
        "branch_id": branch.branch_id,
        "coverage": branch.coverage,
        "sanity_pass_rate": branch.sanity_pass_rate,
        "failed_checks": branch.failed_checks,
        "cost": branch.cost,
        "failed_checks_norm": branch.failed_checks_norm,
        "cost_norm": branch.cost_norm,
        "score": branch.score,
        "prune_key": {
            "score": branch.score,
            "failed_checks_desc": -branch.failed_checks,
            "cost_desc": -branch.cost,
            "branch_id_desc": list(_branch_id_desc_sort_key(branch.branch_id)),
        },
    }


def _event_id(event_type: BranchEventType, created_seq: int) -> str:
    return f"{event_type.value.lower()}-{created_seq:08d}"


@dataclass
class BranchEventLogger:
    """
    In-memory deterministic event logger for GC-10 governance decisions.

    created_seq is generated internally and monotonically increasing.
    """

    events: list[BranchEventLogEntry] = field(default_factory=list)
    next_created_seq: int = 0

    def _append(
        self,
        event_type: BranchEventType,
        branch_ids: list[str],
        snapshot: dict[str, Any],
        reason: dict[str, Any],
    ) -> BranchEventLogEntry:
        entry = BranchEventLogEntry(
            event_id=_event_id(event_type, self.next_created_seq),
            event_type=event_type,
            branch_ids=branch_ids,
            snapshot=snapshot,
            reason=reason,
            created_seq=self.next_created_seq,
        )
        self.events.append(entry)
        self.next_created_seq += 1
        return entry

    def log_branch_created(
        self,
        branch: BranchStateSummary,
        policy: BranchPolicy,
    ) -> BranchEventLogEntry:
        compute_branch_score(branch, policy)
        return self._append(
            event_type=BranchEventType.BRANCH_CREATED,
            branch_ids=[branch.branch_id],
            snapshot={"branch": _branch_snapshot(branch)},
            reason={"reason": "branch_inserted"},
        )

    def log_branch_pruned(
        self,
        active_branches: list[BranchStateSummary],
        incoming_branch: BranchStateSummary,
        policy: BranchPolicy,
    ) -> BranchEventLogEntry:
        candidates = list(active_branches) + [incoming_branch]
        ranked = rank_branches_for_prune(candidates, policy)
        overflow = max(0, len(candidates) - policy.max_active_branches)
        pruned = ranked[:overflow]

        return self._append(
            event_type=BranchEventType.BRANCH_PRUNED,
            branch_ids=[branch.branch_id for branch in pruned],
            snapshot={
                "policy_max_active_branches": policy.max_active_branches,
                "candidate_count": len(candidates),
                "prune_count": overflow,
                "ranked_candidates": [_branch_snapshot(branch) for branch in ranked],
            },
            reason={
                "prune_strategy": policy.prune_strategy,
                "prune_key": "(score asc, failed_checks desc, cost desc, branch_id desc)",
                "tie_break": policy.tie_break,
            },
        )

    def log_branch_merged(
        self,
        branch_a: BranchStateSummary,
        branch_b: BranchStateSummary,
        proof_type: str,
        proof_ref: str,
    ) -> BranchEventLogEntry:
        can_merge(branch_a, branch_b, proof_type, proof_ref)
        return self._append(
            event_type=BranchEventType.BRANCH_MERGED,
            branch_ids=[branch_a.branch_id, branch_b.branch_id],
            snapshot={
                "branch_a": branch_a.branch_id,
                "branch_b": branch_b.branch_id,
            },
            reason={
                "proof_type": proof_type,
                "proof_ref": proof_ref,
            },
        )
