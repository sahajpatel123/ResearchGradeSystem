"""
GC-10 Branch Governance Tests

Tests for policy validation, score computation, deterministic pruning,
merge eligibility, and event logging.
"""

import pytest
import json
from pathlib import Path

from src.core.branch_governance import (
    ALLOWED_MERGE_RULES,
    ALLOWED_PRUNE_STRATEGY,
    ALLOWED_TIE_BREAK,
    BranchEventLogEntry,
    BranchEventType,
    BranchNormalization,
    BranchPolicy,
    BranchStateSummary,
    BranchWeights,
    parse_branch_id,
    parse_branch_policy,
    parse_branch_state_summary,
)
from src.core.gc10_validators import (
    BranchEventLogger,
    ProofArtifact,
    ProofRegistry,
    ProofStatus,
    can_merge,
    compute_branch_score,
    insert_branch,
    rank_branches_for_prune,
    select_prune_candidates,
)


class TestBranchIdParsing:
    """Test parse_branch_id wire-boundary parser."""

    def test_parse_branch_id_valid(self):
        """GC-10: Valid branch_id passes."""
        assert parse_branch_id("branch-001") == "branch-001"
        assert parse_branch_id("main") == "main"

    def test_parse_branch_id_rejects_none(self):
        """GC-10: Reject None/null branch_id."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_BRANCH_ID"):
            parse_branch_id(None)

    def test_parse_branch_id_rejects_empty(self):
        """GC-10: Reject empty branch_id."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_BRANCH_ID"):
            parse_branch_id("")

    def test_parse_branch_id_rejects_whitespace(self):
        """GC-10: Reject leading/trailing whitespace."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_BRANCH_ID"):
            parse_branch_id(" branch-001")
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_BRANCH_ID"):
            parse_branch_id("branch-001 ")

    def test_parse_branch_id_rejects_non_ascii(self):
        """GC-10: Reject non-ASCII characters."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_BRANCH_ID"):
            parse_branch_id("branch-αβγ")


class TestBranchWeights:
    """Test BranchWeights schema validation."""

    def test_valid_weights(self):
        """GC-10: Valid weights pass."""
        weights = BranchWeights(w1=0.6, w2=0.25, w3=0.1, w4=0.05)
        assert weights.w1 == 0.6
        assert weights.w2 == 0.25

    def test_rejects_negative_weight(self):
        """GC-10: Reject negative weights."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_WEIGHT"):
            BranchWeights(w1=-0.5, w2=0.25, w3=0.1, w4=0.05)

    def test_rejects_nan_weight(self):
        """GC-10: Reject NaN weights."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_WEIGHT"):
            BranchWeights(w1=float("nan"), w2=0.25, w3=0.1, w4=0.05)

    def test_rejects_inf_weight(self):
        """GC-10: Reject Infinity weights."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_WEIGHT"):
            BranchWeights(w1=float("inf"), w2=0.25, w3=0.1, w4=0.05)


class TestBranchNormalization:
    """Test BranchNormalization schema validation."""

    def test_valid_normalization(self):
        """GC-10: Valid normalization passes."""
        norm = BranchNormalization(K=10, C=100.0)
        assert norm.K == 10.0
        assert norm.C == 100.0

    def test_rejects_zero_k(self):
        """GC-10: Reject K <= 0."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_NORMALIZATION"):
            BranchNormalization(K=0, C=100.0)

    def test_rejects_negative_c(self):
        """GC-10: Reject C <= 0."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_NORMALIZATION"):
            BranchNormalization(K=10, C=-50.0)


class TestBranchPolicy:
    """Test BranchPolicy schema validation."""

    def test_valid_policy(self):
        """GC-10: Valid policy passes."""
        policy = BranchPolicy(
            max_active_branches=3,
            weights=BranchWeights(w1=0.6, w2=0.25, w3=0.1, w4=0.05),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )
        assert policy.max_active_branches == 3

    def test_rejects_max_active_zero(self):
        """GC-10: Reject max_active_branches <= 0."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_MAX_ACTIVE"):
            BranchPolicy(
                max_active_branches=0,
                weights=BranchWeights(w1=0.6, w2=0.25, w3=0.1, w4=0.05),
                normalization=BranchNormalization(K=10, C=100.0),
                prune_strategy=ALLOWED_PRUNE_STRATEGY,
                merge_rules=ALLOWED_MERGE_RULES,
                tie_break=ALLOWED_TIE_BREAK,
            )

    def test_rejects_illegal_prune_strategy(self):
        """GC-10: Reject illegal prune_strategy."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_PRUNE_STRATEGY"):
            BranchPolicy(
                max_active_branches=3,
                weights=BranchWeights(w1=0.6, w2=0.25, w3=0.1, w4=0.05),
                normalization=BranchNormalization(K=10, C=100.0),
                prune_strategy="random_prune",
                merge_rules=ALLOWED_MERGE_RULES,
                tie_break=ALLOWED_TIE_BREAK,
            )

    def test_rejects_illegal_merge_rule(self):
        """GC-10: Reject illegal merge_rules."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_MERGE_RULE"):
            BranchPolicy(
                max_active_branches=3,
                weights=BranchWeights(w1=0.6, w2=0.25, w3=0.1, w4=0.05),
                normalization=BranchNormalization(K=10, C=100.0),
                prune_strategy=ALLOWED_PRUNE_STRATEGY,
                merge_rules=["CAS_EQUIV", "HEURISTIC_MATCH"],
                tie_break=ALLOWED_TIE_BREAK,
            )

    def test_rejects_illegal_tie_break(self):
        """GC-10: Reject illegal tie_break order."""
        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_TIE_BREAK"):
            BranchPolicy(
                max_active_branches=3,
                weights=BranchWeights(w1=0.6, w2=0.25, w3=0.1, w4=0.05),
                normalization=BranchNormalization(K=10, C=100.0),
                prune_strategy=ALLOWED_PRUNE_STRATEGY,
                merge_rules=ALLOWED_MERGE_RULES,
                tie_break=["cost", "failed_checks", "branch_id"],
            )


