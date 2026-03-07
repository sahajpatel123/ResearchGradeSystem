"""
GC-11 ArtifactRegistry: Log Reference Resolution.

Minimal in-memory registry for resolving log references to artifacts.
Follows the pattern established by GC-10 ProofRegistry.
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.run_manifest import LogType


@dataclass
class LogArtifact:
    """
    GC-11 log artifact metadata.
    
    Represents a resolved log artifact with its type and payload reference.
    """
    log_id: str
    log_type: LogType
    payload_ref: str
    seed: Optional[int] = None  # For numeric logs, the seed used
    payload: Optional[dict[str, Any]] = None  # Optional full payload for inspection

    def __post_init__(self) -> None:
        if not isinstance(self.log_id, str) or self.log_id == "":
            raise ValueError(
                "log_id must be non-empty string (GC-11: LOG_REFERENCE_INVALID)"
            )
        if not isinstance(self.log_type, LogType):
            raise TypeError(
                f"log_type must be LogType enum, got {type(self.log_type).__name__} "
                "(GC-11: LOG_REFERENCE_INVALID)"
            )
        if not isinstance(self.payload_ref, str) or self.payload_ref == "":
            raise ValueError(
                "payload_ref must be non-empty string (GC-11: LOG_REFERENCE_INVALID)"
            )
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, int):
                raise TypeError(
                    f"seed must be int or None, got {type(self.seed).__name__} "
                    "(GC-11: LOG_REFERENCE_INVALID)"
                )


class ArtifactRegistry:
    """
    GC-11 ArtifactRegistry: In-memory registry for log artifact resolution.
    
    Provides:
    - register(log_id, artifact): Register a log artifact
    - resolve(log_id) -> LogArtifact | None: Resolve log_id to artifact
    - has(log_id) -> bool: Check if log_id exists
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, LogArtifact] = {}

    def register(self, log_id: str, artifact: LogArtifact) -> None:
        """
        Register a log artifact.
        
        Raises ValueError if log_id already registered with different payload_ref.
        """
        if not isinstance(log_id, str) or log_id == "":
            raise ValueError(
                "log_id must be non-empty string (GC-11: LOG_REFERENCE_INVALID)"
            )
        if not isinstance(artifact, LogArtifact):
            raise TypeError(
                f"artifact must be LogArtifact, got {type(artifact).__name__} "
                "(GC-11: LOG_REFERENCE_INVALID)"
            )
        
        if log_id in self._artifacts:
            existing = self._artifacts[log_id]
            if existing.payload_ref != artifact.payload_ref:
                raise ValueError(
                    f"log_id '{log_id}' already registered with different payload_ref "
                    f"(existing: '{existing.payload_ref}', new: '{artifact.payload_ref}') "
                    "(GC-11: LOG_REFERENCE_COLLISION)"
                )
        
        self._artifacts[log_id] = artifact

    def resolve(self, log_id: str) -> Optional[LogArtifact]:
        """
        Resolve log_id to artifact.
        
        Returns None if log_id not found.
        """
        return self._artifacts.get(log_id)

    def has(self, log_id: str) -> bool:
        """Check if log_id exists in registry."""
        return log_id in self._artifacts

    def all_artifacts(self) -> list[LogArtifact]:
        """Return all registered artifacts."""
        return list(self._artifacts.values())

    def clear(self) -> None:
        """Clear all registered artifacts."""
        self._artifacts.clear()
