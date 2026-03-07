"""
GC-11 Validators: RunManifest Validation + Generation.

Implements all validation rules for GC-11 Reproducibility + Determinism Contract.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.core.artifact_registry import ArtifactRegistry, LogArtifact
from src.core.gc11_parsers import (
    parse_commit_hash,
    parse_dependency_lock_hash,
    parse_input_hash,
    parse_log_id,
    parse_payload_ref,
    parse_run_id,
)
from src.core.run_manifest import LogReference, LogType, RunManifest


@dataclass
class GC11ValidationError:
    """GC-11 validation error with category and message."""
    category: str
    message: str
    field: Optional[str] = None


def validate_run_id(manifest: RunManifest) -> list[GC11ValidationError]:
    """Validate run_id is present and valid UUID v4."""
    errors = []
    try:
        parse_run_id(manifest.run_id)
    except ValueError as e:
        if "RUN_ID_MISSING" in str(e):
            errors.append(GC11ValidationError(
                category="RUN_ID_MISSING",
                message=str(e),
                field="run_id"
            ))
        else:
            errors.append(GC11ValidationError(
                category="RUN_ID_INVALID",
                message=str(e),
                field="run_id"
            ))
    except TypeError as e:
        errors.append(GC11ValidationError(
            category="RUN_ID_INVALID",
            message=str(e),
            field="run_id"
        ))
    return errors


def validate_input_hash(manifest: RunManifest) -> list[GC11ValidationError]:
    """Validate input_hash is present and valid hex sha256."""
    errors = []
    try:
        parse_input_hash(manifest.input_hash)
    except ValueError as e:
        if "INPUT_HASH_MISSING" in str(e):
            errors.append(GC11ValidationError(
                category="INPUT_HASH_MISSING",
                message=str(e),
                field="input_hash"
            ))
        else:
            errors.append(GC11ValidationError(
                category="INPUT_HASH_INVALID",
                message=str(e),
                field="input_hash"
            ))
    except TypeError as e:
        errors.append(GC11ValidationError(
            category="INPUT_HASH_INVALID",
            message=str(e),
            field="input_hash"
        ))
    return errors


def validate_deterministic_mode(manifest: RunManifest) -> list[GC11ValidationError]:
    """
    Validate deterministic_mode enforcement.
    
    If deterministic_mode=true:
    - seed REQUIRED (int)
    - tolerance_policy REQUIRED (non-empty dict)
    """
    errors = []
    
    if manifest.deterministic_mode:
        if manifest.seed is None:
            errors.append(GC11ValidationError(
                category="DETERMINISTIC_MODE_MISSING_SEED",
                message="deterministic_mode=true requires seed (int) "
                        "(GC-11: DETERMINISTIC_MODE_MISSING_SEED)",
                field="seed"
            ))
        
        if manifest.tolerance_policy is None:
            errors.append(GC11ValidationError(
                category="DETERMINISTIC_MODE_MISSING_TOLERANCE_POLICY",
                message="deterministic_mode=true requires tolerance_policy (non-empty dict) "
                        "(GC-11: DETERMINISTIC_MODE_MISSING_TOLERANCE_POLICY)",
                field="tolerance_policy"
            ))
        elif len(manifest.tolerance_policy) == 0:
            errors.append(GC11ValidationError(
                category="DETERMINISTIC_MODE_MISSING_TOLERANCE_POLICY",
                message="deterministic_mode=true requires tolerance_policy to be non-empty "
                        "(GC-11: DETERMINISTIC_MODE_MISSING_TOLERANCE_POLICY)",
                field="tolerance_policy"
            ))
    
    return errors


def validate_environment(manifest: RunManifest) -> list[GC11ValidationError]:
    """Validate commit_hash and dependency_lock_hash."""
    errors = []
    
    try:
        parse_commit_hash(manifest.commit_hash)
    except (ValueError, TypeError) as e:
        errors.append(GC11ValidationError(
            category="COMMIT_HASH_MISSING",
            message=str(e),
            field="commit_hash"
        ))
    
    try:
        parse_dependency_lock_hash(manifest.dependency_lock_hash)
    except (ValueError, TypeError) as e:
        errors.append(GC11ValidationError(
            category="LOCK_HASH_MISSING",
            message=str(e),
            field="dependency_lock_hash"
        ))
    
    return errors


def validate_tool_versions(
    manifest: RunManifest,
    registry: Optional[ArtifactRegistry] = None
) -> list[GC11ValidationError]:
    """
    Validate tool_versions.
    
    Rules:
    - tool_versions must be non-empty dict
    - python version always required
    - sympy required if CAS logs present
    - numpy required if numeric logs present
    - lean required if proof logs present (future)
    """
    errors = []
    
    if len(manifest.tool_versions) == 0:
        errors.append(GC11ValidationError(
            category="TOOL_VERSIONS_MISSING",
            message="tool_versions must be non-empty (GC-11: TOOL_VERSIONS_MISSING)",
            field="tool_versions"
        ))
        return errors
    
    # Python always required
    if "python" not in manifest.tool_versions:
        errors.append(GC11ValidationError(
            category="TOOL_VERSIONS_INCOMPLETE",
            message="tool_versions must include 'python' version "
                    "(GC-11: TOOL_VERSIONS_INCOMPLETE)",
            field="tool_versions"
        ))
    
    # Check conditional requirements based on log_type presence
    log_types_present = {ref.log_type for ref in manifest.log_references}
    
    if LogType.CAS in log_types_present:
        if "sympy" not in manifest.tool_versions:
            errors.append(GC11ValidationError(
                category="TOOL_VERSIONS_INCOMPLETE",
                message="tool_versions must include 'sympy' version when CAS logs present "
                        "(GC-11: TOOL_VERSIONS_INCOMPLETE)",
                field="tool_versions"
            ))
    
    if LogType.NUMERIC in log_types_present:
        if "numpy" not in manifest.tool_versions:
            errors.append(GC11ValidationError(
                category="TOOL_VERSIONS_INCOMPLETE",
                message="tool_versions must include 'numpy' version when numeric logs present "
                        "(GC-11: TOOL_VERSIONS_INCOMPLETE)",
                field="tool_versions"
            ))
    
    return errors


def validate_timestamps(manifest: RunManifest) -> list[GC11ValidationError]:
    """
    Validate timestamps.
    
    Rules:
    - started_at present and valid ISO8601
    - ended_at present and valid ISO8601
    - ended_at >= started_at
    """
    errors = []
    
    started_at = None
    ended_at = None
    
    try:
        started_at = datetime.fromisoformat(manifest.started_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(GC11ValidationError(
            category="TIMESTAMPS_INVALID_ORDER",
            message=f"started_at must be valid ISO8601, got '{manifest.started_at}' "
                    "(GC-11: TIMESTAMPS_INVALID_ORDER)",
            field="started_at"
        ))
    
    try:
        ended_at = datetime.fromisoformat(manifest.ended_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(GC11ValidationError(
            category="TIMESTAMPS_INVALID_ORDER",
            message=f"ended_at must be valid ISO8601, got '{manifest.ended_at}' "
                    "(GC-11: TIMESTAMPS_INVALID_ORDER)",
            field="ended_at"
        ))
    
    if started_at is not None and ended_at is not None:
        if ended_at < started_at:
            errors.append(GC11ValidationError(
                category="TIMESTAMPS_INVALID_ORDER",
                message=f"ended_at ({manifest.ended_at}) must be >= started_at ({manifest.started_at}) "
                        "(GC-11: TIMESTAMPS_INVALID_ORDER)",
                field="ended_at"
            ))
    
    return errors


def validate_log_references(
    manifest: RunManifest,
    registry: Optional[ArtifactRegistry] = None
) -> list[GC11ValidationError]:
    """
    Validate log_references.
    
    Rules:
    - log_references must be non-empty
    - each log reference has valid fields
    - log_type in allowed enum
    - if registry provided: each log_id resolves
    - resolved artifact log_type matches manifest log_type
    - payload_ref non-empty strict token
    - detect duplicate log_id with different payload_ref
    """
    errors = []
    
    if len(manifest.log_references) == 0:
        errors.append(GC11ValidationError(
            category="LOG_REFERENCE_INVALID",
            message="log_references must be non-empty (GC-11: LOG_REFERENCE_INVALID)",
            field="log_references"
        ))
        return errors
    
    seen_log_ids: dict[str, str] = {}  # log_id -> payload_ref
    
    for i, ref in enumerate(manifest.log_references):
        # Validate log_id
        try:
            parse_log_id(ref.log_id)
        except (ValueError, TypeError) as e:
            errors.append(GC11ValidationError(
                category="LOG_REFERENCE_INVALID",
                message=f"log_references[{i}]: {e}",
                field=f"log_references[{i}].log_id"
            ))
            continue
        
        # Validate payload_ref
        try:
            parse_payload_ref(ref.payload_ref)
        except (ValueError, TypeError) as e:
            errors.append(GC11ValidationError(
                category="LOG_REFERENCE_INVALID",
                message=f"log_references[{i}]: {e}",
                field=f"log_references[{i}].payload_ref"
            ))
        
        # Check for duplicate log_id with different payload_ref
        if ref.log_id in seen_log_ids:
            if seen_log_ids[ref.log_id] != ref.payload_ref:
                errors.append(GC11ValidationError(
                    category="LOG_REFERENCE_INVALID",
                    message=f"log_references[{i}]: duplicate log_id '{ref.log_id}' "
                            f"with different payload_ref (GC-11: LOG_REFERENCE_COLLISION)",
                    field=f"log_references[{i}].log_id"
                ))
        else:
            seen_log_ids[ref.log_id] = ref.payload_ref
        
        # Resolve in registry if provided
        if registry is not None:
            artifact = registry.resolve(ref.log_id)
            if artifact is None:
                errors.append(GC11ValidationError(
                    category="LOG_REFERENCE_UNRESOLVED",
                    message=f"log_references[{i}]: log_id '{ref.log_id}' not found in registry "
                            "(GC-11: LOG_REFERENCE_UNRESOLVED)",
                    field=f"log_references[{i}].log_id"
                ))
            else:
                # Check type match
                if artifact.log_type != ref.log_type:
                    errors.append(GC11ValidationError(
                        category="LOG_REFERENCE_INVALID",
                        message=f"log_references[{i}]: log_type mismatch "
                                f"(manifest: {ref.log_type.value}, registry: {artifact.log_type.value}) "
                                "(GC-11: LOG_REFERENCE_INVALID)",
                        field=f"log_references[{i}].log_type"
                    ))
    
    return errors


def validate_seed_propagation(
    manifest: RunManifest,
    registry: Optional[ArtifactRegistry] = None
) -> list[GC11ValidationError]:
    """
    Validate seed propagation for deterministic mode.
    
    If deterministic_mode=true and log_references contain numeric logs:
    - resolve numeric log artifacts
    - assert numeric log seed == manifest seed
    """
    errors = []
    
    if not manifest.deterministic_mode:
        return errors
    
    if manifest.seed is None:
        # Already caught by validate_deterministic_mode
        return errors
    
    if registry is None:
        return errors
    
    for i, ref in enumerate(manifest.log_references):
        if ref.log_type != LogType.NUMERIC:
            continue
        
        artifact = registry.resolve(ref.log_id)
        if artifact is None:
            # Already caught by validate_log_references
            continue
        
        if artifact.seed is not None and artifact.seed != manifest.seed:
            errors.append(GC11ValidationError(
                category="MANIFEST_SEED_MISMATCH_NUMERIC_LOG",
                message=f"log_references[{i}]: numeric log seed ({artifact.seed}) "
                        f"does not match manifest seed ({manifest.seed}) "
                        "(GC-11: MANIFEST_SEED_MISMATCH_NUMERIC_LOG)",
                field=f"log_references[{i}].seed"
            ))
    
    return errors


def validate_run_manifest(
    manifest: RunManifest,
    registry: Optional[ArtifactRegistry] = None
) -> list[GC11ValidationError]:
    """
    Validate RunManifest with all GC-11 rules.
    
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    errors.extend(validate_run_id(manifest))
    errors.extend(validate_input_hash(manifest))
    errors.extend(validate_deterministic_mode(manifest))
    errors.extend(validate_environment(manifest))
    errors.extend(validate_tool_versions(manifest, registry))
    errors.extend(validate_timestamps(manifest))
    errors.extend(validate_log_references(manifest, registry))
    errors.extend(validate_seed_propagation(manifest, registry))
    
    return errors


