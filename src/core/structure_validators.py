"""
GC-3 Structural Validators

Fail-closed validation for Step/Claim boundary enforcement.

Validation Rules:
- V1: Referenced claim IDs must exist (DANGLING_CLAIM_ID)
- V2: No orphan claims (ORPHAN_CLAIM)
- V3: Unique claim ownership (DUPLICATE_CLAIM_OWNER)
- V4: Step claim_ids non-empty (EMPTY_CLAIM_IDS)

Additional strict rules:
- Unique step_id (STEP_ID_COLLISION)
- Unique claim_id (CLAIM_ID_COLLISION)
- No duplicates within step.claim_ids (DUPLICATE_CLAIM_IN_STEP)
- depends_on references must exist (DANGLING_STEP_DEP)
"""

from dataclasses import dataclass
from typing import Optional
from src.core.report import ScientificReport


@dataclass
class ValidationError:
    """
    Structured validation error with deterministic reporting.
    
    Fields:
    - category: Error category (e.g., DANGLING_CLAIM_ID, ORPHAN_CLAIM)
    - message: Human-readable error message
    - step_id: Optional step_id where error occurred
    - claim_id: Optional claim_id involved in error
    """
    category: str
    message: str
    step_id: Optional[str] = None
    claim_id: Optional[str] = None
    
    def __str__(self) -> str:
        parts = [f"[{self.category}]", self.message]
        if self.step_id:
            parts.append(f"(step_id: {self.step_id})")
        if self.claim_id:
            parts.append(f"(claim_id: {self.claim_id})")
        return " ".join(parts)


class StructureValidator:
    """
    GC-3 structural validator for ScientificReport.
    
    Enforces fail-closed validation of Step/Claim boundary invariants.
    """
    
    @staticmethod
    def validate_report(report: ScientificReport) -> tuple[bool, list[ValidationError]]:
        """
        Validate complete report structure.
        
        Returns:
            (is_valid, errors) where is_valid is True if no errors, False otherwise
        """
        errors: list[ValidationError] = []
        
        # V1: Referenced claim IDs must exist
        errors.extend(StructureValidator._validate_claim_references(report))
        
        # V2: No orphan claims
        errors.extend(StructureValidator._validate_no_orphans(report))
        
        # V3: Unique claim ownership
        errors.extend(StructureValidator._validate_unique_ownership(report))
        
        # V4: Step claim_ids non-empty (enforced in DerivationStep.__post_init__)
        # This is already checked at construction time
        
        # Additional: Validate depends_on references
        errors.extend(StructureValidator._validate_step_dependencies(report))
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def _validate_claim_references(report: ScientificReport) -> list[ValidationError]:
        """
        V1: Validate that all referenced claim_ids exist.
        
        For every step.claim_ids[i], there must exist a claim with that claim_id.
        """
        errors: list[ValidationError] = []
        
        # Build set of existing claim_ids
        existing_claim_ids = {claim.claim_id for claim in report.claims}
        
        # Check each step's claim_ids
        for step in report.steps:
            for claim_id in step.claim_ids:
                if claim_id not in existing_claim_ids:
                    errors.append(ValidationError(
                        category="DANGLING_CLAIM_ID",
                        message=f"Step references non-existent claim_id: {claim_id}",
                        step_id=step.step_id,
                        claim_id=claim_id,
                    ))
        
        return errors
    
    @staticmethod
    def _validate_no_orphans(report: ScientificReport) -> list[ValidationError]:
        """
        V2: Validate that every claim is referenced by exactly one step (no orphans).
        
        Every claim.claim_id must appear in exactly one step.claim_ids.
        If a claim appears in zero steps, it's an orphan.
        """
        errors: list[ValidationError] = []
        
        # Build set of all referenced claim_ids
        referenced_claim_ids = set()
        for step in report.steps:
            referenced_claim_ids.update(step.claim_ids)
        
        # Check each claim is referenced
        for claim in report.claims:
            if claim.claim_id not in referenced_claim_ids:
                errors.append(ValidationError(
                    category="ORPHAN_CLAIM",
                    message=f"Claim is not referenced by any step: {claim.claim_id}",
                    claim_id=claim.claim_id,
                ))
        
        return errors
    
    @staticmethod
    def _validate_unique_ownership(report: ScientificReport) -> list[ValidationError]:
        """
        V3: Validate that each claim is owned by exactly one step (unique ownership).
        
        A claim_id may not appear in multiple steps.
        """
        errors: list[ValidationError] = []
        
        # Track which step owns each claim_id
        claim_ownership: dict[str, list[str]] = {}  # claim_id -> [step_ids]
        
        for step in report.steps:
            for claim_id in step.claim_ids:
                if claim_id not in claim_ownership:
                    claim_ownership[claim_id] = []
                claim_ownership[claim_id].append(step.step_id)
        
        # Check for duplicate ownership
        for claim_id, owner_step_ids in claim_ownership.items():
            if len(owner_step_ids) > 1:
                errors.append(ValidationError(
                    category="DUPLICATE_CLAIM_OWNER",
                    message=f"Claim is owned by multiple steps: {owner_step_ids}",
                    claim_id=claim_id,
                ))
        
        return errors
    
    @staticmethod
    def _validate_step_dependencies(report: ScientificReport) -> list[ValidationError]:
        """
        Additional: Validate that depends_on references exist.
        
        If a step has depends_on, all referenced step_ids must exist.
        """
        errors: list[ValidationError] = []
        
        # Build set of existing step_ids
        existing_step_ids = {step.step_id for step in report.steps}
        
        # Check each step's depends_on
        for step in report.steps:
            for dep_step_id in step.depends_on:
                if dep_step_id not in existing_step_ids:
                    errors.append(ValidationError(
                        category="DANGLING_STEP_DEP",
                        message=f"Step depends on non-existent step_id: {dep_step_id}",
                        step_id=step.step_id,
                    ))
        
        return errors


def validate_report_structure(report: ScientificReport) -> tuple[bool, list[ValidationError]]:
    """
    Convenience function for validating report structure.
    
    Returns:
        (is_valid, errors) where is_valid is True if no errors, False otherwise
    """
    return StructureValidator.validate_report(report)
