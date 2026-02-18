# GC-3 STEP/CLAIM BOUNDARY — IMPLEMENTATION COMPLETE ✓

## 1) Current Item:
**GC-3 Step/Claim Boundary**

---

## 2) Acceptance Checklist:
- ✅ DerivationStep schema with claim_ids (REQUIRED, NON-EMPTY)
- ✅ StepStatus enum (UNCHECKED, CHECKED, FAILED, INDETERMINATE)
- ✅ INDETERMINATE requires status_reason (enforced)
- ✅ ScientificReport schema with claims + steps
- ✅ V1: Referenced claim_ids must exist (DANGLING_CLAIM_ID)
- ✅ V2: No orphan claims (ORPHAN_CLAIM)
- ✅ V3: Unique claim ownership (DUPLICATE_CLAIM_OWNER)
- ✅ V4: Step claim_ids non-empty (EMPTY_CLAIM_IDS)
- ✅ Additional: Unique step_id (STEP_ID_COLLISION)
- ✅ Additional: Unique claim_id (CLAIM_ID_COLLISION)
- ✅ Additional: No duplicates within step.claim_ids (DUPLICATE_CLAIM_IN_STEP)
- ✅ Additional: depends_on references exist (DANGLING_STEP_DEP)
- ✅ 1 PASS fixture + 9 FAIL fixtures
- ✅ 29 comprehensive tests (all passing)
- ✅ Deterministic error reporting with categories
- ✅ CI-ready (all 158 tests pass)

---

## 3) Implementation Plan:
- **Step 1**: Define DerivationStep schema with validation ✓
- **Step 2**: Define ScientificReport schema ✓
- **Step 3**: Implement structural validators (V1-V4 + extras) ✓
- **Step 4**: Create PASS fixture ✓
- **Step 5**: Create 9 FAIL fixtures ✓
- **Step 6**: Add 29 comprehensive tests ✓
- **Step 7**: Verify all tests pass and document ✓

---

## 4) Files/Modules:

### Schema Files
- `src/core/step.py` - **NEW**: DerivationStep, StepStatus enum
- `src/core/report.py` - **NEW**: ScientificReport container

### Validator Files
- `src/core/structure_validators.py` - **NEW**: StructureValidator, ValidationError, validate_report_structure()

### Fixtures Path
- `tests/fixtures/gc3_valid_report.json` - **NEW**: Valid report
- `tests/fixtures/gc3_invalid_*.json` - **NEW**: 9 failure fixtures

### Tests Path
- `tests/test_gc3_structure.py` - **NEW**: 29 comprehensive tests

---

## 5) Schema Summary:

### DerivationStep Fields
```python
@dataclass
class DerivationStep:
    step_id: str                          # Unique identifier
    claim_ids: list[str]                  # REQUIRED, NON-EMPTY
    step_status: StepStatus               # UNCHECKED/CHECKED/FAILED/INDETERMINATE
    depends_on: list[str]                 # Optional step dependencies
    status_reason: Optional[str]          # Required if INDETERMINATE
```

**Validation** (enforced in `__post_init__`):
- claim_ids must be non-empty (V4: EMPTY_CLAIM_IDS)
- No duplicate claim_ids within step (DUPLICATE_CLAIM_IN_STEP)
- step_status must be StepStatus enum
- INDETERMINATE requires non-empty status_reason

### ScientificReport Fields
```python
@dataclass
class ScientificReport:
    claims: list[Claim]                   # From GC-1/GC-2
    steps: list[DerivationStep]           # Derivation steps
    report_id: Optional[str]              # Optional report identifier
```

**Validation** (enforced in `__post_init__`):
- No duplicate claim_ids in claims list (CLAIM_ID_COLLISION)
- No duplicate step_ids in steps list (STEP_ID_COLLISION)

---

## 6) Validator Rules Implemented:

### Core Rules (V1-V4)

**V1: Referenced claim IDs must exist** (DANGLING_CLAIM_ID)
- For every `step.claim_ids[i]`, there must exist a claim with that `claim_id`
- Fails with: `"Step references non-existent claim_id: {claim_id}"`

**V2: No orphan claims** (ORPHAN_CLAIM)
- Every `claim.claim_id` must appear in exactly one `step.claim_ids`
- If claim appears in zero steps, it's an orphan
- Fails with: `"Claim is not referenced by any step: {claim_id}"`

**V3: Unique claim ownership** (DUPLICATE_CLAIM_OWNER)
- A `claim_id` may not appear in multiple steps
- Fails with: `"Claim is owned by multiple steps: {step_ids}"`

**V4: Step claim_ids non-empty** (EMPTY_CLAIM_IDS)
- `step.claim_ids` must be non-empty list
- Enforced at construction time in `DerivationStep.__post_init__`
- Fails with: `"claim_ids cannot be empty (GC-3 V4: EMPTY_CLAIM_IDS)"`

### Additional Strict Rules

**Unique step_id** (STEP_ID_COLLISION)
- No duplicate step_ids in steps list
- Enforced in `ScientificReport.__post_init__`

**Unique claim_id** (CLAIM_ID_COLLISION)
- No duplicate claim_ids in claims list
- Enforced in `ScientificReport.__post_init__`

**No duplicates within step.claim_ids** (DUPLICATE_CLAIM_IN_STEP)
- A claim_id cannot appear multiple times in same step
- Enforced in `DerivationStep.__post_init__`

