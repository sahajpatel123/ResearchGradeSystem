"""
GC-6 Integrity Metrics Validators

Enforces computed-only policy for integrity metrics.
Metrics must be recomputed and validated against wire values if present.
"""

from typing import Optional
from src.core.report import ScientificReport
from src.core.integrity_metrics import (
    IntegrityMetrics,
    compute_integrity_metrics,
    compute_speculative_flood_warning,
)
from src.core.evidence import EvidenceObject


def validate_and_compute_integrity_metrics(
    report: ScientificReport,
    evidence_by_id: Optional[dict[str, EvidenceObject]] = None
) -> tuple[bool, list[str]]:
    """
    GC-6: Validate and compute integrity metrics for a report.
    
    This enforces the COMPUTED-ONLY policy:
    1. Recompute metrics from claims and evidence (DEFENSIVE - never crashes)
    2. If report.integrity_metrics is present:
       - Compare with computed metrics
       - FAIL on mismatch (INTEGRITY_METRICS_MISMATCH)
    3. If report.integrity_metrics is None:
       - Set it to computed metrics
    4. Compute warnings (SPECULATIVE_FLOOD_WARNING)
    
    Args:
        report: ScientificReport to validate
        evidence_by_id: Map of evidence_id -> EvidenceObject (may be None/malformed)
    
    Returns:
        (is_valid, errors) tuple
    """
    errors = []
    
    # Compute ground truth metrics (DEFENSIVE - never crashes, even on malformed reports)
    computed_metrics = compute_integrity_metrics(report.claims, evidence_by_id)
    
    # If metrics present on wire, validate against computed
    if report.integrity_metrics is not None:
        wire_metrics = report.integrity_metrics
        
        # Check ints match (canonical source of truth)
        if wire_metrics.unsupported_non_spec_claims != computed_metrics.unsupported_non_spec_claims:
            errors.append(
                f"GC-6: INTEGRITY_METRICS_MISMATCH: unsupported_non_spec_claims "
                f"wire={wire_metrics.unsupported_non_spec_claims} != "
                f"computed={computed_metrics.unsupported_non_spec_claims}"
            )
        
        if wire_metrics.total_non_spec_claims != computed_metrics.total_non_spec_claims:
            errors.append(
                f"GC-6: INTEGRITY_METRICS_MISMATCH: total_non_spec_claims "
                f"wire={wire_metrics.total_non_spec_claims} != "
                f"computed={computed_metrics.total_non_spec_claims}"
            )
        
        # Check unsupported_claim_ids match (set equality, deterministic order)
        if set(wire_metrics.unsupported_claim_ids) != set(computed_metrics.unsupported_claim_ids):
            errors.append(
                f"GC-6: INTEGRITY_METRICS_MISMATCH: unsupported_claim_ids "
                f"wire={sorted(wire_metrics.unsupported_claim_ids)} != "
                f"computed={sorted(computed_metrics.unsupported_claim_ids)}"
            )
        
        # Check rate matches (derived from ints, epsilon tolerance)
        epsilon = 1e-9
        if abs(wire_metrics.unsupported_claim_rate - computed_metrics.unsupported_claim_rate) > epsilon:
            errors.append(
                f"GC-6: INTEGRITY_METRICS_MISMATCH: unsupported_claim_rate "
                f"wire={wire_metrics.unsupported_claim_rate} != "
                f"computed={computed_metrics.unsupported_claim_rate}"
            )
        
        if errors:
            return False, errors
    
    # Set computed metrics (overwrite or set if None)
    report.integrity_metrics = computed_metrics
    
    # Compute warnings (warning-only, does not fail validation)
    warning = compute_speculative_flood_warning(report.claims)
    if warning:
        report.integrity_warnings.append(warning)
    
    return True, []


def validate_report_with_integrity(report: ScientificReport) -> tuple[bool, list[str]]:
    """
    GC-6: Full report validation including integrity metrics.
    
    Validation order (MUST be explicit):
    1. GC-5: Validate EvidenceObjects (typed, strict)
    2. GC-4: Validate claim evidence attachment + resolution
    3. GC-6: Compute and validate integrity metrics
    
    Returns:
        (is_valid, errors) tuple
    """
    from src.core.evidence_validators import validate_evidence_attachment
    
    errors = []
    
    # Step 1: GC-5 validation (EvidenceObjects are typed and valid)
    # Build evidence_by_id map from validated evidence
    evidence_by_id = {}
    for evidence_obj in report.evidence:
        # Evidence objects are already GC-5 validated at construction
        # (via __post_init__ in EvidenceObject)
        evidence_by_id[evidence_obj.evidence_id] = evidence_obj
    
    # Step 2: GC-4 validation (evidence attachment + resolution)
    is_valid_gc4, gc4_errors = validate_evidence_attachment(report)
    if not is_valid_gc4:
        errors.extend(gc4_errors)
    
    # Step 3: GC-6 validation (integrity metrics)
    is_valid_gc6, gc6_errors = validate_and_compute_integrity_metrics(report, evidence_by_id)
    if not is_valid_gc6:
        errors.extend(gc6_errors)
    
    # Return overall validation result
    is_valid = is_valid_gc4 and is_valid_gc6
    return is_valid, errors


def can_finalize_report(report: ScientificReport) -> tuple[bool, list[str]]:
    """
    GC-6: Check if report can be finalized.
    
    FINAL is blocked if:
    - Any GC-5 errors exist (invalid EvidenceObjects)
    - Any GC-4 errors exist (missing evidence, dangling evidence_ids)
    - Any GC-6 errors exist (metrics mismatch)
    - Zero claims (GC-1)
    - Unsupported claims exist (GC-6)
    
    Returns:
        (can_finalize, blockers) tuple
    """
    blockers = []
    
    # Run full validation (GC-5 -> GC-4 -> GC-6)
    is_valid, errors = validate_report_with_integrity(report)
    if not is_valid:
        blockers.extend(errors)
        return False, blockers
    
    # Check zero claims (GC-1)
    if len(report.claims) == 0:
        blockers.append("GC-1: Cannot finalize report with zero claims")
        return False, blockers
    
    # Check unsupported claims (GC-6)
    if report.integrity_metrics is None:
        blockers.append("GC-6: integrity_metrics not computed")
        return False, blockers
    
    if report.integrity_metrics.unsupported_non_spec_claims > 0:
        blockers.append(
            f"GC-6: Cannot finalize with {report.integrity_metrics.unsupported_non_spec_claims} "
            f"unsupported non-SPECULATIVE claims: {report.integrity_metrics.unsupported_claim_ids}"
        )
        return False, blockers
    
    return True, []
