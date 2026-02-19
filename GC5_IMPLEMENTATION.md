# GC-5 EVIDENCE OBJECT MINIMUM SCHEMA — IMPLEMENTATION COMPLETE ✓

## 1) Current Item
**GC-5 Evidence Object Minimum Schema**

## 2) Acceptance Checklist
- [x] EvidenceType enum with exactly 3 values (derivation, computation, citation)
- [x] EvidenceStatus enum with exactly 3 values (pass, fail, indeterminate)
- [x] IndeterminateReason enum with exactly 6 tight values
- [x] EvidenceSource tagged union with strict kind validation
- [x] PayloadRef tagged union with strict kind validation
- [x] EvidenceObject schema with all required fields
- [x] evidence_type ↔ source.kind alignment enforced
- [x] Indeterminate must have reason from tight enum
- [x] Wire-boundary parsers for all GC-5 types (NO TRIMMING)
- [x] Strict token validation (ASCII, no whitespace variants, no invisibles)
- [x] Internal whitespace rejection in ID tokens
- [x] 4 PASS fixtures (derivation, computation, citation, indeterminate)
- [x] 14 FAIL fixtures covering all validation rules
- [x] 66 comprehensive GC-5 tests (all passing)
- [x] GC-4 fixtures and tests updated to use GC-5 schema
- [x] All 266 tests passing (71 GC-1 + 58 GC-2 + 29 GC-3 + 42 GC-4 + 66 GC-5)

## 3) Implementation Plan
- Step 1: Define EvidenceType, EvidenceStatus, IndeterminateReason enums ✓
- Step 2: Define EvidenceSource and PayloadRef tagged union dataclasses ✓
- Step 3: Upgrade EvidenceObject schema with all required fields ✓
- Step 4: Implement wire-boundary parsers for all GC-5 types ✓
- Step 5: Implement GC-5 validators with deterministic error categories ✓
- Step 6: Create 4 PASS fixtures (derivation, computation, citation, indeterminate) ✓
- Step 7: Create 14 FAIL fixtures covering all validation rules ✓
- Step 8: Add comprehensive tests for schema, parsers, validators, fixtures ✓
- Step 9: Update GC-4 fixtures and tests to use new GC-5 schema ✓
- Step 10: Verify all tests pass and create documentation ✓

## 4) Files/Modules

### Schema files:
- `src/core/evidence.py` - EvidenceObject, EvidenceType, EvidenceStatus, IndeterminateReason, EvidenceSource, PayloadRef

### Wire parser files:
- `src/core/gc5_wire_parsers.py` - parse_evidence_id, parse_evidence_type, parse_evidence_status, parse_indeterminate_reason, parse_evidence_source, parse_payload_ref, parse_evidence_object

### Validator files:
- `src/core/gc5_validators.py` - validate_evidence_object, validate_report_evidence, validate_evidence_type_source_alignment

### Fixtures path:
- `tests/fixtures/gc5_valid_*.json` (4 PASS fixtures)
- `tests/fixtures/gc5_invalid_*.json` (14 FAIL fixtures)

### Tests path:
- `tests/test_gc5_evidence_schema.py` (66 comprehensive tests)
- `tests/test_gc4_evidence.py` (updated for GC-5 schema)

## 5) Schema Summary

### EvidenceObject fields
```python
@dataclass
class EvidenceObject:
    evidence_id: str                              # Required, strict token
    evidence_type: EvidenceType                   # Required, enum
    source: EvidenceSource                        # Required, tagged union
    status: EvidenceStatus                        # Required, enum
    payload_ref: PayloadRef                       # Required, tagged union
    status_reason: Optional[IndeterminateReason]  # Required iff status == INDETERMINATE
    notes: Optional[str]                          # Optional, non-empty if present
```

### EvidenceSource union
```python
@dataclass
class EvidenceSource:
    kind: Literal["step_id", "tool_run_id", "citation_id"]
    value: str  # Strict token validation
```

### PayloadRef union
```python
@dataclass
class PayloadRef:
    kind: Literal["log_id", "snippet_ref", "expression_ref"]
    value: str  # Strict token validation
```

### Enums

**EvidenceType** (3 values):
- DERIVATION = "derivation"
- COMPUTATION = "computation"
- CITATION = "citation"

