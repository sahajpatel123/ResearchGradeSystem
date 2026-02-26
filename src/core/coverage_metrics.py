"""
GC-7 Coverage Metrics (Computed-Only, Fail-Closed)

Step-level verification bookkeeping with deterministic computation and tamper-resistance.
Coverage metrics are computed from report.steps and MUST NOT be trusted from wire.
"""

from dataclasses import dataclass
from typing import Optional
from src.core.step import DerivationStep, StepStatus


@dataclass
class UncheckedStepItem:
    """
    Item in unchecked_steps bucket.
    
    Represents a step that is either unchecked or indeterminate.
    """
    step_id: str
    kind: str  # "unchecked" | "indeterminate"
    reason: Optional[str] = None  # Present for indeterminate


@dataclass
class FailedStepItem:
    """
    Item in failed_steps bucket.
    
    Represents a step that failed verification.
    """
    step_id: str
    reason: Optional[str] = None


@dataclass
class CoverageMetrics:
    """
    GC-7: Step verification coverage metrics (computed-only).
    
    All fields are computed from report.steps and MUST match recomputation.
    Wire-provided coverage metrics trigger MISMATCH errors if they differ.
    
    Fields:
    - checked_steps: Sorted list of step_ids with status=checked
    - unchecked_steps: List of unchecked + indeterminate steps (with kind/reason)
    - failed_steps: List of failed steps (with optional reason)
    - checked_count: Number of checked steps
    - unchecked_count: Number of unchecked + indeterminate steps
    - failed_count: Number of failed steps
    - total_steps: Total number of steps in report
    - verification_progress_ratio: checked / (checked + unchecked)
    - verified_work_pct: checked / total_steps
    - coverage_note: Required if total_steps == 0, explains zero-step edge case
    """
    checked_steps: list[str]
    unchecked_steps: list[UncheckedStepItem]
    failed_steps: list[FailedStepItem]
    checked_count: int
    unchecked_count: int
    failed_count: int
    total_steps: int
    verification_progress_ratio: float
    verified_work_pct: float
    coverage_note: Optional[str] = None
    
    def __post_init__(self):
        """Validate CoverageMetrics internal consistency."""
        # Counts must match bucket lengths
        if self.checked_count != len(self.checked_steps):
            raise ValueError(
                f"CoverageMetrics: checked_count ({self.checked_count}) != len(checked_steps) ({len(self.checked_steps)})"
            )
        if self.unchecked_count != len(self.unchecked_steps):
            raise ValueError(
                f"CoverageMetrics: unchecked_count ({self.unchecked_count}) != len(unchecked_steps) ({len(self.unchecked_steps)})"
            )
        if self.failed_count != len(self.failed_steps):
            raise ValueError(
                f"CoverageMetrics: failed_count ({self.failed_count}) != len(failed_steps) ({len(self.failed_steps)})"
            )
        
        # total_steps must equal sum of all counts
        expected_total = self.checked_count + self.unchecked_count + self.failed_count
        if self.total_steps != expected_total:
            raise ValueError(
                f"CoverageMetrics: total_steps ({self.total_steps}) != sum of counts ({expected_total})"
            )
        
        # Zero-step edge case: coverage_note REQUIRED
        if self.total_steps == 0 and not self.coverage_note:
            raise ValueError(
                "CoverageMetrics: coverage_note REQUIRED when total_steps == 0 (GC-7: COVERAGE_NOTE_MISSING_ZERO_STEPS)"
            )
        
        # Validate ratios are in [0.0, 1.0]
        if not (0.0 <= self.verification_progress_ratio <= 1.0):
            raise ValueError(
                f"CoverageMetrics: verification_progress_ratio ({self.verification_progress_ratio}) not in [0.0, 1.0]"
            )
        if not (0.0 <= self.verified_work_pct <= 1.0):
            raise ValueError(
                f"CoverageMetrics: verified_work_pct ({self.verified_work_pct}) not in [0.0, 1.0]"
            )
        
        # Validate no NaN/Infinity
        import math
        if math.isnan(self.verification_progress_ratio) or math.isinf(self.verification_progress_ratio):
            raise ValueError(
                f"CoverageMetrics: verification_progress_ratio is NaN/Infinity (GC-7: COVERAGE_INVALID_NUMBER)"
            )
        if math.isnan(self.verified_work_pct) or math.isinf(self.verified_work_pct):
            raise ValueError(
                f"CoverageMetrics: verified_work_pct is NaN/Infinity (GC-7: COVERAGE_INVALID_NUMBER)"
            )


