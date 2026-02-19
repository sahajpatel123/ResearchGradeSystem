# GC-4 EVIDENCE ATTACHMENT RULE — IMPLEMENTATION COMPLETE ✓

## 1) Current Item:
**GC-4 Evidence Attachment Rule**

---

## 2) Acceptance Checklist:
- ✅ Claim schema updated with evidence_ids (list[str]) and verify_falsify (Optional[str])
- ✅ EvidenceObject minimal schema (evidence_id required)
- ✅ ScientificReport includes evidence list
- ✅ Wire-boundary parser: parse_evidence_id() with strict validation
- ✅ Wire-boundary parser: parse_evidence_ids() with duplicate detection
- ✅ NON_SPEC_MISSING_EVIDENCE: Non-SPECULATIVE must have ≥1 evidence_id
- ✅ SPEC_MISSING_VERIFY_FALSIFY: SPECULATIVE must have verify_falsify
- ✅ DANGLING_EVIDENCE_ID: evidence_ids must resolve to report.evidence[]
- ✅ EVIDENCE_ID_DUP_IN_CLAIM: No duplicate evidence_ids within claim
- ✅ EVIDENCE_ID_EMPTY: evidence_ids cannot be empty/whitespace
- ✅ Unicode protection: Rejects ZWSP, NBSP, non-ASCII in evidence_ids
- ✅ 1 PASS fixture with all 4 claim types
- ✅ 7 FAIL fixtures covering all error categories
- ✅ 36 comprehensive tests (all passing)
- ✅ CI-ready (all 194 tests pass)

---

## 3) Implementation Plan:
- **Step 1**: Update Claim schema with evidence_ids and verify_falsify ✓
- **Step 2**: Create EvidenceObject and update ScientificReport ✓
- **Step 3**: Implement wire-boundary parsers ✓
- **Step 4**: Implement GC-4 validators (3 core + 2 additional rules) ✓
- **Step 5**: Create PASS fixture ✓
- **Step 6**: Create 7 FAIL fixtures ✓
- **Step 7**: Add 36 comprehensive tests ✓
- **Step 8**: Verify integration with finalization ✓
- **Step 9**: Document and finalize ✓

---

## 4) Files/Modules:

### Schema Files
- `src/core/claim.py` - **MODIFIED**: Added verify_falsify field, evidence_ids type validation
- `src/core/evidence.py` - **NEW**: EvidenceObject minimal schema
- `src/core/report.py` - **MODIFIED**: Added evidence list, EVIDENCE_ID_COLLISION check

### Wire Parser Files
- `src/core/evidence_validators.py` - **NEW**: parse_evidence_id(), parse_evidence_ids(), EvidenceValidator

### Validator Files
- `src/core/evidence_validators.py` - **NEW**: Complete GC-4 validation logic

### Fixtures Path
- `tests/fixtures/gc4_valid_all_evidence.json` - **NEW**: Valid report with all 4 claim types
- `tests/fixtures/gc4_invalid_*.json` - **NEW**: 7 failure fixtures

### Tests Path
- `tests/test_gc4_evidence.py` - **NEW**: 36 comprehensive tests

---

## 5) Schema Summary:

### Claim Fields (Updated)
```python
claim_id: str
statement: str
claim_label: ClaimLabel
step_id: Optional[str]
evidence_ids: list[str]              # GC-4: REQUIRED for non-SPECULATIVE
claim_span: Optional[tuple[int, int]]
verify_falsify: Optional[str]        # GC-4: REQUIRED for SPECULATIVE
```

**GC-4 Requirements**:
- Non-SPECULATIVE (DERIVED/COMPUTED/CITED): Must have ≥1 evidence_id
- SPECULATIVE: Must have non-empty verify_falsify (after trim)
- evidence_ids must be list type (enforced in __post_init__)

### ScientificReport Evidence List
```python
claims: list[Claim]
steps: list[DerivationStep]
evidence: list[EvidenceObject]       # GC-4: NEW
report_id: Optional[str]
```

**Validation**:
- No duplicate evidence_ids in evidence list (EVIDENCE_ID_COLLISION)

### EvidenceObject Minimal Fields
```python
evidence_id: str                     # REQUIRED, non-empty
evidence_type: Optional[str]         # Not validated in GC-4
content: Optional[str]               # Not validated in GC-4
source: Optional[str]                # Not validated in GC-4
```

**GC-4 Scope**: Only evidence_id existence enforced. Type semantics in GC-5+.

---

## 6) Validator Rules Implemented:

### Core Rules (GC-4 Required)

**NON_SPEC_MISSING_EVIDENCE**
- **Rule**: Non-SPECULATIVE claims (DERIVED/COMPUTED/CITED) must have ≥1 evidence_id
- **Error**: `"NON_SPEC_MISSING_EVIDENCE: Claim {claim_id} (label={label}) must have ≥1 evidence_id (GC-4)"`
- **Enforcement**: Fail-closed validation

