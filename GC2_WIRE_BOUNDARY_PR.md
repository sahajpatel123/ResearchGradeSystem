# GC-2 CLEANUP PR — WIRE BOUNDARY FREEZE ✓

## Goal
Freeze GC-2 completely by hardening the JSON ingestion boundary (wire string → internal enum) with strict unicode validation and high-risk fixtures.

## Scope
- **Only GC-2 cleanup**: No inference logic, no evidence checks, no unrelated refactors
- **Labels remain EXACTLY 4** (case-sensitive): DERIVED / COMPUTED / CITED / SPECULATIVE

---

## 1) Wire Boundary Parser Implementation ✓

### Single Chokepoint: `parse_claim_label(wire: Any) -> ClaimLabel`

**Location**: `src/core/validators.py:16-120`

**Purpose**: The ONLY codepath for parsing claim labels from external sources (JSON, API, etc.)

**Strict Validation Rules**:
- ✅ Accept ONLY JSON string with exact ASCII token match
- ✅ Reject non-string types (null, list, object, number, bool)
- ✅ Reject whitespace variants (leading/trailing spaces, tabs, newlines)
- ✅ Reject unicode invisibles (ZWSP U+200B, NBSP U+00A0, BOM, Word Joiner, ZWJ, ZWNJ)
- ✅ Reject unicode confusables (Greek Epsilon, Cyrillic lookalikes, fullwidth chars)
- ✅ Reject any non-ASCII characters
- ✅ Reject casing changes (e.g., "derived")
- ✅ Reject extra tokens (e.g., "DERIVED✅")

**Error Format**: Deterministic and explicit
```python
# Examples:
"Invalid ClaimLabel: None (GC-2)"
"Invalid ClaimLabel: 'ASSUMED' (must be one of: DERIVED, COMPUTED, CITED, SPECULATIVE) (GC-2)"
"Invalid ClaimLabel: 'derived' must be uppercase (expected DERIVED) (GC-2)"
"Invalid ClaimLabel: 'DERIVED ' has invalid whitespace (GC-2)"
"Invalid ClaimLabel: 'DERIVED\u200b' contains invisible unicode character (GC-2)"
"Invalid ClaimLabel: 'DΕRIVED' contains non-ASCII characters (GC-2)"
```

---

## 2) Wire Ingestion Enforcement ✓

### Updated Ingestion Path

**`validate_claim_label_from_dict(data: dict) -> ClaimLabel`**
- **Location**: `src/core/validators.py:183-203`
- **Change**: Now delegates to `parse_claim_label()` instead of `validate_claim_label_string()`
- **Purpose**: Ensures JSON fixture loading uses the wire parser

**Code**:
```python
def validate_claim_label_from_dict(data: dict) -> ClaimLabel:
    if "claim_label" not in data:
        raise KeyError("Missing required field 'claim_label' (GC-2)")
    
    return parse_claim_label(data["claim_label"])  # Wire parser chokepoint
```

### Validation Order (Critical)
Order matters to provide specific error messages:
1. **Unicode invisibles** (ZWSP, NBSP, etc.) - checked FIRST
2. **ASCII whitespace** (spaces, tabs, newlines)
3. **Case variants** (lowercase, mixed case)
4. **Non-ASCII** (confusables, emoji)
5. **Generic invalid** (unknown label values)

---

## 3) High-Risk Unicode Fixtures ✓

### Added 3 Fixtures (All Fail Deterministically)

**1. ZWSP (Zero-Width Space U+200B)**
- **File**: `tests/fixtures/gc2_invalid_label_zwsp.json`
- **Label**: `"DERIVED\u200b"` (ZWSP embedded)
- **Error**: `"Invalid ClaimLabel: 'DERIVED\u200b' contains invisible unicode character (GC-2)"`

**2. NBSP (Non-Breaking Space U+00A0)**
- **File**: `tests/fixtures/gc2_invalid_label_nbsp.json`
- **Label**: `"CITED\u00a0"` (NBSP at end)
- **Error**: `"Invalid ClaimLabel: 'CITED\u00a0' contains invisible unicode character (GC-2)"`

**3. Unicode Confusable (Greek Epsilon)**
- **File**: `tests/fixtures/gc2_invalid_label_confusable.json`
- **Label**: `"DΕRIVED"` (Greek Epsilon Ε U+0395 instead of ASCII E)
- **Error**: `"Invalid ClaimLabel: 'DΕRIVED' contains non-ASCII characters (GC-2)"`

**All 3 fixtures**:
- ✅ Fail at wire parsing stage (before any later logic)
- ✅ Provide deterministic error messages
- ✅ Tested in `test_gc2_wire_boundary.py`

---

## 4) Tests Added ✓

### New Test File: `test_gc2_wire_boundary.py` (29 tests)

**TestParseClaimLabelWireBoundary (11 tests)**:
- `test_parse_claim_label_accepts_valid_labels` - All 4 valid labels accepted
- `test_parse_claim_label_rejects_non_string_null` - None/null rejected
- `test_parse_claim_label_rejects_non_string_bool` - Boolean rejected
- `test_parse_claim_label_rejects_non_string_number` - Numbers rejected
- `test_parse_claim_label_rejects_non_string_list` - Lists rejected
- `test_parse_claim_label_rejects_non_string_dict` - Dicts rejected
- `test_parse_claim_label_rejects_empty_string` - Empty string rejected
- `test_parse_claim_label_rejects_whitespace_leading` - Leading whitespace rejected
- `test_parse_claim_label_rejects_whitespace_trailing` - Trailing whitespace rejected
- `test_parse_claim_label_rejects_lowercase` - Lowercase rejected
- `test_parse_claim_label_rejects_invalid_label` - Invalid values rejected