def compute_coverage_metrics(steps: list[DerivationStep]) -> CoverageMetrics:
    """
    Compute coverage metrics from report steps (GC-7).
    
    Single source of truth for coverage bookkeeping. Builds buckets from step_status only.
    
    Rules:
    1) Bucket assignment:
       - checked_steps <- step_status == checked
       - unchecked_steps <- step_status in {unchecked, indeterminate}
       - failed_steps <- step_status == failed
    2) Counts derived from bucket lengths
    3) total_steps = len(steps)
    4) verification_progress_ratio:
       - denom = checked_count + unchecked_count
       - if denom == 0 -> 0.0 (all failed or zero steps)
       - else checked_count / denom
    5) verified_work_pct:
       - 0.0 if total_steps == 0
       - else checked_count / total_steps
    6) Determinism:
       - checked_steps sorted lexicographically
       - unchecked_steps sorted by step_id
       - failed_steps sorted by step_id
       - no duplicates
    7) Zero-step edge case:
       - all counts = 0
       - ratios = 0.0
       - coverage_note = "No derivation steps present; coverage set to 0.0"
    
    Args:
        steps: List of DerivationStep objects from report
    
    Returns:
        CoverageMetrics with computed buckets, counts, and ratios
    """
    # Build buckets from step_status
    checked_steps: list[str] = []
    unchecked_steps: list[UncheckedStepItem] = []
    failed_steps: list[FailedStepItem] = []
    
    for step in steps:
        if step.step_status == StepStatus.CHECKED:
            checked_steps.append(step.step_id)
        elif step.step_status in (StepStatus.UNCHECKED, StepStatus.INDETERMINATE):
            kind = "unchecked" if step.step_status == StepStatus.UNCHECKED else "indeterminate"
            unchecked_steps.append(UncheckedStepItem(
                step_id=step.step_id,
                kind=kind,
                reason=step.status_reason if step.step_status == StepStatus.INDETERMINATE else None
            ))
        elif step.step_status == StepStatus.FAILED:
            failed_steps.append(FailedStepItem(
                step_id=step.step_id,
                reason=step.status_reason  # Optional for failed
            ))
    
    # Sort buckets for determinism
    checked_steps.sort()
    unchecked_steps.sort(key=lambda x: x.step_id)
    failed_steps.sort(key=lambda x: x.step_id)
    
    # Compute counts
    checked_count = len(checked_steps)
    unchecked_count = len(unchecked_steps)
    failed_count = len(failed_steps)
    total_steps = len(steps)
    
    # Compute verification_progress_ratio
    denom = checked_count + unchecked_count
    if denom == 0:
        verification_progress_ratio = 0.0
    else:
        verification_progress_ratio = checked_count / denom
    
    # Compute verified_work_pct
    if total_steps == 0:
        verified_work_pct = 0.0
    else:
        verified_work_pct = checked_count / total_steps
    
    # Zero-step edge case: coverage_note REQUIRED
    coverage_note = None
    if total_steps == 0:
        coverage_note = "No derivation steps present; coverage set to 0.0"
    
    return CoverageMetrics(
        checked_steps=checked_steps,
        unchecked_steps=unchecked_steps,
        failed_steps=failed_steps,
        checked_count=checked_count,
        unchecked_count=unchecked_count,
        failed_count=failed_count,
        total_steps=total_steps,
        verification_progress_ratio=verification_progress_ratio,
        verified_work_pct=verified_work_pct,
        coverage_note=coverage_note,
    )