class TestBranchStateSummary:
    """Test BranchStateSummary schema validation."""

    def test_valid_summary(self):
        """GC-10: Valid summary passes."""
        summary = BranchStateSummary(
            branch_id="branch-001",
            coverage=0.8,
            sanity_pass_rate=0.9,
            failed_checks=2,
            cost=50.0,
            created_seq=1,
        )
        assert summary.branch_id == "branch-001"
        assert summary.coverage == 0.8

    def test_rejects_coverage_out_of_range(self):
        """GC-10: Reject coverage outside [0,1]."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_RANGE"):
            BranchStateSummary(
                branch_id="branch-001",
                coverage=1.5,
                sanity_pass_rate=0.9,
                failed_checks=0,
                cost=10.0,
                created_seq=1,
            )

    def test_rejects_negative_failed_checks(self):
        """GC-10: Reject negative failed_checks."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_FAILED_CHECKS"):
            BranchStateSummary(
                branch_id="branch-001",
                coverage=0.8,
                sanity_pass_rate=0.9,
                failed_checks=-1,
                cost=10.0,
                created_seq=1,
            )

    def test_rejects_negative_cost(self):
        """GC-10: Reject negative cost."""
        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_COST"):
            BranchStateSummary(
                branch_id="branch-001",
                coverage=0.8,
                sanity_pass_rate=0.9,
                failed_checks=0,
                cost=-10.0,
                created_seq=1,
            )


class TestScoreComputation:
    """Test compute_branch_score function."""

    def test_score_computation_matches_formula_and_normalization(self):
        """GC-10: Score computed correctly with normalization."""
        policy = BranchPolicy(
            max_active_branches=3,
            weights=BranchWeights(w1=1.0, w2=0.5, w3=0.2, w4=0.1),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )
        summary = BranchStateSummary(
            branch_id="branch-001",
            coverage=0.8,
            sanity_pass_rate=0.6,
            failed_checks=5,
            cost=50.0,
            created_seq=1,
        )

        score = compute_branch_score(summary, policy)

        # Manual calculation:
        # failed_checks_norm = min(1, 5/10) = 0.5
        # cost_norm = min(1, 50/100) = 0.5
        # score = 1.0*0.8 + 0.5*0.6 - 0.2*0.5 - 0.1*0.5
        #       = 0.8 + 0.3 - 0.1 - 0.05 = 0.95
        assert summary.failed_checks_norm == 0.5
        assert summary.cost_norm == 0.5
        assert abs(score - 0.95) < 1e-9

    def test_normalization_caps_at_one(self):
        """GC-10: Normalization caps at 1.0."""
        policy = BranchPolicy(
            max_active_branches=3,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=1.0, w4=1.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )
        summary = BranchStateSummary(
            branch_id="branch-001",
            coverage=0.5,
            sanity_pass_rate=0.5,
            failed_checks=100,  # > K
            cost=500.0,  # > C
            created_seq=1,
        )

        compute_branch_score(summary, policy)

        assert summary.failed_checks_norm == 1.0
        assert summary.cost_norm == 1.0