**EvidenceStatus** (3 values):
- PASS = "pass"
- FAIL = "fail"
- INDETERMINATE = "indeterminate"

**IndeterminateReason** (6 tight values):
- UNSUPPORTED = "unsupported"
- DOMAIN = "domain"
- SINGULARITY = "singularity"
- TIMEOUT = "timeout"
- MISSING_BC_IC = "missing_bc_ic"
- TOOL_ERROR = "tool_error"

## 6) Validator Rules Implemented

### Core field presence
- **EVIDENCE_MISSING_FIELD_<fieldname>**: Missing required field in evidence object

### Enum strictness
- **EVIDENCE_TYPE_INVALID**: evidence_type not in {derivation, computation, citation}
- **EVIDENCE_STATUS_INVALID**: status not in {pass, fail, indeterminate}
- **SOURCE_KIND_INVALID**: source.kind not in {step_id, tool_run_id, citation_id}
- **PAYLOAD_REF_KIND_INVALID**: payload_ref.kind not in {log_id, snippet_ref, expression_ref}
- **INDETERMINATE_REASON_INVALID**: status_reason not in tight enum

### Token strictness
- **EVIDENCE_ID_INVALID**: evidence_id violates token rules
- **SOURCE_VALUE_INVALID**: source.value violates token rules
- **PAYLOAD_REF_VALUE_INVALID**: payload_ref.value violates token rules

Token rules enforced:
- Must be string type
- Must be ASCII-only
- Must not contain invisibles (ZWSP, NBSP, BOM, WJ, ZWNJ, ZWJ)
- Must have NO leading/trailing whitespace (no trimming)
- Must not contain internal whitespace (space, tab, newline)
- Must not be empty

### Alignment rule
- **EVIDENCE_SOURCE_KIND_MISMATCH**: evidence_type ↔ source.kind alignment violated
  - derivation → step_id
  - computation → tool_run_id
  - citation → citation_id

### Indeterminate rule
- **INDETERMINATE_MISSING_REASON**: status == indeterminate AND status_reason missing/null
- **status_reason present when not indeterminate**: status_reason present when status != indeterminate

### Payload ref required
- **PAYLOAD_REF_MISSING**: payload_ref field missing

### Notes rule
- **NOTES_EMPTY**: notes present but empty after trim

### Collision rule
- **EVIDENCE_ID_COLLISION**: Duplicate evidence_id in report.evidence[]

## 7) Wire Parsing Posture

### Exact accepted/rejected rules

**Accepted**:
- Exact ASCII strings with NO leading/trailing whitespace
- Example: `"evidence-001"`, `"step-id-123"`, `"log-derivation-001"`

**Rejected (deterministic)**:

**Type rejections**:
- None/null
- Non-string types (int, list, dict, bool)
- Non-dict for tagged unions

**Content rejections**:
- Empty string
- Whitespace-only
- **Leading/trailing whitespace** (space, tab, newline, CR) — **NO TRIMMING**
- Unicode invisibles (ZWSP, NBSP, BOM, WJ, ZWNJ, ZWJ)
- Non-ASCII characters (confusables)
- **Internal whitespace** (space, tab, newline inside token)

**Enum rejections**:
- Values not in enum (case-sensitive, exact match)
- Wrong case (e.g., "Derivation" rejected, must be "derivation")

**Tagged union rejections**:
- Missing "kind" or "value" keys
- Invalid kind values
- Value violates token rules

## 8) Fixtures Added

### PASS fixtures (4):
- `gc5_valid_derivation.json` - Valid derivation evidence with step_id source
- `gc5_valid_computation.json` - Valid computation evidence with tool_run_id source
- `gc5_valid_citation.json` - Valid citation evidence with citation_id source
- `gc5_valid_indeterminate.json` - Valid indeterminate evidence with status_reason

