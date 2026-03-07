"""
GC-11 RunManifest Schema: Reproducibility + Determinism Contract.

Defines the RunManifest and LogReference schemas for making every run
replayable and auditable.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class LogType(Enum):
    """
    GC-11 frozen log type enum (v0).
    
    Allowed types for log references in RunManifest.
    """
    NUMERIC = "numeric"
    CAS = "cas"
    RETRIEVAL = "retrieval"
    BRANCH = "branch"
    FAILURE_LOCALIZATION = "failure_localization"


@dataclass
class LogReference:
    """
    GC-11 typed log reference.
    
    Each log reference must:
    - Have a valid log_id (strict token)
    - Have a typed log_type from frozen enum
    - Have a valid payload_ref (strict token)
    - Resolve in ArtifactRegistry with matching type
    """
    log_id: str
    log_type: LogType
    payload_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.log_id, str):
            raise TypeError(
                f"log_id must be str, got {type(self.log_id).__name__} "
                "(GC-11: LOG_REFERENCE_INVALID)"
            )
        if self.log_id == "":
            raise ValueError(
                "log_id must be non-empty (GC-11: LOG_REFERENCE_INVALID)"
            )
        if not isinstance(self.log_type, LogType):
            raise TypeError(
                f"log_type must be LogType enum, got {type(self.log_type).__name__} "
                "(GC-11: LOG_REFERENCE_INVALID)"
            )
        if not isinstance(self.payload_ref, str):
            raise TypeError(
                f"payload_ref must be str, got {type(self.payload_ref).__name__} "
                "(GC-11: LOG_REFERENCE_INVALID)"
            )
        if self.payload_ref == "":
            raise ValueError(
                "payload_ref must be non-empty (GC-11: LOG_REFERENCE_INVALID)"
            )


@dataclass
class RunManifest:
    """
    GC-11 RunManifest: Reproducibility + Determinism Contract.
    
    Every run must have a manifest that:
    - Uniquely identifies the run (run_id)
    - Uniquely identifies input content (input_hash)
    - Records deterministic mode and seed propagation
    - Records environment identity (commit + lock hashes)
    - Records tool versions
    - Records timestamps
    - Contains typed, resolvable log references
    
    Validation rules:
    - run_id: UUID v4 format (strict token)
    - input_hash: hex-encoded sha256 (64 chars)
    - deterministic_mode=true => seed REQUIRED + tolerance_policy REQUIRED
    - commit_hash, dependency_lock_hash: non-empty strict tokens
    - tool_versions: non-empty dict with python always required
    - started_at <= ended_at
    - log_references: non-empty list of valid LogReference
    """
    run_id: str
    input_hash: str
    deterministic_mode: bool
    tool_versions: dict[str, str]
    commit_hash: str
    dependency_lock_hash: str
    started_at: str
    ended_at: str
    log_references: list[LogReference]
    seed: Optional[int] = None
    tolerance_policy: Optional[dict[str, Any]] = None
    duration_ms: Optional[int] = None
    report_ref: Optional[str] = None
    corpus_snapshot_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str):
            raise TypeError(
                f"run_id must be str, got {type(self.run_id).__name__} "
                "(GC-11: RUN_ID_INVALID)"
            )
        if not isinstance(self.input_hash, str):
            raise TypeError(
                f"input_hash must be str, got {type(self.input_hash).__name__} "
                "(GC-11: INPUT_HASH_INVALID)"
            )
        if not isinstance(self.deterministic_mode, bool):
            raise TypeError(
                f"deterministic_mode must be bool, got {type(self.deterministic_mode).__name__} "
                "(GC-11: DETERMINISTIC_MODE_INVALID)"
            )
        if not isinstance(self.tool_versions, dict):
            raise TypeError(
                f"tool_versions must be dict, got {type(self.tool_versions).__name__} "
                "(GC-11: TOOL_VERSIONS_MISSING)"
            )
        if not isinstance(self.commit_hash, str):
            raise TypeError(
                f"commit_hash must be str, got {type(self.commit_hash).__name__} "
                "(GC-11: COMMIT_HASH_MISSING)"
            )
        if not isinstance(self.dependency_lock_hash, str):
            raise TypeError(
                f"dependency_lock_hash must be str, got {type(self.dependency_lock_hash).__name__} "
                "(GC-11: LOCK_HASH_MISSING)"
            )
        if not isinstance(self.started_at, str):
            raise TypeError(
                f"started_at must be str, got {type(self.started_at).__name__} "
                "(GC-11: TIMESTAMPS_INVALID)"
            )
        if not isinstance(self.ended_at, str):
            raise TypeError(
                f"ended_at must be str, got {type(self.ended_at).__name__} "
                "(GC-11: TIMESTAMPS_INVALID)"
            )
        if not isinstance(self.log_references, list):
            raise TypeError(
                f"log_references must be list, got {type(self.log_references).__name__} "
                "(GC-11: LOG_REFERENCE_INVALID)"
            )
        if self.seed is not None and not isinstance(self.seed, int):
            raise TypeError(
                f"seed must be int or None, got {type(self.seed).__name__} "
                "(GC-11: DETERMINISTIC_MODE_INVALID)"
            )
        if isinstance(self.seed, bool):
            raise TypeError(
                "seed must be int, not bool (GC-11: DETERMINISTIC_MODE_INVALID)"
            )
        if self.tolerance_policy is not None and not isinstance(self.tolerance_policy, dict):
            raise TypeError(
                f"tolerance_policy must be dict or None, got {type(self.tolerance_policy).__name__} "
                "(GC-11: DETERMINISTIC_MODE_INVALID)"
            )
        if self.duration_ms is not None:
            if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int):
                raise TypeError(
                    f"duration_ms must be int or None, got {type(self.duration_ms).__name__} "
                    "(GC-11: TIMESTAMPS_INVALID)"
                )
        if self.report_ref is not None and not isinstance(self.report_ref, str):
            raise TypeError(
                f"report_ref must be str or None, got {type(self.report_ref).__name__} "
                "(GC-11: MANIFEST_INVALID)"
            )
        if self.corpus_snapshot_ref is not None and not isinstance(self.corpus_snapshot_ref, str):
            raise TypeError(
                f"corpus_snapshot_ref must be str or None, got {type(self.corpus_snapshot_ref).__name__} "
                "(GC-11: MANIFEST_INVALID)"
            )
