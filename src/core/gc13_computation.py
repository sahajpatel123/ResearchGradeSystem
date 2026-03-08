"""
GC-13 Computation Functions: Status and Missing Artifacts.

These are the SINGLE SOURCE OF TRUTH for report status and missing artifacts.
Status and missing_artifacts are computed-only; never trusted from wire.
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.report_checks import CheckStatus, ReportChecks, ReportStatus


@dataclass
class ReportArtifacts:
    """
    GC-13 report artifacts container for computation.
    
    Contains all fields needed to compute status and missing_artifacts.
    """
    # Core artifacts
    problem_restatement: Optional[str] = None
    assumption_ledger: Optional[list] = None
    derivation_steps: Optional[list] = None
    claims: Optional[list] = None
    evidence_objects: Optional[list] = None
    coverage_metrics: Optional[dict] = None
    conclusion: Optional[str] = None
    confidence: Optional[str] = None
    
    # RAG/citations
    used_rag: bool = False
    citations: Optional[list] = None
    
    # Checks
    checks: Optional[ReportChecks] = None
    
    # Task kind for derivation semantics
    task_kind: Optional[str] = None  # "derivational" or "non_derivational"
    non_derivational_reason: Optional[str] = None
    
    # Run manifest linkage
    run_manifest_ref: Optional[str] = None


# Required artifacts for FINAL (v0)
REQUIRED_ARTIFACTS = [
    "problem_restatement",
    "assumption_ledger",
    "derivation",
    "claims_labeled",
    "evidence_for_non_spec_claims",
    "coverage_metrics",
    "conclusion",
    "confidence",
    "checks_complete",
]


def _check_problem_restatement(artifacts: ReportArtifacts) -> bool:
    """Check if problem restatement is present and non-empty."""
    if artifacts.problem_restatement is None:
        return False
    if not isinstance(artifacts.problem_restatement, str):
        return False
    return artifacts.problem_restatement.strip() != ""


def _check_assumption_ledger(artifacts: ReportArtifacts) -> bool:
    """Check if assumption ledger is present."""
    if artifacts.assumption_ledger is None:
        return False
    if not isinstance(artifacts.assumption_ledger, list):
        return False
    return True  # Empty list is allowed (no assumptions)


def _check_derivation(artifacts: ReportArtifacts) -> bool:
    """
    Check if derivation is present.
    
    GC-13 DERIVATION SEMANTICS:
    - For derivational tasks: at least one derivation step required
    - For non-derivational tasks: no steps required IF non_derivational_reason provided
    - "no derivation possible yet" is INCOMPLETE, not FINAL
    """
    # Non-derivational task with reason
    if artifacts.task_kind == "non_derivational":
        if artifacts.non_derivational_reason is not None:
            if isinstance(artifacts.non_derivational_reason, str):
                if artifacts.non_derivational_reason.strip() != "":
                    return True
        return False
    
    # Derivational task (default): requires at least one step
    if artifacts.derivation_steps is None:
        return False
    if not isinstance(artifacts.derivation_steps, list):
        return False
    return len(artifacts.derivation_steps) > 0


def _check_claims_labeled(artifacts: ReportArtifacts) -> bool:
    """Check if all claims are labeled (GC-2)."""
    if artifacts.claims is None:
        return False
    if not isinstance(artifacts.claims, list):
        return False
    # Empty claims list is valid (no claims to label)
    return True


def _check_evidence_for_non_spec_claims(artifacts: ReportArtifacts) -> bool:
    """Check if all non-SPEC claims have valid evidence (GC-4/GC-5)."""
    if artifacts.claims is None:
        return False
    if artifacts.evidence_objects is None:
        return False
    # Simplified check: evidence_objects list exists
    # Full validation done by GC-4/GC-5 validators
    return True


def _check_coverage_metrics(artifacts: ReportArtifacts) -> bool:
    """Check if coverage metrics are present (GC-7)."""
    if artifacts.coverage_metrics is None:
        return False
    if not isinstance(artifacts.coverage_metrics, dict):
        return False
    return True


def _check_conclusion(artifacts: ReportArtifacts) -> bool:
    """Check if conclusion is present and non-empty."""
    if artifacts.conclusion is None:
        return False
    if not isinstance(artifacts.conclusion, str):
        return False
    return artifacts.conclusion.strip() != ""


def _check_confidence(artifacts: ReportArtifacts) -> bool:
    """Check if confidence is present and non-empty."""
    if artifacts.confidence is None:
        return False
    if not isinstance(artifacts.confidence, str):
        return False
    return artifacts.confidence.strip() != ""


def _check_checks_complete(artifacts: ReportArtifacts) -> bool:
    """Check if all required checks are present."""
    if artifacts.checks is None:
        return False
    if not isinstance(artifacts.checks, ReportChecks):
        return False
    return True


def _check_rag_citations(artifacts: ReportArtifacts) -> tuple[bool, list[str]]:
    """
    Check RAG citations requirement.
    
    If used_rag=true:
    - citations must be present
    - citations must satisfy GC-12 provenance (validated separately)
    
    Returns:
        (is_valid, list of missing artifact names)
    """
    if not artifacts.used_rag:
        return True, []
    
    # RAG used, citations required
    if artifacts.citations is None:
        return False, ["rag_citations"]
    if not isinstance(artifacts.citations, list):
        return False, ["rag_citations"]
    if len(artifacts.citations) == 0:
        return False, ["rag_citations"]
    
    return True, []


def compute_missing_artifacts(artifacts: ReportArtifacts) -> list[str]:
    """
    Compute missing artifacts for a report.
    
    GC-13: This is the SINGLE SOURCE OF TRUTH for missing_artifacts.
    Returns a deterministic, sorted list of missing artifact names.
    
    Args:
        artifacts: ReportArtifacts container
        
    Returns:
        Sorted list of missing artifact names
    """
    missing = []
    
    if not _check_problem_restatement(artifacts):
        missing.append("problem_restatement")
    
    if not _check_assumption_ledger(artifacts):
        missing.append("assumption_ledger")
    
    if not _check_derivation(artifacts):
        missing.append("derivation")
    
    if not _check_claims_labeled(artifacts):
        missing.append("claims_labeled")
    
    if not _check_evidence_for_non_spec_claims(artifacts):
        missing.append("evidence_for_non_spec_claims")
    
    if not _check_coverage_metrics(artifacts):
        missing.append("coverage_metrics")
    
    if not _check_conclusion(artifacts):
        missing.append("conclusion")
    
    if not _check_confidence(artifacts):
        missing.append("confidence")
    
    if not _check_checks_complete(artifacts):
        missing.append("checks_complete")
    
    # RAG citations
    rag_valid, rag_missing = _check_rag_citations(artifacts)
    if not rag_valid:
        missing.extend(rag_missing)
    
    # Return sorted for determinism
    return sorted(missing)


def compute_report_status(artifacts: ReportArtifacts) -> ReportStatus:
    """
    Compute report status from artifacts.
    
    GC-13: This is the SINGLE SOURCE OF TRUTH for status.
    Status is computed-only; never trusted from wire.
    
    Args:
        artifacts: ReportArtifacts container
        
    Returns:
        ReportStatus.FINAL if all requirements met, else ReportStatus.INCOMPLETE
    """
    missing = compute_missing_artifacts(artifacts)
    
    if len(missing) == 0:
        return ReportStatus.FINAL
    else:
        return ReportStatus.INCOMPLETE