**TestParseClaimLabelUnicodeInvisibles (6 tests)**:
- `test_parse_claim_label_rejects_zwsp` - ZWSP (U+200B) rejected
- `test_parse_claim_label_rejects_nbsp` - NBSP (U+00A0) rejected
- `test_parse_claim_label_rejects_bom` - BOM (U+FEFF) rejected
- `test_parse_claim_label_rejects_word_joiner` - Word Joiner (U+2060) rejected
- `test_parse_claim_label_rejects_zwnj` - ZWNJ (U+200C) rejected
- `test_parse_claim_label_rejects_zwj` - ZWJ (U+200D) rejected

**TestParseClaimLabelUnicodeConfusables (5 tests)**:
- `test_parse_claim_label_rejects_greek_epsilon` - Greek Ε instead of E
- `test_parse_claim_label_rejects_cyrillic_a` - Cyrillic А instead of A
- `test_parse_claim_label_rejects_cyrillic_i` - Cyrillic І instead of I
- `test_parse_claim_label_rejects_fullwidth_d` - Fullwidth Ｄ rejected
- `test_parse_claim_label_rejects_emoji_suffix` - Emoji suffix rejected

**TestJSONIngestionUsesWireParser (2 tests)**:
- `test_validate_claim_label_from_dict_uses_wire_parser` - Ingestion uses wire parser
- `test_json_fixture_ingestion_enforces_wire_parser` - Fixture loading enforced

**TestWireBoundaryHighRiskFixtures (3 tests)**:
- `test_gc2_invalid_label_zwsp_fixture` - ZWSP fixture fails
- `test_gc2_invalid_label_nbsp_fixture` - NBSP fixture fails
- `test_gc2_invalid_label_confusable_fixture` - Confusable fixture fails

**TestWireBoundaryIsSingleChokepoint (2 tests)**:
- `test_wire_parser_is_documented_as_chokepoint` - Documentation verified
- `test_validate_from_dict_delegates_to_wire_parser` - Delegation verified

### Updated Existing Tests
- `test_gc2_labels.py`: Updated 7 fixture tests to match new wire parser error messages

---

## 5) Changed Files Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/validators.py` | **Modified** | Added `parse_claim_label()` wire parser (16-120), updated `validate_claim_label_from_dict()` to use it |
| `tests/test_gc2_wire_boundary.py` | **NEW** | 29 comprehensive wire boundary tests |
| `tests/fixtures/gc2_invalid_label_zwsp.json` | **NEW** | ZWSP fixture |
| `tests/fixtures/gc2_invalid_label_nbsp.json` | **NEW** | NBSP fixture |
| `tests/fixtures/gc2_invalid_label_confusable.json` | **NEW** | Unicode confusable fixture |
| `tests/test_gc2_labels.py` | **Modified** | Updated 7 tests to match wire parser error messages |

---

## 6) Wire Parsing Chokepoint Details

### Where Implemented
**Function**: `parse_claim_label(wire: Any) -> ClaimLabel`  
**Location**: `src/core/validators.py:16-120`  
**Documentation**: Marked as "WIRE BOUNDARY PARSER - Single chokepoint for JSON ingestion"

### Ingestion Paths Updated
1. **`validate_claim_label_from_dict()`** - JSON fixture loading
   - **Before**: Called `validate_claim_label_string()`
   - **After**: Calls `parse_claim_label()` (wire parser)
   - **Impact**: All JSON ingestion now goes through wire parser

### Future Ingestion Points
Any future JSON/API ingestion MUST call `parse_claim_label()` directly. Do NOT:
- Use automatic enum deserialization
- Call `validate_claim_label_string()` for wire data
- Bypass the wire parser

---

## 7) Test Results

```
129 tests passed in 0.10s ✓
```

**Breakdown**:
- 71 tests from GC-1 (claim definition, finalization)
- 29 tests from GC-2 (label validation)
- 29 tests from GC-2 wire boundary (NEW)

**All tests deterministic and CI-ready.**

---

## 8) Definition of Done — GC-2 FROZEN ✓

- ✅ Single wire parser (`parse_claim_label()`) implemented
- ✅ All JSON ingestion uses wire parser
- ✅ Invalid labels fail deterministically at ingestion
- ✅ ZWSP/NBSP/confusable fixtures fail with specific errors
- ✅ 29 wire boundary tests cover all edge cases
- ✅ CI green (129 tests pass)
- ✅ No scope creep (no inference, no evidence checks)
- ✅ Labels remain EXACTLY 4 (DERIVED, COMPUTED, CITED, SPECULATIVE)

---

## 9) GC-2 Status: **FROZEN** 🔒

GC-2 is now completely frozen with:
- ✅ Canonical schema (`statement`, 4 labels)
- ✅ Validation enforcement (missing, invalid, type checks)
- ✅ **Wire boundary hardening (unicode invisibles, confusables)**
- ✅ Single chokepoint for all ingestion
- ✅ Comprehensive fixtures (12 total: 1 valid + 11 invalid)
- ✅ Comprehensive tests (58 total: 29 labels + 29 wire boundary)

**Next GC: GC-3 Step/Claim Boundary**
