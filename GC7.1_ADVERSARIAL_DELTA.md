# GC-7.1 ADVERSARIAL DELTA SUITE

**Purpose:** Adversarial test coverage for GC-7.1 status_reason policy correction  
**Scope:** 8 delta fixtures targeting the patched policy  
**Policy Under Test:** Failed steps MAY have status_reason; checked/unchecked MUST NOT

---

## Policy Summary (GC-7.1)

### Final Status Reason Policy

| step_status    | status_reason | Policy                          |
|----------------|---------------|---------------------------------|
| `indeterminate`| REQUIRED      | Non-empty, non-whitespace       |
| `failed`       | OPTIONAL      | If present, must be non-empty   |
| `checked`      | NOT ALLOWED   | Fail-closed: reject if present  |
| `unchecked`    | NOT ALLOWED   | Fail-closed: reject if present  |

### Error Categories (Revised - GC-7.1a)

- `INDETERMINATE_MISSING_REASON` - indeterminate without status_reason (None/null only)
- `STATUS_REASON_EMPTY_WHEN_PRESENT` - status_reason field present but empty/whitespace-only/invisible-only (any step_status) (GC-7.1a new)
- `STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED` - checked/unchecked with status_reason (GC-7.1 renamed)

---

## Delta Fixtures (8 Total)

### 1) gc7_adversarial_failed_valid_reason.json

**Category:** PASS  
**Attack Vector:** `failed_step_with_valid_reason`  
**Purpose:** Failed step with valid status_reason (GC-7.1 policy: optional but allowed)

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "failed",
  "status_reason": "Verification failed: missing required data source"
}
```

**Expected Outcome:** ✅ PASS  
**Rationale:** Failed steps MAY include status_reason (GC-7.1 policy change)

**Coverage Metrics:**
- `failed_steps`: `[{"step_id": "step-001", "reason": "Verification failed: missing required data source"}]`
- `failed_count`: 1
- `total_steps`: 1

---

### 2) gc7_adversarial_failed_whitespace_reason.json

**Category:** FAIL  
**Attack Vector:** `failed_step_whitespace_only_reason`  
**Purpose:** Failed step with whitespace-only status_reason

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "failed",
  "status_reason": "   "
}
```

**Expected Outcome:** ❌ FAIL  
**Error Category:** `STATUS_REASON_EMPTY_WHEN_PRESENT` (GC-7.1a)  
**Policy Decision:** FAIL - status_reason is optional for failed, but if present must be non-empty after trim

**Rationale:** Fail-closed posture - if status_reason is provided, it must have semantic content (non-whitespace). Whitespace-only strings are rejected even when status_reason is optional. GC-7.1a: Generic empty-when-present category applies to any step_status.

**Wire Posture:** No trimming for storage, but emptiness check validates semantic content.

---

### 3) gc7_adversarial_checked_with_reason.json

**Category:** FAIL  
**Attack Vector:** `checked_step_with_status_reason`  
**Purpose:** Checked step with status_reason (not allowed - fail-closed)

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "checked",
  "status_reason": "Adversarial: trying to add reason to checked step"
}
```

**Expected Outcome:** ❌ FAIL  
**Error Category:** `STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED`  
**Rationale:** GC-7.1 policy: status_reason NOT ALLOWED for checked/unchecked (fail-closed)

**Attack Description:** Adversary attempts to inject status_reason on checked step, hoping to bypass validation or inject metadata.

---

### 4) gc7_adversarial_unchecked_with_reason.json

**Category:** FAIL  
**Attack Vector:** `unchecked_step_with_status_reason`  
**Purpose:** Unchecked step with status_reason (not allowed - fail-closed)

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "unchecked",
  "status_reason": "Adversarial: trying to add reason to unchecked step"
}
```

**Expected Outcome:** ❌ FAIL  
**Error Category:** `STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED`  
**Rationale:** GC-7.1 policy: status_reason NOT ALLOWED for checked/unchecked (fail-closed)

