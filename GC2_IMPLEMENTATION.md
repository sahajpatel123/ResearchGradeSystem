# GC-2 CLAIM LABELS — IMPLEMENTATION COMPLETE ✓

## 1) Current Item:
**GC-2 Claim Labels (Only 4)**

## 2) Acceptance Checklist:
- [x] ClaimLabel enum has EXACTLY 4 labels (DERIVED, COMPUTED, CITED, SPECULATIVE)
- [x] Labels are case-sensitive exact ASCII strings
- [x] Missing label validation fails with clear error
- [x] Invalid label value validation fails
- [x] Whitespace variants (leading/trailing) validation fails
- [x] Lowercase variants validation fails
- [x] List/array type validation fails
- [x] Null/None validation fails
- [x] Empty string validation fails
- [x] Valid fixture with all 4 labels created
- [x] 8 invalid fixtures created (assumed, lowercase, whitespace, null, empty, list, missing, dict)
- [x] All 29 GC-2 tests pass deterministically

## 3) Implementation Plan:
- **Step 1**: Verify ClaimLabel enum correctness (4 labels, case-sensitive) ✓
- **Step 2**: Add validation to Claim.__post_init__ (label required, type check) ✓
- **Step 3**: Create validators.py with strict validation functions ✓
- **Step 4**: Create valid fixture with all 4 label types ✓
- **Step 5**: Create 8 invalid fixtures covering all failure modes ✓
- **Step 6**: Add 29 comprehensive label validation tests ✓
- **Step 7**: Add GC-2 scope documentation to ClaimLabel enum ✓
- **Step 8**: Verify all 100 tests pass in CI-style command ✓

## 4) Files/Modules:

### Core Schema & Validation
- `src/core/claim.py` - ClaimLabel enum with GC-2 documentation, Claim validation
- `src/core/validators.py` - **NEW**: Strict label validation functions

### Tests
- `tests/test_gc2_labels.py` - **NEW**: 29 comprehensive GC-2 tests

### Fixtures (9 total)
- `tests/fixtures/gc2_valid_all_labels.json` - **NEW**: Valid with all 4 labels
- `tests/fixtures/gc2_invalid_label_assumed.json` - **NEW**: Invalid label "ASSUMED"
- `tests/fixtures/gc2_invalid_label_lowercase.json` - **NEW**: Lowercase "derived"
- `tests/fixtures/gc2_invalid_label_trailing_space.json` - **NEW**: "DERIVED "
- `tests/fixtures/gc2_invalid_label_leading_space.json` - **NEW**: " COMPUTED"
- `tests/fixtures/gc2_invalid_label_null.json` - **NEW**: null value
- `tests/fixtures/gc2_invalid_label_empty.json` - **NEW**: empty string ""
- `tests/fixtures/gc2_invalid_label_list.json` - **NEW**: list type
- `tests/fixtures/gc2_invalid_label_missing.json` - **NEW**: missing field

## 5) Schema / Validation Rules:

### Enum Values (Exact)
```python
class ClaimLabel(Enum):
    DERIVED = "DERIVED"
    COMPUTED = "COMPUTED"
    CITED = "CITED"
    SPECULATIVE = "SPECULATIVE"
```

### Rejection Rules

**Missing Label**:
- `claim_label=None` → ValueError: "Claim label is required (GC-2)"

**Invalid Type**:
- String instead of enum → TypeError: "Claim label must be ClaimLabel enum, got str"
- Integer → TypeError: "Claim label must be ClaimLabel enum, got int"
- List → TypeError: "Claim label cannot be a list (GC-2)"
- Dict → TypeError: "Claim label cannot be a dict (GC-2)"

**Invalid String Value** (when validating from string):
- "ASSUMED" → ValueError: "Invalid claim label: 'ASSUMED'. Must be one of: {DERIVED, COMPUTED, CITED, SPECULATIVE}"
- "PROVEN" → ValueError: "Invalid claim label: 'PROVEN'"

**Whitespace Variants**:
- "DERIVED " → ValueError: "Claim label has invalid whitespace: 'DERIVED '. Must be exact"
- " COMPUTED" → ValueError: "Claim label has invalid whitespace: ' COMPUTED'. Must be exact"

**Lowercase Variants**:
- "derived" → ValueError: "Claim label must be uppercase: got 'derived', expected 'DERIVED'"
- "computed" → ValueError: "Claim label must be uppercase: got 'computed', expected 'COMPUTED'"

**Empty/Null**:
- "" → ValueError: "Claim label cannot be empty string (GC-2)"
- None → ValueError: "Claim label cannot be None (GC-2)"