### FAIL fixtures (14):
- `gc5_invalid_evidence_type.json` - EVIDENCE_TYPE_INVALID
- `gc5_invalid_source_kind_mismatch.json` - EVIDENCE_SOURCE_KIND_MISMATCH
- `gc5_invalid_indeterminate_missing_reason.json` - INDETERMINATE_MISSING_REASON
- `gc5_invalid_status_reason_when_not_indeterminate.json` - status_reason when not indeterminate
- `gc5_invalid_missing_payload_ref.json` - EVIDENCE_MISSING_FIELD_PAYLOAD_REF
- `gc5_invalid_notes_empty.json` - NOTES_EMPTY
- `gc5_invalid_evidence_id_whitespace.json` - EVIDENCE_ID_INVALID (whitespace)
- `gc5_invalid_evidence_id_zwsp.json` - EVIDENCE_ID_INVALID (ZWSP)
- `gc5_invalid_evidence_id_internal_whitespace.json` - EVIDENCE_ID_INVALID (internal whitespace)
- `gc5_invalid_source_value_whitespace.json` - SOURCE_VALUE_INVALID
- `gc5_invalid_payload_ref_value_whitespace.json` - PAYLOAD_REF_VALUE_INVALID
- `gc5_invalid_source_kind.json` - SOURCE_KIND_INVALID
- `gc5_invalid_payload_ref_kind.json` - PAYLOAD_REF_KIND_INVALID
- `gc5_invalid_indeterminate_reason.json` - INDETERMINATE_REASON_INVALID

## 9) Tests Added

### Test classes (66 tests total):

**TestEvidenceEnums** (3 tests):
- test_evidence_type_enum_values
- test_evidence_status_enum_values
- test_indeterminate_reason_enum_values

**TestEvidenceSource** (6 tests):
- test_evidence_source_valid_step_id
- test_evidence_source_valid_tool_run_id
- test_evidence_source_valid_citation_id
- test_evidence_source_rejects_invalid_kind
- test_evidence_source_rejects_empty_value
- test_evidence_source_rejects_whitespace_value

**TestPayloadRef** (6 tests):
- test_payload_ref_valid_log_id
- test_payload_ref_valid_snippet_ref
- test_payload_ref_valid_expression_ref
- test_payload_ref_rejects_invalid_kind
- test_payload_ref_rejects_empty_value
- test_payload_ref_rejects_whitespace_value

**TestEvidenceObjectSchema** (15 tests):
- test_evidence_object_valid_derivation
- test_evidence_object_valid_computation
- test_evidence_object_valid_citation
- test_evidence_object_valid_indeterminate_with_reason
- test_evidence_object_alignment_derivation_step_id
- test_evidence_object_alignment_computation_tool_run_id
- test_evidence_object_alignment_citation_citation_id
- test_evidence_object_rejects_alignment_mismatch
- test_evidence_object_indeterminate_requires_reason
- test_evidence_object_rejects_status_reason_when_not_indeterminate
- test_evidence_object_valid_notes
- test_evidence_object_rejects_empty_notes
- test_evidence_object_rejects_whitespace_evidence_id

**TestWireBoundaryParsers** (18 tests):
- test_parse_evidence_id_valid
- test_parse_evidence_id_rejects_whitespace
- test_parse_evidence_id_rejects_internal_whitespace
- test_parse_evidence_id_rejects_zwsp
- test_parse_evidence_id_rejects_non_ascii
- test_parse_evidence_type_valid
- test_parse_evidence_type_rejects_invalid
- test_parse_evidence_type_case_sensitive
- test_parse_evidence_status_valid
- test_parse_evidence_status_rejects_invalid
- test_parse_indeterminate_reason_valid
- test_parse_indeterminate_reason_rejects_invalid
- test_parse_evidence_source_valid
- test_parse_evidence_source_rejects_invalid_kind
- test_parse_evidence_source_rejects_whitespace_value
- test_parse_payload_ref_valid
- test_parse_payload_ref_rejects_invalid_kind
- test_parse_payload_ref_rejects_whitespace_value
- test_parse_evidence_object_valid
- test_parse_evidence_object_missing_field

**TestGC5Fixtures** (18 tests):
- test_gc5_valid_derivation_fixture
- test_gc5_valid_computation_fixture
- test_gc5_valid_citation_fixture
- test_gc5_valid_indeterminate_fixture
- test_gc5_invalid_evidence_type_fixture
- test_gc5_invalid_source_kind_mismatch_fixture
- test_gc5_invalid_indeterminate_missing_reason_fixture
- test_gc5_invalid_status_reason_when_not_indeterminate_fixture
- test_gc5_invalid_missing_payload_ref_fixture
- test_gc5_invalid_notes_empty_fixture
- test_gc5_invalid_evidence_id_whitespace_fixture
- test_gc5_invalid_evidence_id_zwsp_fixture
- test_gc5_invalid_evidence_id_internal_whitespace_fixture
- test_gc5_invalid_source_value_whitespace_fixture
- test_gc5_invalid_payload_ref_value_whitespace_fixture
- test_gc5_invalid_source_kind_fixture
- test_gc5_invalid_payload_ref_kind_fixture
- test_gc5_invalid_indeterminate_reason_fixture