class TestPruneRanking:
    """Test rank_branches_for_prune function."""

    def test_prune_lowest_score_first_deterministic(self):
        """GC-10: Prune lowest score first."""
        policy = BranchPolicy(
            max_active_branches=2,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )

        branches = [
            BranchStateSummary("branch-high", 0.9, 0.7, 1, 20.0, 1),
            BranchStateSummary("branch-low", 0.4, 0.8, 2, 20.0, 2),
            BranchStateSummary("branch-mid", 0.7, 0.5, 2, 25.0, 3),
        ]

        ranked = rank_branches_for_prune(branches, policy)

        # Scores: high=0.9, low=0.4, mid=0.7
        # Prune order: low (0.4), mid (0.7), high (0.9)
        assert ranked[0].branch_id == "branch-low"
        assert ranked[1].branch_id == "branch-mid"
        assert ranked[2].branch_id == "branch-high"

    def test_prune_tie_break_order_frozen(self):
        """GC-10: Tie-break order is frozen: failed_checks desc, cost desc, branch_id desc."""
        policy = BranchPolicy(
            max_active_branches=2,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )

        # All have same coverage (score), different tie-break criteria
        branches = [
            BranchStateSummary("branch-alpha", 0.5, 0.9, 2, 10.0, 1),
            BranchStateSummary("branch-beta", 0.5, 0.8, 3, 9.0, 2),  # More failed_checks
            BranchStateSummary("branch-gamma", 0.5, 0.7, 2, 15.0, 3),  # Higher cost
            BranchStateSummary("branch-zeta", 0.5, 0.6, 2, 10.0, 4),  # Larger branch_id
        ]

        ranked = rank_branches_for_prune(branches, policy)

        # Tie-break: prune MORE failed_checks first, then HIGHER cost, then LARGER branch_id
        # beta (3 failed) -> gamma (2 failed, 15 cost) -> zeta (2 failed, 10 cost, larger id) -> alpha
        assert ranked[0].branch_id == "branch-beta"
        assert ranked[1].branch_id == "branch-gamma"
        assert ranked[2].branch_id == "branch-zeta"
        assert ranked[3].branch_id == "branch-alpha"

    def test_prune_same_input_same_output_twice(self):
        """GC-10: Same input produces same output (determinism)."""
        policy = BranchPolicy(
            max_active_branches=2,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )

        def make_branches():
            return [
                BranchStateSummary("branch-a", 0.5, 0.9, 2, 10.0, 1),
                BranchStateSummary("branch-b", 0.5, 0.8, 3, 9.0, 2),
                BranchStateSummary("branch-c", 0.5, 0.7, 2, 15.0, 3),
            ]

        ranked1 = rank_branches_for_prune(make_branches(), policy)
        ranked2 = rank_branches_for_prune(make_branches(), policy)

        assert [b.branch_id for b in ranked1] == [b.branch_id for b in ranked2]


class TestBranchCapEnforcement:
    """Test select_prune_candidates function."""

    def test_branch_cap_enforced_on_insert_replace_worst(self):
        """GC-10: Cap enforced, worst branch pruned."""
        policy = BranchPolicy(
            max_active_branches=2,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )

        active = [
            BranchStateSummary("branch-high", 0.9, 0.7, 1, 20.0, 1),
            BranchStateSummary("branch-low", 0.4, 0.8, 2, 20.0, 2),
        ]
        incoming = BranchStateSummary("branch-mid", 0.7, 0.5, 2, 25.0, 3)

        to_prune = select_prune_candidates(active, incoming, policy)

        # 3 branches, cap=2, prune 1 (lowest score = branch-low)
        assert to_prune == ["branch-low"]

    def test_no_prune_when_under_cap(self):
        """GC-10: No pruning when under cap."""
        policy = BranchPolicy(
            max_active_branches=5,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )

        active = [
            BranchStateSummary("branch-a", 0.9, 0.7, 1, 20.0, 1),
            BranchStateSummary("branch-b", 0.4, 0.8, 2, 20.0, 2),
        ]
        incoming = BranchStateSummary("branch-c", 0.7, 0.5, 2, 25.0, 3)

        to_prune = select_prune_candidates(active, incoming, policy)

        assert to_prune == []