**Attack Description:** Adversary attempts to inject status_reason on unchecked step, testing policy enforcement.

---

### 5) gc7_adversarial_indeterminate_no_reason.json

**Category:** FAIL  
**Attack Vector:** `indeterminate_without_status_reason`  
**Purpose:** Indeterminate step without status_reason (required field missing)

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "indeterminate"
}
```

**Expected Outcome:** ❌ FAIL  
**Error Category:** `INDETERMINATE_MISSING_REASON`  
**Rationale:** GC-7.1 policy: indeterminate → status_reason REQUIRED (non-empty)

**Attack Description:** Adversary omits required status_reason for indeterminate step, testing required field enforcement.

---

### 6) gc7_adversarial_indeterminate_invisible_reason.json

**Category:** FAIL  
**Attack Vector:** `indeterminate_invisible_only_reason`  
**Purpose:** Indeterminate step with invisible-only status_reason (ZWSP x3)

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "indeterminate",
  "status_reason": "\u200b\u200b\u200b"
}
```

**Expected Outcome:** ❌ FAIL  
**Error Category:** `INDETERMINATE_REASON_EMPTY`  
**Invisible Characters:** U+200B (ZERO WIDTH SPACE) x3

**Rationale:** Fail-closed - invisible-only strings have no semantic content, should be rejected like whitespace-only.

**Attack Description:** Adversary uses invisible Unicode characters (ZWSP) to bypass emptiness checks, hoping parser only checks for ASCII whitespace.

**Defense:** Parser must detect invisible characters as semantically empty.

---

### 7) gc7_adversarial_failed_reason_coverage.json

**Category:** PASS  
**Attack Vector:** `failed_reason_in_coverage_bucket`  
**Purpose:** Failed step with status_reason - verify coverage computes correctly with reason in bucket

**Wire Input:**
```json
{
  "steps": [
    {"step_id": "step-001", "step_status": "checked"},
    {"step_id": "step-002", "step_status": "failed", "status_reason": "Computation error: division by zero"},
    {"step_id": "step-003", "step_status": "unchecked"}
  ]
}
```

**Expected Outcome:** ✅ PASS  
**Expected Coverage:**
```json
{
  "checked_steps": ["step-001"],
  "unchecked_steps": [{"step_id": "step-003", "kind": "unchecked"}],
  "failed_steps": [{"step_id": "step-002", "reason": "Computation error: division by zero"}],
  "checked_count": 1,
  "unchecked_count": 1,
  "failed_count": 1,
  "total_steps": 3,
  "verification_progress_ratio": 0.5,
  "verified_work_pct": 0.3333333333333333
}
```

**Rationale:** Coverage computation must handle failed steps with optional status_reason correctly. Failed step with reason should appear in `failed_steps` bucket with reason field populated.

**Attack Description:** Tests that coverage metrics correctly include failed step reason in bucket structure without breaking partition/count logic.

---

### 8) gc7_adversarial_parser_drift_trimming.json

**Category:** FAIL  
**Attack Vector:** `wire_parser_drift_whitespace_trimming`  
**Purpose:** Wire parser drift - checked step with whitespace-only status_reason (tests trimming bypass)

**Wire Input:**
```json
{
  "step_id": "step-001",
  "step_status": "checked",
  "status_reason": "  \t\n  "
}
```

**Expected Outcome:** ❌ FAIL  
**Error Category:** `STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED`

**Attack Description:** Adversary provides whitespace-only status_reason on checked step, hoping parser will trim to empty and accept. Parser must reject presence of field regardless of content.

**Wire Posture:** No trimming at wire boundary - reject field presence for checked/unchecked.

**Rationale:** Fail-closed - checked steps cannot have status_reason field present at all, even if whitespace-only. This tests that the validator checks for field presence BEFORE any trimming or content validation.

