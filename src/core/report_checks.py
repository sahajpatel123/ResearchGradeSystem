"""
GC-13 Report Checks Schema: Closed v0 Check Registry.

Defines the ReportChecks schema with a closed set of required checks.
All checks must be explicitly present; omission is failure.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CheckStatus(Enum):
    """
    GC-13 check status enum.
    
    Allowed values (closed set):
    - PASS: Check passed
    - FAIL: Check failed
    - INDETERMINATE: Check could not determine pass/fail
    - NOT_RUN: Check was not executed
    - NOT_APPLICABLE: Check does not apply to this report (requires reason)
    """
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReportStatus(Enum):
    """
    GC-13 report status enum.
    
    Computed-only; never trusted from wire.
    """
    FINAL = "FINAL"
    INCOMPLETE = "INCOMPLETE"


@dataclass
class CheckResult:
    """
    GC-13 check result.
    
    Fields:
    - status: CheckStatus (required)
    - reason: str (REQUIRED if status == NOT_APPLICABLE)
    - payload_ref: Optional reference to check payload
    """
    status: CheckStatus
    reason: Optional[str] = None
    payload_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CheckStatus):
            raise TypeError(
                f"status must be CheckStatus, got {type(self.status).__name__} "
                "(GC-13: CHECK_STATUS_INVALID)"
            )
        if self.status == CheckStatus.NOT_APPLICABLE:
            if self.reason is None:
                raise ValueError(
                    "reason is required when status is NOT_APPLICABLE "
                    "(GC-13: CHECK_NOT_APPLICABLE_MISSING_REASON)"
                )
            if not isinstance(self.reason, str):
                raise TypeError(
                    f"reason must be str, got {type(self.reason).__name__} "
                    "(GC-13: CHECK_NOT_APPLICABLE_MISSING_REASON)"
                )
            if self.reason.strip() == "":
                raise ValueError(
                    "reason must be non-empty (not whitespace-only) when status is NOT_APPLICABLE "
                    "(GC-13: CHECK_NOT_APPLICABLE_MISSING_REASON)"
                )


# Closed v0 check registry - these are the ONLY allowed check fields
REQUIRED_CHECK_FIELDS = frozenset([
    "units_check",
    "limits_check",
    "numeric_check",
    "critic_check",
    "known_result_check",
])


@dataclass
class ReportChecks:
    """
    GC-13 report checks (closed v0 set).
    
    All 5 check fields MUST be present. Omission is failure.
    No extra ad hoc check fields allowed.
    
    Required checks:
    - units_check: Dimensional analysis / unit consistency
    - limits_check: Boundary condition / limit checks
    - numeric_check: Numerical verification
    - critic_check: Critical review / sanity check
    - known_result_check: Comparison against known results
    """
    units_check: CheckResult
    limits_check: CheckResult
    numeric_check: CheckResult
    critic_check: CheckResult
    known_result_check: CheckResult

    def __post_init__(self) -> None:
        if not isinstance(self.units_check, CheckResult):
            raise TypeError(
                f"units_check must be CheckResult, got {type(self.units_check).__name__} "
                "(GC-13: CHECK_STATUS_MISSING)"
            )
        if not isinstance(self.limits_check, CheckResult):
            raise TypeError(
                f"limits_check must be CheckResult, got {type(self.limits_check).__name__} "
                "(GC-13: CHECK_STATUS_MISSING)"
            )
        if not isinstance(self.numeric_check, CheckResult):
            raise TypeError(
                f"numeric_check must be CheckResult, got {type(self.numeric_check).__name__} "
                "(GC-13: CHECK_STATUS_MISSING)"
            )
        if not isinstance(self.critic_check, CheckResult):
            raise TypeError(
                f"critic_check must be CheckResult, got {type(self.critic_check).__name__} "
                "(GC-13: CHECK_STATUS_MISSING)"
            )
        if not isinstance(self.known_result_check, CheckResult):
            raise TypeError(
                f"known_result_check must be CheckResult, got {type(self.known_result_check).__name__} "
                "(GC-13: CHECK_STATUS_MISSING)"
            )

    def get_all_checks(self) -> dict[str, CheckResult]:
        """Return all checks as a dictionary."""
        return {
            "units_check": self.units_check,
            "limits_check": self.limits_check,
            "numeric_check": self.numeric_check,
            "critic_check": self.critic_check,
            "known_result_check": self.known_result_check,
        }

    def has_any_failure(self) -> bool:
        """Check if any check has FAIL status."""
        return any(
            check.status == CheckStatus.FAIL
            for check in self.get_all_checks().values()
        )
