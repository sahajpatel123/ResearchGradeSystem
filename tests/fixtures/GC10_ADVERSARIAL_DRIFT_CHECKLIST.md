# GC-10.1 Adversarial Drift Checklist

## Purpose
This checklist documents the freeze enforcement tests for GC-10.1 W behaviors:
1. **proof_ref resolution** - merge requires registry lookup, not just non-empty string
2. **audit log completeness** - events must contain full snapshots for reproducibility

---

## Attack Vectors & Expected Categories

### Merge Proof Resolution Attacks

| Attack | Fixture | Error Category | Drift Scenario |
|--------|---------|----------------|----------------|
| proof_ref not found | `gc10_adv_merge_proof_ref_not_found.json` | `BRANCH_MERGE_PROOF_REF_NOT_FOUND` | devs revert to "non-empty proof_ref only" |
| proof status=fail | `gc10_adv_merge_proof_status_fail.json` | `BRANCH_MERGE_PROOF_STATUS_NOT_PASS` | devs allow merge when proof exists but don't check status |
| proof status=indeterminate | `gc10_adv_merge_proof_status_indeterminate.json` | `BRANCH_MERGE_PROOF_STATUS_NOT_PASS` | devs treat indeterminate as "good enough" |
| proof_type mismatch | `gc10_adv_merge_proof_type_mismatch.json` | `BRANCH_MERGE_PROOF_TYPE_MISMATCH` | devs skip proof_type validation |
| wire strong_agreement=true | `gc10_adv_merge_wire_strong_agreement_true.json` | `BRANCH_MERGE_PROOF_STATUS_NOT_PASS` | devs trust wire booleans |
| heuristic merge rule | `gc10_adv_merge_heuristic_rule.json` | `BRANCH_MERGE_PROOF_TYPE_INVALID` | devs allow heuristic rules |
| empty proof_ref bypass | `gc10_adv_merge_empty_proof_ref_bypass.json` | `BRANCH_MERGE_PROOF_REF_MISSING` | devs allow empty proof_ref when wire merge=true |

### Audit Log Completeness Attacks

| Attack | Fixture | Error Category | Drift Scenario |
|--------|---------|----------------|----------------|
| prune missing snapshot | `gc10_adv_prune_event_missing_snapshot.json` | `AUDIT_LOG_MISSING_SNAPSHOT` | devs stop logging snapshot for performance |
| prune missing prune_key | `gc10_adv_prune_event_missing_prune_key.json` | `AUDIT_LOG_MISSING_PRUNE_KEY` | devs remove prune_key to reduce log size |
| merge missing proof_artifact | `gc10_adv_merge_event_missing_proof_artifact.json` | `AUDIT_LOG_MISSING_PROOF_ARTIFACT` | devs omit proof_artifact to save space |
| created missing score | `gc10_adv_created_event_missing_score.json` | `AUDIT_LOG_MISSING_SCORE` | devs skip score computation in created events |

---

## Required Fields

### BRANCH_PRUNED Event Snapshot
```json
{
  "policy_max_active_branches": int,
  "candidate_count": int,
  "prune_count": int,
  "ranked_candidates": [
    {
      "branch_id": str,
      "coverage": float,
      "sanity_pass_rate": float,
      "failed_checks": int,
      "cost": float,
      "failed_checks_norm": float,
      "cost_norm": float,
      "score": float,
      "prune_key": {
        "score": float,
        "failed_checks_desc": int,
        "cost_desc": float,
        "branch_id_desc": list[int]
      }
    }
  ]
}
```

### BRANCH_PRUNED Event Reason
```json
{
  "prune_strategy": "lowest_score_first",
  "prune_key": "(score asc, failed_checks desc, cost desc, branch_id desc)",
  "tie_break": ["failed_checks", "cost", "branch_id"]
}
```

### BRANCH_MERGED Event Reason (with registry)
```json
{
  "proof_type": "CAS_EQUIV" | "STRONG_NUMERIC_AGREEMENT",
  "proof_ref": str,
  "proof_artifact": {
    "proof_type": str,
    "status": "pass",
    "created_seq": int,
    "payload_ref": str | null
  }
}
```

### BRANCH_CREATED Event Snapshot
```json
{
  "branch": {
    "branch_id": str,
    "coverage": float,
    "sanity_pass_rate": float,
    "failed_checks": int,
    "cost": float,
    "failed_checks_norm": float,
    "cost_norm": float,
    "score": float,
    "prune_key": {...}
  }
}
```

---

## Drift Prevention Rules

### Rule 1: Never trust wire booleans
- `merge=true` from wire → IGNORE
- `strong_agreement=true` from wire → IGNORE
- Always resolve proof_ref in registry and check status

### Rule 2: proof_ref must resolve
- Non-empty string is NOT sufficient
- Must call `registry.resolve(proof_ref)` and get non-None result
- Error: `BRANCH_MERGE_PROOF_REF_NOT_FOUND`

### Rule 3: proof status must be PASS
- `status=fail` → reject merge
- `status=indeterminate` → reject merge
- Only `status=pass` allows merge
- Error: `BRANCH_MERGE_PROOF_STATUS_NOT_PASS`

### Rule 4: proof_type must match
- Requested proof_type must equal resolved artifact.proof_type
- Error: `BRANCH_MERGE_PROOF_TYPE_MISMATCH`

### Rule 5: Only objective proof types allowed
- `CAS_EQUIV` ✓
- `STRONG_NUMERIC_AGREEMENT` ✓
- `HEURISTIC_SIMILARITY` ✗
- `COSINE_MATCH` ✗
- Error: `BRANCH_MERGE_PROOF_TYPE_INVALID`

### Rule 6: Audit logs must be complete
- PRUNED events: full ranked_candidates with prune_key
- MERGED events: proof_artifact when registry provided
- CREATED events: score computed and logged
- Rationale: reproducibility and auditability

---

## Test Classes

- `TestAdversarialMergeProofResolution` - 7 tests
- `TestAdversarialAuditLogCompleteness` - 4 tests

Total: **11 adversarial freeze enforcement tests**
