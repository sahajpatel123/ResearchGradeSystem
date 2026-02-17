# Research-Grade System (RGS)

## GC-1 Claim Definition Implementation

This module implements GC-1 (Claim Definition) from the Bucket 1 Constitution with production-grade schemas, extraction logic, integrity checks, and fail-closed enforcement.

### Installation

```bash
pip install -r requirements.txt
```

### Running Tests

```bash
pytest
```

For coverage report:
```bash
pytest --cov=src --cov-report=term-missing
```

### Core Components

#### 1. Claim Schema (`src/core/claim.py`)
- **ClaimLabel**: Enum with exactly 4 labels (DERIVED, COMPUTED, CITED, SPECULATIVE)
- **Claim**: Data model with claim_id, **statement** (canonical field), claim_label, step_id, evidence_ids, claim_span
  - Validates: statement must be non-empty after trimming whitespace
- **ClaimDraft**: Intermediate representation during extraction

#### 2. ClaimExtractor (`src/core/claim_extractor.py`)
Conservative extraction following GC-1:
- Detects equations/identities in LaTeX
- Treats leak phrases ("obviously", "clearly", etc.) as claim triggers, not exemptions
- Splits multi-claim sentences
- Exempts pure variable declarations when unambiguous

```python
from src.core.claim_extractor import extract_claims

text = "The energy is E = mc^2."
latex_blocks = [r"$$F = ma$$"]
claims = extract_claims(text, latex_blocks=latex_blocks)
```

#### 3. Integrity Checks (`src/core/integrity.py`)
- **compute_unsupported_claim_rate**: GC-6 implementation (unsupported_non_spec_claims / total_non_spec_claims)
- **finalization_check**: GC-13 stub - blocks FINAL if:
  - Zero claims extracted (returns INCOMPLETE with checklist)
  - Unsupported non-SPECULATIVE claims exist

```python
from src.core.integrity import compute_unsupported_claim_rate, finalization_check
from src.core.claim import Claim, ClaimLabel

claims = [Claim.create("E = mc^2", ClaimLabel.DERIVED)]
rate = compute_unsupported_claim_rate(claims)
can_finalize, reasons = finalization_check(claims)
```

#### 4. Logging (`src/core/logging.py`)
Minimal reproducibility hooks (GC-11 friendly):
- Deterministic input hashing
- Structured JSON logs for extraction and finalization

```python
from src.core.logging import ClaimLogger

logger = ClaimLogger(log_dir="logs")
input_hash = logger.log_extraction(text, claims, run_id="run_001")
logger.log_finalization_check(claims, can_finalize, reasons, run_id="run_001")
```

### Test Coverage

- **27 positive extraction tests**: equations, assertions, theorems, implications, etc.
- **14 negative tests**: definitions, leak phrases, splitting, edge cases
- **6 unsupported-claim rate tests**: various support scenarios
- **5 finalization check tests**: blocking conditions (including zero-claims rule)
- **3 fixture validation tests**: INCOMPLETE valid, whitespace invalid, zero-claims
- **8 whitespace validation tests**: empty/whitespace-only statement rejection
- **4 zero-claims finalization tests**: blocking, checklist, speculative-only
- **10 logging tests**: deterministic hashing, extraction/finalization logging

Total: **71 deterministic tests**

### Fail-Closed Behavior

**Blocking Conditions**:
1. **Zero claims extracted**: System must NOT silently finalize
   - Returns INCOMPLETE with checklist asking for derivation steps, equations, or explicit "no derivation possible yet"
2. **Unsupported non-SPECULATIVE claims**: Any non-SPECULATIVE claim without evidence (empty evidence_ids)

**Result**: 
- `finalization_check()` returns `(False, reasons_list)`
- Status: INCOMPLETE or CANNOT_FINALIZE
- Reasons include: blocking condition, unsupported claim count/rate, sample claims, or checklist

### Next Steps

Next ledger item: **1) Multiform Input Support**