**SPEC_MISSING_VERIFY_FALSIFY**
- **Rule**: SPECULATIVE claims must have non-empty verify_falsify (after trim)
- **Error**: `"SPEC_MISSING_VERIFY_FALSIFY: Claim {claim_id} (label=SPECULATIVE) must have non-empty verify_falsify (GC-4)"`
- **Enforcement**: Fail-closed validation

**DANGLING_EVIDENCE_ID**
- **Rule**: Every evidence_id in claim.evidence_ids must exist in report.evidence[]
- **Error**: `"DANGLING_EVIDENCE_ID: Claim {claim_id} references non-existent evidence_id: {eid} (GC-4)"`
- **Enforcement**: Fail-closed validation

### Additional Strict Rules

**EVIDENCE_ID_DUP_IN_CLAIM**
- **Rule**: No duplicate evidence_ids within single claim
- **Error**: `"EVIDENCE_ID_DUP_IN_CLAIM: Claim {claim_id} has duplicate evidence_ids: {duplicates} (GC-4)"`
- **Enforcement**: Fail-closed validation

**EVIDENCE_ID_EMPTY**
- **Rule**: evidence_ids entries cannot be empty or whitespace-only
- **Error**: `"EVIDENCE_ID_EMPTY: Claim {claim_id} evidence_ids[{idx}] is empty or whitespace-only (GC-4)"`
- **Enforcement**: Fail-closed validation

**EVIDENCE_IDS_WRONG_TYPE**
- **Rule**: evidence_ids must be list type
- **Error**: `"Claim {claim_id}: evidence_ids must be a list, got {type}"`
- **Enforcement**: Construction-time (Claim.__post_init__)

**EVIDENCE_ID_COLLISION**
- **Rule**: No duplicate evidence_ids in report.evidence list
- **Error**: `"Duplicate evidence_ids in evidence list: {duplicates} (GC-4: EVIDENCE_ID_COLLISION)"`
- **Enforcement**: Construction-time (ScientificReport.__post_init__)

---

## 7) Wire Parsing Posture:

### What is Accepted
- **Valid evidence_id**: Non-empty ASCII string (trimmed)
- **Valid evidence_ids**: List of valid evidence_id strings (no duplicates)
- **Empty list**: Valid for SPECULATIVE claims only

### What is Rejected
**Type Rejections**:
- None/null → `"Invalid evidence_id: None (GC-4)"`
- Non-string types (int, list, dict, bool) → `"expected string, got {type}"`
- Non-list for evidence_ids → `"expected list, got {type}"`

**Content Rejections**:
- Empty string → `"Invalid evidence_id: empty string (GC-4)"`
- Whitespace-only → `"Invalid evidence_id: {repr} is whitespace-only (GC-4)"`
- Unicode invisibles (ZWSP U+200B, NBSP U+00A0, BOM, WJ, ZWNJ, ZWJ) → `"contains invisible unicode character"`
- Non-ASCII characters → `"contains non-ASCII characters (GC-4)"`
- Duplicates within list → `"EVIDENCE_ID_DUP_IN_CLAIM"`

### How Errors Surface
1. **Wire parsing stage**: parse_evidence_id() / parse_evidence_ids()
   - Raises TypeError or ValueError immediately
   - Errors are deterministic and explicit
   
2. **Construction stage**: Claim.__post_init__() / ScientificReport.__post_init__()
   - Type validation for evidence_ids list
   - Collision detection for evidence list
   
3. **Validation stage**: EvidenceValidator.validate_report_evidence()
   - Returns (is_valid, errors) tuple
   - Collects all errors before returning
   - Errors are categorized strings

---

## 8) Fixtures Added:

### PASS Fixture (1)
**`gc4_valid_all_evidence.json`**:
- 4 claims: DERIVED (2 evidence_ids), COMPUTED (1 evidence_id), CITED (1 evidence_id), SPECULATIVE (verify_falsify)
- 2 steps: Proper step/claim structure
- 4 evidence objects: All evidence_ids resolve
- All GC-4 rules satisfied

### FAIL Fixtures (7)

| Fixture | Error Category | Description |
|---------|----------------|-------------|
| `gc4_invalid_non_spec_missing_evidence.json` | NON_SPEC_MISSING_EVIDENCE | DERIVED with empty evidence_ids |
| `gc4_invalid_spec_missing_verify_falsify.json` | SPEC_MISSING_VERIFY_FALSIFY | SPECULATIVE without verify_falsify |
| `gc4_invalid_dangling_evidence_id.json` | DANGLING_EVIDENCE_ID | References evidence-999 |
| `gc4_invalid_duplicate_evidence_ids.json` | EVIDENCE_ID_DUP_IN_CLAIM | evidence-001 appears twice |
| `gc4_invalid_evidence_ids_wrong_type.json` | EVIDENCE_IDS_WRONG_TYPE | evidence_ids is string, not list |
| `gc4_invalid_evidence_id_zwsp.json` | Wire parsing | evidence_id contains ZWSP |
| `gc4_invalid_spec_whitespace_verify_falsify.json` | SPEC_MISSING_VERIFY_FALSIFY | verify_falsify is whitespace-only |