class TestMergeEligibility:
    """Test can_merge function."""

    def test_merge_requires_objective_proof_only(self):
        """GC-10: Merge requires CAS_EQUIV or STRONG_NUMERIC_AGREEMENT + proof_ref."""
        branch_a = BranchStateSummary("branch-left", 0.8, 0.9, 1, 30.0, 10)
        branch_b = BranchStateSummary("branch-right", 0.82, 0.88, 1, 32.0, 11)

        # CAS_EQUIV allowed
        assert can_merge(branch_a, branch_b, "CAS_EQUIV", "cas/proofs/proof-001.json")

        # STRONG_NUMERIC_AGREEMENT allowed
        assert can_merge(branch_a, branch_b, "STRONG_NUMERIC_AGREEMENT", "numeric/logs/check-042.json")

    def test_merge_rejects_unsupported_proof_type(self):
        """GC-10: Reject unsupported proof_type."""
        branch_a = BranchStateSummary("branch-left", 0.8, 0.9, 1, 30.0, 10)
        branch_b = BranchStateSummary("branch-right", 0.82, 0.88, 1, 32.0, 11)

        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_TYPE_INVALID"):
            can_merge(branch_a, branch_b, "HEURISTIC_MATCH", "heuristic/proofs/proof-001.json")

    def test_merge_rejects_missing_proof_ref(self):
        """GC-10: Reject missing proof_ref."""
        branch_a = BranchStateSummary("branch-left", 0.8, 0.9, 1, 30.0, 10)
        branch_b = BranchStateSummary("branch-right", 0.82, 0.88, 1, 32.0, 11)

        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_REF_MISSING"):
            can_merge(branch_a, branch_b, "CAS_EQUIV", "")

        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_REF_MISSING"):
            can_merge(branch_a, branch_b, "CAS_EQUIV", None)


class TestEventLogging:
    """Test BranchEventLogger."""

    def test_log_branch_created(self):
        """GC-10: Log branch creation."""
        policy = BranchPolicy(
            max_active_branches=3,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )
        branch = BranchStateSummary("branch-new", 0.8, 0.9, 1, 30.0, 1)

        logger = BranchEventLogger()
        entry = logger.log_branch_created(branch, policy)

        assert entry.event_type == BranchEventType.BRANCH_CREATED
        assert entry.branch_ids == ["branch-new"]
        assert entry.created_seq == 0

    def test_log_branch_pruned(self):
        """GC-10: Log branch pruning with snapshot."""
        policy = BranchPolicy(
            max_active_branches=2,
            weights=BranchWeights(w1=1.0, w2=0.0, w3=0.0, w4=0.0),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy=ALLOWED_PRUNE_STRATEGY,
            merge_rules=ALLOWED_MERGE_RULES,
            tie_break=ALLOWED_TIE_BREAK,
        )
        active = [
            BranchStateSummary("branch-high", 0.9, 0.7, 1, 20.0, 1),
            BranchStateSummary("branch-low", 0.4, 0.8, 2, 20.0, 2),
        ]
        incoming = BranchStateSummary("branch-mid", 0.7, 0.5, 2, 25.0, 3)

        logger = BranchEventLogger()
        entry = logger.log_branch_pruned(active, incoming, policy)

        assert entry.event_type == BranchEventType.BRANCH_PRUNED
        assert "branch-low" in entry.branch_ids
        assert "ranked_candidates" in entry.snapshot

    def test_log_branch_merged(self):
        """GC-10: Log branch merge with proof."""
        branch_a = BranchStateSummary("branch-left", 0.8, 0.9, 1, 30.0, 10)
        branch_b = BranchStateSummary("branch-right", 0.82, 0.88, 1, 32.0, 11)

        logger = BranchEventLogger()
        entry = logger.log_branch_merged(branch_a, branch_b, "CAS_EQUIV", "cas/proofs/proof-001.json")

        assert entry.event_type == BranchEventType.BRANCH_MERGED
        assert entry.branch_ids == ["branch-left", "branch-right"]
        assert entry.reason["proof_type"] == "CAS_EQUIV"
        assert entry.reason["proof_ref"] == "cas/proofs/proof-001.json"