**Defense:** Validator must check `if status_reason_wire is not None` for checked/unchecked, rejecting ANY value (including whitespace-only).

---

## Policy Decisions

### Failed Step Status Reason Quality

**Question:** If failed step provides status_reason, must it be non-empty/non-whitespace?

**Decision:** YES - FAIL if present but empty/whitespace-only

**Rationale:**
- Fail-closed posture: if status_reason is provided, it must have semantic content
- Whitespace-only or invisible-only strings are rejected even when status_reason is optional
- This prevents adversarial "present but meaningless" attacks

**Implementation:**
```python
elif step_status == StepStatus.FAILED:
    # Failed steps MAY include status_reason (optional)
    status_reason = parse_status_reason(status_reason_wire, required=False) if status_reason_wire is not None else None
```

`parse_status_reason` with `required=False` still validates non-emptiness if value is provided.

---

## Error Category Alignment

### Renamed Categories (GC-7.1)

| Old Name (GC-7.0)                              | New Name (GC-7.1)                                    |
|------------------------------------------------|------------------------------------------------------|
| `STATUS_REASON_PRESENT_WHEN_NOT_INDETERMINATE` | `STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED` |

**Reason for Rename:** More precise - policy now allows status_reason on failed, so "not indeterminate" is inaccurate. New name explicitly states checked/unchecked are disallowed.

### All GC-7 Error Categories (13 Total)

**Step-Level (4):**
1. `STEP_STATUS_INVALID`
2. `INDETERMINATE_MISSING_REASON`
3. `INDETERMINATE_REASON_EMPTY`
4. `STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED`

**Coverage/Bookkeeping (9):**
5. `COVERAGE_METRICS_MISMATCH`
6. `COVERAGE_BUCKET_GHOST_STEP_ID`
7. `COVERAGE_BUCKET_DUPLICATE_STEP_ID`
8. `COVERAGE_PARTITION_MISMATCH`
9. `COVERAGE_COUNT_MISMATCH`
10. `COVERAGE_RATIO_MISMATCH`
11. `COVERAGE_NOTE_MISSING_ZERO_STEPS`
12. `COVERAGE_INVALID_NUMBER`
13. `COVERAGE_WRONG_TYPE`

---

## Attack Surface Analysis

### Newly Allowed: Failed Steps with Status Reason

**Risk:** Adversary could inject arbitrary metadata via failed step status_reason

**Mitigation:**
- status_reason is optional for failed (not required)
- If present, must be non-empty/non-whitespace (fail-closed)
- No special parsing or interpretation of status_reason content
- status_reason is purely informational, not used in coverage computation logic

**Residual Risk:** Low - status_reason is display-only metadata, not used in validation logic

### Newly Restricted: Checked/Unchecked Cannot Have Status Reason

**Risk:** Adversary could attempt to bypass restriction via whitespace trimming or parser drift

**Mitigation:**
- Validator checks field presence BEFORE content validation
- Rejects ANY value for checked/unchecked, including whitespace-only
- No trimming at wire boundary for field presence check

**Residual Risk:** Negligible - fail-closed posture with explicit field presence check

### Invisible Character Attacks

**Risk:** Adversary uses invisible Unicode (ZWSP, NBSP, etc.) to bypass emptiness checks

**Mitigation:**
- `parse_status_reason` validates semantic content after trim
- Invisible-only strings treated as empty (fail-closed)

**Residual Risk:** Low - existing wire parser infrastructure handles invisibles

---

## Test Coverage Summary

### Delta Fixtures by Category

**PASS (2):**
1. `gc7_adversarial_failed_valid_reason.json` - Failed with valid reason
2. `gc7_adversarial_failed_reason_coverage.json` - Coverage computation with failed reason