**depends_on references must exist** (DANGLING_STEP_DEP)
- If step has `depends_on`, all referenced step_ids must exist
- Fails with: `"Step depends on non-existent step_id: {step_id}"`

---

## 7) Fixtures Added:

### PASS Fixture (1)
**`gc3_valid_report.json`**:
- 3 claims (DERIVED, DERIVED, COMPUTED)
- 2 steps: step-001 owns claims 1+2, step-002 owns claim 3
- step-002 depends on step-001
- All validation rules satisfied

### FAIL Fixtures (9)

| Fixture | Error Category | Description |
|---------|----------------|-------------|
| `gc3_invalid_dangling_claim_id.json` | DANGLING_CLAIM_ID | Step references non-existent claim-999 |
| `gc3_invalid_orphan_claim.json` | ORPHAN_CLAIM | claim-002 not referenced by any step |
| `gc3_invalid_duplicate_owner.json` | DUPLICATE_CLAIM_OWNER | claim-001 in both step-001 and step-002 |
| `gc3_invalid_empty_claim_ids.json` | EMPTY_CLAIM_IDS | Step has empty claim_ids list |
| `gc3_invalid_claim_id_collision.json` | CLAIM_ID_COLLISION | Duplicate claim-001 in claims list |
| `gc3_invalid_step_id_collision.json` | STEP_ID_COLLISION | Duplicate step-001 in steps list |
| `gc3_invalid_duplicate_in_step.json` | DUPLICATE_CLAIM_IN_STEP | claim-001 appears twice in same step |
| `gc3_invalid_dangling_step_dep.json` | DANGLING_STEP_DEP | Step depends on non-existent step-999 |
| `gc3_invalid_indeterminate_no_reason.json` | (construction error) | INDETERMINATE without status_reason |

---

## 8) Tests Added:

### Test Classes (4 classes, 29 tests)

**TestDerivationStepSchema (7 tests)**:
- `test_step_creation_valid` - Valid step construction
- `test_step_claim_ids_non_empty` - V4: Empty claim_ids rejected
- `test_step_duplicate_claim_in_step_rejected` - Duplicate within step rejected
- `test_step_status_enum_required` - StepStatus enum enforced
- `test_indeterminate_requires_reason` - INDETERMINATE needs reason
- `test_indeterminate_with_reason_valid` - INDETERMINATE with reason accepted
- `test_step_create_factory` - Factory method generates step_id

**TestScientificReportSchema (3 tests)**:
- `test_report_creation_valid` - Valid report construction
- `test_claim_id_collision_rejected` - Duplicate claim_id rejected
- `test_step_id_collision_rejected` - Duplicate step_id rejected

**TestStructuralValidation (7 tests)**:
- `test_step_claim_ids_resolve` - V1: Valid references pass
- `test_dangling_claim_id_rejected` - V1: Dangling reference fails
- `test_orphan_claim_rejected` - V2: Orphan claim fails
- `test_claim_unique_owner_enforced` - V3: Duplicate owner fails
- `test_multiple_claims_single_step_valid` - Multiple claims in step OK
- `test_step_dependencies_validated` - Dangling dependency fails
- `test_valid_step_dependencies` - Valid dependencies pass

**TestGC3Fixtures (10 tests)**:
- `test_gc3_valid_report_fixture` - Valid fixture passes
- `test_gc3_invalid_dangling_claim_id_fixture` - Dangling fails
- `test_gc3_invalid_orphan_claim_fixture` - Orphan fails
- `test_gc3_invalid_duplicate_owner_fixture` - Duplicate owner fails
- `test_gc3_invalid_empty_claim_ids_fixture` - Empty claim_ids fails
- `test_gc3_invalid_claim_id_collision_fixture` - Claim collision fails
- `test_gc3_invalid_step_id_collision_fixture` - Step collision fails
- `test_gc3_invalid_duplicate_in_step_fixture` - Duplicate in step fails
- `test_gc3_invalid_dangling_step_dep_fixture` - Dangling dep fails
- `test_gc3_invalid_indeterminate_no_reason_fixture` - Missing reason fails

**TestValidationErrorReporting (2 tests)**:
- `test_validation_error_structure` - ValidationError structure verified
- `test_multiple_errors_reported` - Multiple errors reported together

### Test Results:
```
29 GC-3 tests: PASSED
158 total tests: PASSED (0.11s)
```

**Breakdown**:
- 71 GC-1 tests (claim definition, finalization)
- 58 GC-2 tests (label validation, wire boundary)
- 29 GC-3 tests (step/claim boundary) **NEW**

---

## 9) Done/Next:

### Done ✓
- **GC-3 Step/Claim Boundary fully implemented and frozen**
- DerivationStep schema with claim_ids (REQUIRED, NON-EMPTY)
- StepStatus enum with INDETERMINATE validation
- ScientificReport container for claims + steps
- Structural validators enforcing V1-V4 + additional rules
- Fail-closed validation with deterministic error categories
- 10 fixtures (1 PASS + 9 FAIL) lock the contract
- 29 comprehensive tests cover all validation paths
- No scope creep: no evidence enforcement (that's GC-4)
- No allowance for empty claim_ids (v0 strict)
- All 158 tests pass deterministically

### Next ledger item: **GC-4 Evidence Attachment Rule**