class TestPolicyValidationRejectsInvalidConfigs:
    """Test policy validation rejects invalid configurations."""

    def test_fixture_fail_max_active_zero(self):
        """FAIL fixture: max_active_branches=0."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_max_active_zero.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_MAX_ACTIVE"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_negative_weight(self):
        """FAIL fixture: negative weight."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_negative_weight.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_WEIGHT"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_nan_weight(self):
        """FAIL fixture: NaN weight (string)."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_nan_weight.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(TypeError, match="BRANCH_POLICY_INVALID_WEIGHT"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_missing_normalization(self):
        """FAIL fixture: K=0."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_missing_normalization.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_NORMALIZATION"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_illegal_prune_strategy(self):
        """FAIL fixture: illegal prune_strategy."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_illegal_prune_strategy.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_PRUNE_STRATEGY"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_illegal_merge_rule(self):
        """FAIL fixture: illegal merge_rule."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_illegal_merge_rule.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_MERGE_RULE"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_illegal_tie_break(self):
        """FAIL fixture: illegal tie_break order."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_illegal_tie_break.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_POLICY_INVALID_TIE_BREAK"):
            parse_branch_policy(data["policy"])

    def test_fixture_fail_branch_summary_out_of_range(self):
        """FAIL fixture: coverage out of range."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_branch_summary_out_of_range.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        with pytest.raises(ValueError, match="BRANCH_SUMMARY_INVALID_RANGE"):
            parse_branch_state_summary(data["branch"])

    def test_fixture_fail_merge_unsupported_proof(self):
        """FAIL fixture: unsupported proof_type."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_merge_unsupported_proof.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        branch_a = parse_branch_state_summary(data["branch_a"])
        branch_b = parse_branch_state_summary(data["branch_b"])

        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_TYPE_INVALID"):
            can_merge(branch_a, branch_b, data["proof_type"], data["proof_ref"])

    def test_fixture_fail_merge_missing_proof_ref(self):
        """FAIL fixture: missing proof_ref."""
        fixture_path = Path(__file__).parent / "fixtures" / "gc10_fail_merge_missing_proof_ref.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        branch_a = parse_branch_state_summary(data["branch_a"])
        branch_b = parse_branch_state_summary(data["branch_b"])

        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_REF_MISSING"):
            can_merge(branch_a, branch_b, data["proof_type"], data["proof_ref"])


class TestPassFixtures:
    """Test PASS fixtures."""

    def test_fixture_policy_valid(self):
        """PASS fixture: valid policy."""
        fixture_path = Path(__file__).parent / "fixtures" / "policy_valid.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        policy = parse_branch_policy(data["policy"])
        assert policy.max_active_branches == 3

    def test_fixture_prune_deterministic_basic(self):
        """PASS fixture: deterministic prune with distinct scores."""
        fixture_path = Path(__file__).parent / "fixtures" / "prune_deterministic_basic.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        policy = parse_branch_policy(data["policy"])
        active = [parse_branch_state_summary(b) for b in data["active_branches"]]
        incoming = parse_branch_state_summary(data["incoming_branch"])

        to_prune = select_prune_candidates(active, incoming, policy)

        assert to_prune == data["expected_prune"]

    def test_fixture_prune_tie_break_all_levels(self):
        """PASS fixture: tie-break all levels."""
        fixture_path = Path(__file__).parent / "fixtures" / "prune_tie_break_all_levels.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        policy = parse_branch_policy(data["policy"])
        branches = [parse_branch_state_summary(b) for b in data["branches"]]

        ranked = rank_branches_for_prune(branches, policy)

        assert [b.branch_id for b in ranked] == data["expected_prune_order"]

    def test_fixture_merge_allowed_with_cas_equiv(self):
        """PASS fixture: merge with CAS_EQUIV."""
        fixture_path = Path(__file__).parent / "fixtures" / "merge_allowed_with_cas_equiv.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        branch_a = parse_branch_state_summary(data["branch_a"])
        branch_b = parse_branch_state_summary(data["branch_b"])

        result, _ = can_merge(branch_a, branch_b, data["proof_type"], data["proof_ref"])
        assert result == data["expected"]

    def test_fixture_merge_allowed_with_strong_numeric(self):
        """PASS fixture: merge with STRONG_NUMERIC_AGREEMENT."""
        fixture_path = Path(__file__).parent / "fixtures" / "merge_allowed_with_strong_numeric.json"
        with open(fixture_path, "r") as f:
            data = json.load(f)

        branch_a = parse_branch_state_summary(data["branch_a"])
        branch_b = parse_branch_state_summary(data["branch_b"])

        result, _ = can_merge(branch_a, branch_b, data["proof_type"], data["proof_ref"])
        assert result == data["expected"]


class TestInsertBranchOrchestration:
    """Test insert_branch orchestration function for cap enforcement E2E."""

    def _make_policy(self, max_active: int = 3) -> BranchPolicy:
        return BranchPolicy(
            max_active_branches=max_active,
            weights=BranchWeights(w1=0.4, w2=0.3, w3=0.2, w4=0.1),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy="lowest_score_first",
            merge_rules=["CAS_EQUIV", "STRONG_NUMERIC_AGREEMENT"],
            tie_break=["failed_checks", "cost", "branch_id"],
        )

    def _make_branch(self, branch_id: str, coverage: float = 0.8, failed_checks: int = 0, cost: float = 10.0) -> BranchStateSummary:
        return BranchStateSummary(
            branch_id=branch_id,
            coverage=coverage,
            sanity_pass_rate=0.9,
            failed_checks=failed_checks,
            cost=cost,
            created_seq=0,
        )

    def test_branch_insert_adds_under_cap_and_logs_created(self):
        """E2E: Insert under cap adds branch and emits BRANCH_CREATED."""
        policy = self._make_policy(max_active=3)
        event_log = BranchEventLogger()
        
        active = [self._make_branch("branch-001"), self._make_branch("branch-002")]
        incoming = self._make_branch("branch-003")
        
        result = insert_branch(active, incoming, policy, event_log)
        
        assert len(result) == 3
        assert any(b.branch_id == "branch-003" for b in result)
        assert len(event_log.events) == 1
        assert event_log.events[0].event_type == BranchEventType.BRANCH_CREATED
        assert event_log.events[0].branch_ids == ["branch-003"]

    def test_branch_insert_at_cap_prunes_worst_deterministically_and_logs_prune_and_create(self):
        """E2E: Insert at cap prunes worst, emits BRANCH_PRUNED then BRANCH_CREATED."""
        policy = self._make_policy(max_active=2)
        event_log = BranchEventLogger()
        
        # branch-001 has lowest score (low coverage)
        active = [
            self._make_branch("branch-001", coverage=0.3),
            self._make_branch("branch-002", coverage=0.9),
        ]
        incoming = self._make_branch("branch-003", coverage=0.8)
        
        result = insert_branch(active, incoming, policy, event_log)
        
        # branch-001 should be pruned (lowest score)
        assert len(result) == 2
        assert not any(b.branch_id == "branch-001" for b in result)
        assert any(b.branch_id == "branch-002" for b in result)
        assert any(b.branch_id == "branch-003" for b in result)
        
        # Should have PRUNED then CREATED events
        assert len(event_log.events) == 2
        assert event_log.events[0].event_type == BranchEventType.BRANCH_PRUNED
        assert "branch-001" in event_log.events[0].branch_ids
        assert event_log.events[1].event_type == BranchEventType.BRANCH_CREATED
        assert event_log.events[1].branch_ids == ["branch-003"]

    def test_branch_insert_same_input_same_output_twice(self):
        """E2E: Determinism - same input produces same output across runs."""
        policy = self._make_policy(max_active=2)
        
        active = [
            self._make_branch("branch-001", coverage=0.3),
            self._make_branch("branch-002", coverage=0.9),
        ]
        incoming = self._make_branch("branch-003", coverage=0.8)
        
        # Run twice
        event_log1 = BranchEventLogger()
        result1 = insert_branch(list(active), incoming, policy, event_log1)
        
        event_log2 = BranchEventLogger()
        result2 = insert_branch(list(active), incoming, policy, event_log2)
        
        # Results must be identical
        result1_ids = sorted(b.branch_id for b in result1)
        result2_ids = sorted(b.branch_id for b in result2)
        assert result1_ids == result2_ids
        
        # Events must be identical
        assert len(event_log1.events) == len(event_log2.events)
        for e1, e2 in zip(event_log1.events, event_log2.events):
            assert e1.event_type == e2.event_type
            assert e1.branch_ids == e2.branch_ids


class TestMergeProofResolution:
    """Test merge proof resolution against ProofRegistry."""

    def _make_branch(self, branch_id: str) -> BranchStateSummary:
        return BranchStateSummary(
            branch_id=branch_id,
            coverage=0.8,
            sanity_pass_rate=0.9,
            failed_checks=0,
            cost=10.0,
            created_seq=0,
        )

    def test_merge_requires_proof_ref_resolves(self):
        """Merge fails if proof_ref does not resolve in registry."""
        registry = ProofRegistry()
        branch_a = self._make_branch("branch-001")
        branch_b = self._make_branch("branch-002")
        
        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_REF_NOT_FOUND"):
            can_merge(branch_a, branch_b, "CAS_EQUIV", "proof-missing", registry)

    def test_merge_rejects_proof_type_mismatch(self):
        """Merge fails if resolved proof_type doesn't match requested."""
        registry = ProofRegistry()
        artifact = ProofArtifact(
            proof_type="CAS_EQUIV",
            status=ProofStatus.PASS,
            created_seq=0,
        )
        registry.register("proof-001", artifact)
        
        branch_a = self._make_branch("branch-001")
        branch_b = self._make_branch("branch-002")
        
        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_TYPE_MISMATCH"):
            can_merge(branch_a, branch_b, "STRONG_NUMERIC_AGREEMENT", "proof-001", registry)

    def test_merge_rejects_non_pass_proof_status(self):
        """Merge fails if resolved proof status is not PASS."""
        registry = ProofRegistry()
        artifact = ProofArtifact(
            proof_type="CAS_EQUIV",
            status=ProofStatus.FAIL,
            created_seq=0,
        )
        registry.register("proof-001", artifact)
        
        branch_a = self._make_branch("branch-001")
        branch_b = self._make_branch("branch-002")
        
        with pytest.raises(ValueError, match="BRANCH_MERGE_PROOF_STATUS_NOT_PASS"):
            can_merge(branch_a, branch_b, "CAS_EQUIV", "proof-001", registry)

    def test_merge_accepts_cas_equiv_pass(self):
        """Merge succeeds with CAS_EQUIV and PASS status."""
        registry = ProofRegistry()
        artifact = ProofArtifact(
            proof_type="CAS_EQUIV",
            status=ProofStatus.PASS,
            created_seq=0,
            payload_ref="log-001",
        )
        registry.register("proof-001", artifact)
        
        branch_a = self._make_branch("branch-001")
        branch_b = self._make_branch("branch-002")
        
        result, resolved = can_merge(branch_a, branch_b, "CAS_EQUIV", "proof-001", registry)
        
        assert result is True
        assert resolved is artifact
        assert resolved.proof_type == "CAS_EQUIV"
        assert resolved.status == ProofStatus.PASS

    def test_merge_accepts_strong_numeric_pass_only_from_registry(self):
        """STRONG_NUMERIC_AGREEMENT merge only accepts PASS from registry (not wire claims)."""
        registry = ProofRegistry()
        artifact = ProofArtifact(
            proof_type="STRONG_NUMERIC_AGREEMENT",
            status=ProofStatus.PASS,
            created_seq=1,
            payload_ref="gc9-log-001",
        )
        registry.register("proof-strong-001", artifact)
        
        branch_a = self._make_branch("branch-001")
        branch_b = self._make_branch("branch-002")
        
        result, resolved = can_merge(branch_a, branch_b, "STRONG_NUMERIC_AGREEMENT", "proof-strong-001", registry)
        
        assert result is True
        assert resolved.proof_type == "STRONG_NUMERIC_AGREEMENT"
        assert resolved.status == ProofStatus.PASS