**FAIL (6):**
1. `gc7_adversarial_failed_whitespace_reason.json` - Failed with whitespace-only reason
2. `gc7_adversarial_checked_with_reason.json` - Checked with status_reason
3. `gc7_adversarial_unchecked_with_reason.json` - Unchecked with status_reason
4. `gc7_adversarial_indeterminate_no_reason.json` - Indeterminate without reason
5. `gc7_adversarial_indeterminate_invisible_reason.json` - Indeterminate with invisible-only reason
6. `gc7_adversarial_parser_drift_trimming.json` - Wire parser drift via whitespace trimming

### Attack Vectors Covered

1. ✅ Failed step with valid status_reason (policy change)
2. ✅ Failed step with whitespace-only status_reason (quality enforcement)
3. ✅ Checked step with status_reason (fail-closed)
4. ✅ Unchecked step with status_reason (fail-closed)
5. ✅ Indeterminate without status_reason (required field)
6. ✅ Indeterminate with invisible-only reason (semantic emptiness)
7. ✅ Coverage computation with failed reason (bucket structure)
8. ✅ Wire parser drift via whitespace trimming (field presence check)

---

## Expected Outcomes Summary

| Fixture                                        | Category | Error Category                                       | Outcome |
|------------------------------------------------|----------|------------------------------------------------------|---------|
| gc7_adversarial_failed_valid_reason            | PASS     | N/A                                                  | ✅ PASS  |
| gc7_adversarial_failed_whitespace_reason       | FAIL     | INDETERMINATE_REASON_EMPTY                           | ❌ FAIL  |
| gc7_adversarial_checked_with_reason            | FAIL     | STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED   | ❌ FAIL  |
| gc7_adversarial_unchecked_with_reason          | FAIL     | STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED   | ❌ FAIL  |
| gc7_adversarial_indeterminate_no_reason        | FAIL     | INDETERMINATE_MISSING_REASON                         | ❌ FAIL  |
| gc7_adversarial_indeterminate_invisible_reason | FAIL     | INDETERMINATE_REASON_EMPTY                           | ❌ FAIL  |
| gc7_adversarial_failed_reason_coverage         | PASS     | N/A                                                  | ✅ PASS  |
| gc7_adversarial_parser_drift_trimming          | FAIL     | STATUS_REASON_NOT_ALLOWED_FOR_CHECKED_OR_UNCHECKED   | ❌ FAIL  |

---

## Integration Notes

### No Production Code Changes Required

All adversarial fixtures test existing GC-7.1 implementation:
- `src/core/step.py` - DerivationStep validation
- `src/core/gc7_validators.py` - Wire boundary validation
- `src/core/gc7_wire_parsers.py` - parse_status_reason

### Test Suite Integration

Add to `tests/test_gc7_coverage_metrics.py`:
```python
class TestGC7AdversarialDelta:
    """GC-7.1 adversarial delta suite for status_reason policy correction."""
    
    def test_adversarial_failed_valid_reason(self):
        """PASS: Failed step with valid status_reason (GC-7.1 policy)."""
        # Load fixture and validate
        
    def test_adversarial_failed_whitespace_reason(self):
        """FAIL: Failed step with whitespace-only status_reason."""
        # Load fixture and expect INDETERMINATE_REASON_EMPTY
        
    # ... (6 more tests)
```

---

## Conclusion

GC-7.1 adversarial delta suite provides comprehensive coverage of the status_reason policy correction:

✅ **Policy Change Validated:** Failed steps can have status_reason  
✅ **Fail-Closed Enforcement:** Checked/unchecked reject status_reason  
✅ **Quality Enforcement:** Whitespace/invisible-only reasons rejected  
✅ **Wire Parser Hardening:** Field presence checked before content validation  
✅ **Coverage Computation:** Failed reason correctly included in buckets

**Total Fixtures:** 8 (2 PASS + 6 FAIL)  
**Error Categories:** 3 (aligned with GC-7.1 rename)  
**Attack Vectors:** 8 distinct scenarios

**Status:** Ready for integration testing
