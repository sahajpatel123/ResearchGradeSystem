# GC-6.1 PATCH SET — COMPLETE ✓

**Status:** FROZEN - Ready for production use  
**Tests:** 323 passing (266 original + 42 GC-6 + 15 ID parsers)  
**Scope:** Compute-on-invalid, fixture naming clarity, ID wire-boundary hardening

---

## Patch Summary

GC-6.1 addresses three critical issues before freezing GC-6:

1. **Compute-on-invalid**: `compute_integrity_metrics()` now works defensively even when GC-4/GC-5 fail (for diagnostics)
2. **Fixture naming clarity**: Split fixtures into `report_valid` (pass full validation) vs `metrics_only` (may fail GC-4)
3. **ID wire-boundary hardening**: Strict parsers for claim_id, step_id, tool_run_id, citation_id (reject-only, no trimming)

---

## 1) Compute-on-Invalid (Diagnostics)

### Problem
If GC-6 runs only after GC-4/GC-5 validators, the "hallucination meter" disappears exactly when debugging needs it most (during early dev when failures are common).

### Solution
`compute_integrity_metrics()` is now **DEFENSIVE** and works on malformed reports:

**Key changes:**
- Accepts `Any` types for claims and evidence_by_id (not just validated types)
- Never crashes on malformed input (returns deterministic metrics)
- Adds `diagnostics_notes: list[str]` field to IntegrityMetrics
- Handles: None values, wrong types, malformed claim objects, malformed evidence_ids

**Behavior:**
```python
# Works even when report is completely malformed
metrics = compute_integrity_metrics(None, None)
# Returns: IntegrityMetrics(unsupported=0, total=0, rate=0.0, ids=[], 
#                           diagnostics_notes=["claims was None", "evidence_by_id was None"])

# Works when claims have wrong types
metrics = compute_integrity_metrics("not a list", {})
# Returns: IntegrityMetrics with diagnostics_notes=["claims wrong type (str)"]

# Works when evidence_ids is malformed
claim.evidence_ids = "not-a-list"  # Bypass validation
metrics = compute_integrity_metrics([claim], {})
# Returns: unsupported=1 with diagnostics_notes=["evidence_ids wrong type"]
```

**Fail-closed for diagnostics:**
- If any parsing/type issue prevents confirming support → treat as unsupported
- Option A strict still applies: ANY dangling evidence_id → unsupported
- Deterministic output even on garbage input

### Files Modified
- `src/core/integrity_metrics.py` - Defensive compute function with diagnostics_notes
- `src/core/gc6_validators.py` - Updated to handle defensive compute

### Tests Added (5)
- `test_gc6_computes_when_report_invalid_gc4_missing_evidence()`
- `test_gc6_computes_when_evidence_objects_gc5_invalid()`
- `test_gc6_never_throws_on_malformed_report_shapes()`
- `test_gc6_handles_malformed_claim_objects()`
- `test_gc6_handles_malformed_evidence_ids()`

---

## 2) Fixture Naming Clarity

### Problem
Calling a fixture "valid" while it contains unsupported claims is confusing if GC-4 is strict.

### Solution
Split fixtures into two clear categories:

**A) `report_valid` fixtures** - MUST pass GC-5 + GC-4 + GC-6 enforcement
- `gc6_report_valid_all_supported.json` - All non-SPEC claims supported (rate=0.0)
- `gc6_report_valid_zero_total.json` - All claims SPECULATIVE (total=0, rate=0.0)

**B) `metrics_only` fixtures** - May be invalid for GC-4; used ONLY for compute_integrity_metrics tests
- `gc6_metrics_only_mixed_support.json` - Mixed support (may have dangling evidence_ids)
- `gc6_metrics_only_all_unsupported.json` - All non-SPEC claims unsupported

### Renamed Fixtures
```
gc6_valid_all_supported.json       → gc6_report_valid_all_supported.json
gc6_valid_zero_total.json          → gc6_report_valid_zero_total.json
gc6_valid_mixed_support.json       → gc6_metrics_only_mixed_support.json
gc6_valid_all_unsupported.json     → gc6_metrics_only_all_unsupported.json
```

### Test Updates
- Updated fixture paths in `tests/test_gc6_integrity_metrics.py`
- Added clear docstrings distinguishing categories
- `report_valid` fixtures tested with full validation
- `metrics_only` fixtures tested only for computation correctness

---

## 3) ID Wire-Boundary Hardening

### Problem
GC-6 outputs `unsupported_claim_ids`. If claim_id can contain invisibles/confusables, determinism + mismatch checks + UI linking become unreliable.

### Solution
Created strict wire-boundary parsers matching GC-2/GC-4 posture (reject-only, NO TRIM):

**New module:** `src/core/id_parsers.py`

**Parsers:**
- `parse_claim_id(wire: Any) -> str`
- `parse_step_id(wire: Any) -> str`
- `parse_tool_run_id(wire: Any) -> str`
- `parse_citation_id(wire: Any) -> str`