class TestAuditLogAssertions:
    """Test audit log event content and structure assertions."""

    def _make_policy(self, max_active: int = 2) -> BranchPolicy:
        return BranchPolicy(
            max_active_branches=max_active,
            weights=BranchWeights(w1=0.4, w2=0.3, w3=0.2, w4=0.1),
            normalization=BranchNormalization(K=10, C=100.0),
            prune_strategy="lowest_score_first",
            merge_rules=["CAS_EQUIV", "STRONG_NUMERIC_AGREEMENT"],
            tie_break=["failed_checks", "cost", "branch_id"],
        )

    def _make_branch(self, branch_id: str, coverage: float = 0.8) -> BranchStateSummary:
        return BranchStateSummary(
            branch_id=branch_id,
            coverage=coverage,
            sanity_pass_rate=0.9,
            failed_checks=0,
            cost=10.0,
            created_seq=0,
        )

    def test_prune_event_contains_snapshot_and_reason(self):
        """BRANCH_PRUNED event contains victim_branch_id, candidate snapshots, prune_key."""
        policy = self._make_policy(max_active=2)
        event_log = BranchEventLogger()
        
        active = [
            self._make_branch("branch-001", coverage=0.3),
            self._make_branch("branch-002", coverage=0.9),
        ]
        incoming = self._make_branch("branch-003", coverage=0.8)
        
        insert_branch(active, incoming, policy, event_log)
        
        prune_event = event_log.events[0]
        assert prune_event.event_type == BranchEventType.BRANCH_PRUNED
        
        # Required fields for PRUNED
        assert "branch-001" in prune_event.branch_ids  # victim_branch_id
        assert "ranked_candidates" in prune_event.snapshot
        assert "policy_max_active_branches" in prune_event.snapshot
        assert "prune_count" in prune_event.snapshot
        
        # Each candidate should have score snapshot
        for candidate in prune_event.snapshot["ranked_candidates"]:
            assert "branch_id" in candidate
            assert "coverage" in candidate
            assert "score" in candidate
            assert "prune_key" in candidate
        
        # Reason should include prune_strategy and tie_break
        assert "prune_strategy" in prune_event.reason
        assert "prune_key" in prune_event.reason
        assert "tie_break" in prune_event.reason

    def test_merge_event_contains_proof_ref_and_resolution(self):
        """BRANCH_MERGED event contains proof_type, proof_ref, resolved artifact summary."""
        event_log = BranchEventLogger()
        registry = ProofRegistry()
        
        artifact = ProofArtifact(
            proof_type="CAS_EQUIV",
            status=ProofStatus.PASS,
            created_seq=0,
            payload_ref="log-001",
        )
        registry.register("proof-001", artifact)
        
        branch_a = self._make_branch("branch-001")
        branch_b = self._make_branch("branch-002")
        
        merge_event = event_log.log_branch_merged(branch_a, branch_b, "CAS_EQUIV", "proof-001", registry)
        
        assert merge_event.event_type == BranchEventType.BRANCH_MERGED
        assert merge_event.branch_ids == ["branch-001", "branch-002"]
        
        # Required fields for MERGED
        assert "proof_type" in merge_event.reason
        assert merge_event.reason["proof_type"] == "CAS_EQUIV"
        assert "proof_ref" in merge_event.reason
        assert merge_event.reason["proof_ref"] == "proof-001"
        
        # Resolved proof artifact summary
        assert "proof_artifact" in merge_event.reason
        assert merge_event.reason["proof_artifact"]["proof_type"] == "CAS_EQUIV"
        assert merge_event.reason["proof_artifact"]["status"] == "pass"
        
        # Score snapshots for branches
        assert "branch_a" in merge_event.snapshot
        assert "branch_b" in merge_event.snapshot

    def test_created_event_emitted_on_insert(self):
        """BRANCH_CREATED event emitted when branch is inserted."""
        policy = self._make_policy(max_active=5)
        event_log = BranchEventLogger()
        
        active = []
        incoming = self._make_branch("branch-001")
        
        insert_branch(active, incoming, policy, event_log)
        
        assert len(event_log.events) == 1
        created_event = event_log.events[0]
        
        assert created_event.event_type == BranchEventType.BRANCH_CREATED
        assert created_event.branch_ids == ["branch-001"]
        assert "branch" in created_event.snapshot
        assert created_event.snapshot["branch"]["branch_id"] == "branch-001"
        assert "score" in created_event.snapshot["branch"]
        assert "reason" in created_event.reason