def compute_input_hash(input_bundle: dict[str, Any]) -> str:
    """
    Compute deterministic input hash from InputBundle.
    
    Uses sorted JSON serialization + SHA256 for stability.
    """
    # Sort keys for deterministic serialization
    serialized = json.dumps(input_bundle, sort_keys=True, separators=(",", ":"))
    hash_bytes = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return hash_bytes


def generate_run_id() -> str:
    """Generate a new UUID v4 run_id."""
    return str(uuid.uuid4())


def build_run_manifest(
    input_bundle: dict[str, Any],
    deterministic_mode: bool,
    tool_versions: dict[str, str],
    commit_hash: str,
    dependency_lock_hash: str,
    started_at: str,
    ended_at: str,
    log_references: list[LogReference],
    seed: Optional[int] = None,
    tolerance_policy: Optional[dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
    report_ref: Optional[str] = None,
    corpus_snapshot_ref: Optional[str] = None,
    run_id: Optional[str] = None,
) -> RunManifest:
    """
    Build a RunManifest from run context.
    
    Automatically computes input_hash and generates run_id if not provided.
    """
    if run_id is None:
        run_id = generate_run_id()
    
    input_hash = compute_input_hash(input_bundle)
    
    return RunManifest(
        run_id=run_id,
        input_hash=input_hash,
        deterministic_mode=deterministic_mode,
        tool_versions=tool_versions,
        commit_hash=commit_hash,
        dependency_lock_hash=dependency_lock_hash,
        started_at=started_at,
        ended_at=ended_at,
        log_references=log_references,
        seed=seed,
        tolerance_policy=tolerance_policy,
        duration_ms=duration_ms,
        report_ref=report_ref,
        corpus_snapshot_ref=corpus_snapshot_ref,
    )