## 10) Integration / Finalization

### Report validation order
1. **GC-5 validation first**: Validate report.evidence[] with GC-5 schema
   - All EvidenceObjects must be typed and valid
   - Enums must be strict
   - Tagged unions must be valid
   - Alignment must be enforced
   - Indeterminate must have reason
   - No evidence_id collisions

2. **GC-4 validation second**: Validate evidence_ids resolve against validated EvidenceObjects
   - Non-SPECULATIVE claims must have ≥1 evidence_id
   - SPECULATIVE claims must have verify_falsify
   - All evidence_ids must resolve to report.evidence[]

3. **Finalization gate**: FINAL is blocked if any GC-5 or GC-4 validation errors exist
   - GC-5 errors prevent evidence from being valid
   - GC-4 errors prevent claims from being supported
   - Both block finalization deterministically

### Integration with existing code
- GC-4 fixtures updated to use GC-5 schema (4 fixtures updated)
- GC-4 tests updated to use GC-5 types (42 tests updated)
- All evidence objects now use strict typed schema
- Wire parsers used for fixture loading

## 11) Done/Next

### What is done
- ✅ GC-5 Evidence Object Minimum Schema fully implemented
- ✅ Strict enums (EvidenceType, EvidenceStatus, IndeterminateReason)
- ✅ Tagged unions (EvidenceSource, PayloadRef)
- ✅ evidence_type ↔ source.kind alignment enforced
- ✅ Indeterminate must have reason from tight enum
- ✅ Wire-boundary parsers with NO TRIMMING posture
- ✅ Strict token validation (ASCII, no whitespace variants, no invisibles, no internal whitespace)
- ✅ 4 PASS fixtures + 14 FAIL fixtures
- ✅ 66 comprehensive GC-5 tests
- ✅ GC-4 fixtures and tests updated to use GC-5 schema
- ✅ All 266 tests passing (71 GC-1 + 58 GC-2 + 29 GC-3 + 42 GC-4 + 66 GC-5)
- ✅ Fail-closed validation with deterministic error categories
- ✅ No scope creep (no evidence content semantics beyond schema)
- ✅ Integration with report validation (GC-5 before GC-4)
- ✅ FINAL blocked if any GC-5/GC-4 errors exist

### Next ledger item
**Next ledger item: GC-6 Unsupported Claim + Unsupported-Claim Rate**

---

## Test Results

```
266 tests passing (0.15s)
- 71 GC-1 tests (claim definition, finalization)
- 58 GC-2 tests (label validation, wire boundary)
- 29 GC-3 tests (step/claim boundary)
- 42 GC-4 tests (evidence attachment + wire hardening)
- 66 GC-5 tests (evidence object schema) ✓ NEW
```

## Files Created/Modified

### New Files (3):
- `src/core/gc5_wire_parsers.py` - Wire-boundary parsers for all GC-5 types
- `src/core/gc5_validators.py` - GC-5 validators
- `tests/test_gc5_evidence_schema.py` - 66 comprehensive tests

### Modified Files (2):
- `src/core/evidence.py` - Upgraded from GC-4 minimal schema to GC-5 strict typed schema
- `tests/test_gc4_evidence.py` - Updated to use GC-5 schema types

### New Fixtures (18):
- 4 PASS fixtures (gc5_valid_*.json)
- 14 FAIL fixtures (gc5_invalid_*.json)

### Updated Fixtures (4):
- `gc4_valid_all_evidence.json` - Updated to use GC-5 schema
- `gc4_invalid_dangling_evidence_id.json` - Updated to use GC-5 schema
- `gc4_invalid_duplicate_evidence_ids.json` - Updated to use GC-5 schema
- `gc4_invalid_multiple_dangling_evidence_ids.json` - Updated to use GC-5 schema

---

## GC-5 is now FROZEN and ready for production use.