## 6) Fixtures Added:

### Valid Fixture (1)
**`gc2_valid_all_labels.json`**:
- 4 claims, each with different label (DERIVED, COMPUTED, CITED, SPECULATIVE)
- Demonstrates all valid labels in use
- Status: INCOMPLETE (has unsupported claims)

### Invalid Fixtures (8)

1. **`gc2_invalid_label_assumed.json`**: Label "ASSUMED" not in valid set
2. **`gc2_invalid_label_lowercase.json`**: Label "derived" is lowercase
3. **`gc2_invalid_label_trailing_space.json`**: Label "DERIVED " has trailing space
4. **`gc2_invalid_label_leading_space.json`**: Label " COMPUTED" has leading space
5. **`gc2_invalid_label_null.json`**: Label is null
6. **`gc2_invalid_label_empty.json`**: Label is empty string ""
7. **`gc2_invalid_label_list.json`**: Label is list ["DERIVED", "COMPUTED"]
8. **`gc2_invalid_label_missing.json`**: Label field missing entirely

Each invalid fixture includes expected error message in "error" field.

## 7) Tests Added:

### Test Classes (5)

**TestClaimLabelEnum (3 tests)**:
- `test_claim_label_enum_allows_only_four` - Verifies exactly 4 labels
- `test_claim_label_enum_case_sensitive` - Verifies case sensitivity
- `test_claim_label_enum_exact_strings` - Verifies no whitespace in values

**TestClaimLabelValidation (12 tests)**:
- `test_claim_label_missing_fails` - None/missing → fail
- `test_claim_label_invalid_value_fails` - "ASSUMED", "PROVEN" → fail
- `test_claim_label_trailing_space_fails` - "DERIVED " → fail
- `test_claim_label_leading_space_fails` - " CITED" → fail
- `test_claim_label_lowercase_fails` - "derived" → fail
- `test_claim_label_mixed_case_fails` - "Derived" → fail
- `test_claim_label_list_type_fails` - ["DERIVED"] → fail
- `test_claim_label_dict_type_fails` - {"label": "DERIVED"} → fail
- `test_claim_label_null_fails` - None → fail
- `test_claim_label_empty_string_fails` - "" → fail
- `test_claim_label_integer_type_fails` - 42 → fail
- `test_claim_label_valid_accepts_all_four` - All 4 valid labels accepted

**TestClaimLabelFromDict (2 tests)**:
- `test_claim_label_from_dict_missing_key_fails` - Missing 'claim_label' key → fail
- `test_claim_label_from_dict_valid` - Valid dict parsing

**TestGC2Fixtures (9 tests)**:
- `test_gc2_valid_all_labels_fixture` - Valid fixture with all 4 labels
- `test_gc2_invalid_label_assumed_fixture` - "ASSUMED" → fail
- `test_gc2_invalid_label_lowercase_fixture` - "derived" → fail
- `test_gc2_invalid_label_trailing_space_fixture` - "DERIVED " → fail
- `test_gc2_invalid_label_leading_space_fixture` - " COMPUTED" → fail
- `test_gc2_invalid_label_null_fixture` - null → fail
- `test_gc2_invalid_label_empty_fixture` - "" → fail
- `test_gc2_invalid_label_list_fixture` - list → fail
- `test_gc2_invalid_label_missing_fixture` - missing field → fail

**TestClaimConstructionWithLabels (3 tests)**:
- `test_claim_create_with_all_valid_labels` - Claim.create works with all 4 labels
- `test_claim_direct_construction_with_invalid_type` - String instead of enum → fail
- `test_claim_direct_construction_with_integer` - Integer → fail

### Test Results:
```
29 GC-2 tests passed
100 total tests passed in 0.11s
```

All tests deterministic and CI-ready.

## 8) Done/Next:

### Done ✓
- GC-2 Claim Labels fully implemented
- EXACTLY 4 labels enforced (DERIVED, COMPUTED, CITED, SPECULATIVE)
- Case-sensitive, exact ASCII strings enforced
- Fail-closed validation on missing/invalid/whitespace/lowercase/list labels
- Comprehensive validator module created
- 9 fixtures (1 valid + 8 invalid) lock the contract
- 29 tests cover all validation paths
- GC-2 scope documentation added: "GC-2 enforces label validity only. Evidence compatibility and citation requirements are enforced later by GC-4/GC-12."
- All 100 tests pass (71 from GC-1 + 29 from GC-2)
- No scope creep: no inference logic, no evidence checks, strict labels only

### Next ledger item: **GC-3 Step/Claim Boundary**