**Strict token rules for all IDs:**
1. Must be JSON string (not None, not int, not list)
2. Must be ASCII-only (reject non-ASCII characters)
3. Must contain NO invisibles:
   - ZWSP (U+200B)
   - NBSP (U+00A0)
   - BOM (U+FEFF)
   - WJ (U+2060)
   - ZWNJ (U+200C)
   - ZWJ (U+200D)
4. Must have NO leading/trailing whitespace (reject, do NOT trim)
5. Must be non-empty

**Validation order:**
1. Type check (must be string)
2. Empty check
3. Unicode invisibles check (FIRST, before whitespace)
4. Leading/trailing whitespace check (reject if `s != s.strip()`)
5. ASCII-only check

**Error messages:**
- `TypeError`: "must be string, got {type}"
- `ValueError`: "contains unicode invisible character (U+200B)"
- `ValueError`: "has leading/trailing whitespace (no trimming)"
- `ValueError`: "contains non-ASCII characters"
- `ValueError`: "empty string"

### Fixtures Added (2)
- `gc6_invalid_claim_id_zwsp.json` - claim_id with ZWSP (U+200B)
- `gc6_invalid_claim_id_nbsp.json` - claim_id with NBSP (U+00A0)

### Tests Added (15)
**TestParseClaimId (6 tests):**
- test_parse_claim_id_valid
- test_parse_claim_id_rejects_none
- test_parse_claim_id_rejects_wrong_type
- test_parse_claim_id_rejects_empty
- test_parse_claim_id_rejects_whitespace_variants
- test_parse_claim_id_rejects_invisibles_and_non_ascii

**TestParseStepId (3 tests):**
- test_parse_step_id_valid
- test_parse_step_id_rejects_whitespace_variants
- test_parse_step_id_rejects_invisibles

**TestParseToolRunId (3 tests):**
- test_parse_tool_run_id_valid
- test_parse_tool_run_id_rejects_whitespace_variants
- test_parse_tool_run_id_rejects_invisibles

**TestParseCitationId (3 tests):**
- test_parse_citation_id_valid
- test_parse_citation_id_rejects_whitespace_variants
- test_parse_citation_id_rejects_invisibles

---

## Definition of Done (GC-6 FROZEN)

- [x] `compute_integrity_metrics()` runs deterministically even when GC-4/GC-5 fail
- [x] Fixtures renamed and split (report_valid vs metrics_only)
- [x] claim_id/step_id/tool_run_id/citation_id hardened with reject-only parsers
- [x] CI green: 323 tests passing (0.16s)
- [x] Tests explicitly cover:
  - [x] Compute-on-invalid (5 tests)
  - [x] Fixture category meaning (clear naming + docstrings)
  - [x] ID hygiene (15 tests)

---

## Test Results

```
323 tests passing (0.16s)
- 71 GC-1 tests (claim definition, finalization)
- 58 GC-2 tests (label validation, wire boundary)
- 29 GC-3 tests (step/claim boundary)
- 42 GC-4 tests (evidence attachment + wire hardening)
- 66 GC-5 tests (evidence object schema)
- 42 GC-6 tests (integrity metrics) ✓ UPDATED
- 15 ID parser tests (claim_id, step_id, tool_run_id, citation_id) ✓ NEW
```

---

## Files Created/Modified

### New Files (3):
- `src/core/id_parsers.py` - ID wire-boundary parsers (claim_id, step_id, tool_run_id, citation_id)
- `tests/test_id_parsers.py` - 15 comprehensive ID hygiene tests
- `GC6.1_PATCH.md` - This documentation

### Modified Files (3):
- `src/core/integrity_metrics.py` - Defensive compute function + diagnostics_notes
- `src/core/gc6_validators.py` - Updated to handle defensive compute
- `tests/test_gc6_integrity_metrics.py` - Added 5 compute-on-invalid tests, updated fixture paths

### Renamed Fixtures (4):
- `gc6_valid_all_supported.json` → `gc6_report_valid_all_supported.json`
- `gc6_valid_zero_total.json` → `gc6_report_valid_zero_total.json`
- `gc6_valid_mixed_support.json` → `gc6_metrics_only_mixed_support.json`
- `gc6_valid_all_unsupported.json` → `gc6_metrics_only_all_unsupported.json`

### New Fixtures (2):
- `gc6_invalid_claim_id_zwsp.json` - ZWSP in claim_id
- `gc6_invalid_claim_id_nbsp.json` - NBSP in claim_id

---

## Next Steps

**GC-6 is now FROZEN** with:
- Unforgeable hallucination meter (computed-only, fail-closed)
- Defensive diagnostics (works even when GC-4/GC-5 fail)
- Clear fixture categories (report_valid vs metrics_only)
- Hardened ID hygiene (reject-only parsers for all IDs)

**Next GC:** GC-7 Step Status + Coverage Bookkeeping

---

## Canonical Numbering

All code comments, fixture names, and test names use **GC-6** (not old numbering).
GC-6 == Unsupported claim + unsupported-claim rate.