---

## 9) Tests Added:

### Test Classes (5 classes, 36 tests)

**TestEvidenceObjectSchema (3 tests)**:
- `test_evidence_creation_valid` - Valid evidence object
- `test_evidence_id_required` - evidence_id non-empty enforcement
- `test_evidence_id_trimmed` - evidence_id trimming

**TestWireBoundaryParsing (14 tests)**:
- `test_parse_evidence_id_valid` - Valid evidence_id accepted
- `test_parse_evidence_id_rejects_none` - None rejected
- `test_parse_evidence_id_rejects_non_string` - Type validation
- `test_parse_evidence_id_rejects_empty` - Empty string rejected
- `test_parse_evidence_id_rejects_whitespace` - Whitespace-only rejected
- `test_parse_evidence_id_rejects_zwsp` - ZWSP rejected
- `test_parse_evidence_id_rejects_nbsp` - NBSP rejected
- `test_parse_evidence_id_rejects_non_ascii` - Unicode confusables rejected
- `test_parse_evidence_ids_valid` - Valid list accepted
- `test_parse_evidence_ids_empty_list_valid` - Empty list OK for SPECULATIVE
- `test_parse_evidence_ids_rejects_non_list` - Type validation
- `test_parse_evidence_ids_rejects_duplicates` - Duplicate detection
- `test_parse_evidence_ids_rejects_invalid_entry` - Invalid entry rejected

**TestEvidenceValidation (10 tests)**:
- `test_non_spec_requires_evidence_ids` - NON_SPEC_MISSING_EVIDENCE
- `test_derived_with_evidence_valid` - DERIVED with evidence OK
- `test_computed_requires_evidence` - COMPUTED needs evidence
- `test_cited_requires_evidence` - CITED needs evidence
- `test_spec_requires_verify_falsify` - SPEC_MISSING_VERIFY_FALSIFY
- `test_spec_whitespace_verify_falsify_rejected` - Whitespace rejected
- `test_spec_with_verify_falsify_valid` - SPECULATIVE with verify_falsify OK
- `test_evidence_ids_must_resolve` - DANGLING_EVIDENCE_ID
- `test_duplicate_evidence_ids_rejected` - EVIDENCE_ID_DUP_IN_CLAIM
- `test_multiple_evidence_ids_valid` - Multiple evidence_ids OK

**TestGC4Fixtures (8 tests)**:
- `test_gc4_valid_all_evidence_fixture` - Valid fixture passes
- `test_gc4_invalid_non_spec_missing_evidence_fixture` - Missing evidence fails
- `test_gc4_invalid_spec_missing_verify_falsify_fixture` - Missing verify_falsify fails
- `test_gc4_invalid_dangling_evidence_id_fixture` - Dangling evidence fails
- `test_gc4_invalid_duplicate_evidence_ids_fixture` - Duplicates fail
- `test_gc4_invalid_evidence_ids_wrong_type_fixture` - Wrong type fails
- `test_gc4_invalid_evidence_id_zwsp_fixture` - ZWSP fails at wire parsing
- `test_gc4_invalid_spec_whitespace_verify_falsify_fixture` - Whitespace fails

**TestScientificReportEvidence (2 tests)**:
- `test_report_evidence_list_valid` - Evidence list valid
- `test_report_duplicate_evidence_ids_rejected` - Collision detection

### Test Results:
```
36 GC-4 tests: PASSED
194 total tests: PASSED (0.11s)
```

**Breakdown**:
- 71 GC-1 tests (claim definition, finalization)
- 58 GC-2 tests (label validation, wire boundary)
- 29 GC-3 tests (step/claim boundary)
- 36 GC-4 tests (evidence attachment) **NEW**

---

## 10) Done/Next:

### Done ✓
- **GC-4 Evidence Attachment Rule fully implemented and frozen**
- Claim schema updated with evidence_ids and verify_falsify
- EvidenceObject minimal schema (evidence_id only)
- ScientificReport includes evidence list with collision detection
- Wire-boundary parsers with strict unicode protection
- 3 core validation rules + 4 additional strict rules
- Fail-closed enforcement with deterministic error categories
- 8 fixtures lock the contract (1 PASS + 7 FAIL)
- 36 comprehensive tests cover all validation paths
- No scope creep: evidence type semantics deferred to GC-5+
- All 194 tests pass deterministically
- First "no bluffing" gate operational

### Integration Status
- Evidence validation is standalone (can be called independently)
- Ready for finalization_check integration (GC-13)
- Blocks FINAL if any GC-4 validation errors exist

### Next ledger item: **GC-5 Evidence Object Minimum Schema**
