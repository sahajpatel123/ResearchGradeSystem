"""
GC-11 RunManifest Tests: Reproducibility + Determinism Contract.

Tests all validation rules for GC-11:
- run_id and input_hash parsing
- deterministic_mode enforcement
- environment/tools validation
- timestamps validation
- log reference resolution
- seed propagation
- manifest generation
"""

import json
from pathlib import Path

import pytest

from src.core.artifact_registry import ArtifactRegistry, LogArtifact
from src.core.gc11_parsers import (
    parse_commit_hash,
    parse_dependency_lock_hash,
    parse_input_hash,
    parse_log_id,
    parse_payload_ref,
    parse_run_id,
)
from src.core.gc11_validators import (
    GC11ValidationError,
    build_run_manifest,
    compute_input_hash,
    generate_run_id,
    validate_deterministic_mode,
    validate_environment,
    validate_input_hash,
    validate_log_references,
    validate_run_id,
    validate_run_manifest,
    validate_seed_propagation,
    validate_timestamps,
    validate_tool_versions,
)
from src.core.run_manifest import LogReference, LogType, RunManifest


def _load_fixture(name: str) -> dict:
    """Load a GC-11 fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / name
    with open(fixture_path, "r") as f:
        return json.load(f)


def _build_manifest_from_fixture(data: dict) -> RunManifest:
    """Build RunManifest from fixture data."""
    m = data["manifest"]
    log_refs = [
        LogReference(
            log_id=ref["log_id"],
            log_type=LogType(ref["log_type"]),
            payload_ref=ref["payload_ref"],
        )
        for ref in m["log_references"]
    ]
    return RunManifest(
        run_id=m["run_id"],
        input_hash=m["input_hash"],
        deterministic_mode=m["deterministic_mode"],
        tool_versions=m["tool_versions"],
        commit_hash=m["commit_hash"],
        dependency_lock_hash=m["dependency_lock_hash"],
        started_at=m["started_at"],
        ended_at=m["ended_at"],
        log_references=log_refs,
        seed=m.get("seed"),
        tolerance_policy=m.get("tolerance_policy"),
        duration_ms=m.get("duration_ms"),
        report_ref=m.get("report_ref"),
    )


def _build_registry_from_fixture(data: dict) -> ArtifactRegistry:
    """Build ArtifactRegistry from fixture data."""
    registry = ArtifactRegistry()
    for artifact_data in data.get("registry_artifacts", []):
        artifact = LogArtifact(
            log_id=artifact_data["log_id"],
            log_type=LogType(artifact_data["log_type"]),
            payload_ref=artifact_data["payload_ref"],
            seed=artifact_data.get("seed"),
        )
        registry.register(artifact_data["log_id"], artifact)
    return registry


class TestRunIdParsing:
    """Test parse_run_id wire-boundary parser."""

    def test_parse_run_id_valid_uuid_v4(self):
        """Valid UUID v4 format accepted."""
        result = parse_run_id("550e8400-e29b-41d4-a716-446655440000")
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_parse_run_id_valid_uuid_v4_uppercase(self):
        """UUID v4 with uppercase hex is normalized to lowercase."""
        result = parse_run_id("550E8400-E29B-41D4-A716-446655440000")
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_parse_run_id_rejects_none(self):
        """None run_id rejected with RUN_ID_MISSING."""
        with pytest.raises(ValueError, match="RUN_ID_MISSING"):
            parse_run_id(None)

    def test_parse_run_id_rejects_empty(self):
        """Empty run_id rejected."""
        with pytest.raises(ValueError, match="RUN_ID_INVALID"):
            parse_run_id("")

    def test_parse_run_id_rejects_non_uuid(self):
        """Non-UUID format rejected."""
        with pytest.raises(ValueError, match="RUN_ID_INVALID"):
            parse_run_id("not-a-valid-uuid")

    def test_parse_run_id_rejects_uuid_v1(self):
        """UUID v1 format rejected (version nibble must be 4)."""
        with pytest.raises(ValueError, match="RUN_ID_INVALID"):
            parse_run_id("550e8400-e29b-11d4-a716-446655440000")

    def test_parse_run_id_rejects_whitespace(self):
        """Leading/trailing whitespace rejected."""
        with pytest.raises(ValueError, match="RUN_ID_INVALID"):
            parse_run_id(" 550e8400-e29b-41d4-a716-446655440000")

    def test_parse_run_id_rejects_wrong_type(self):
        """Non-string type rejected."""
        with pytest.raises(TypeError, match="RUN_ID_INVALID"):
            parse_run_id(12345)


class TestInputHashParsing:
    """Test parse_input_hash wire-boundary parser."""

    def test_parse_input_hash_valid_sha256(self):
        """Valid 64-char lowercase hex accepted."""
        valid_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        result = parse_input_hash(valid_hash)
        assert result == valid_hash

    def test_parse_input_hash_rejects_none(self):
        """None input_hash rejected with INPUT_HASH_MISSING."""
        with pytest.raises(ValueError, match="INPUT_HASH_MISSING"):
            parse_input_hash(None)

    def test_parse_input_hash_rejects_empty(self):
        """Empty input_hash rejected."""
        with pytest.raises(ValueError, match="INPUT_HASH_INVALID"):
            parse_input_hash("")

    def test_parse_input_hash_rejects_short(self):
        """Too short hash rejected."""
        with pytest.raises(ValueError, match="INPUT_HASH_INVALID"):
            parse_input_hash("abc123")

    def test_parse_input_hash_rejects_uppercase(self):
        """Uppercase hex rejected (must be lowercase)."""
        with pytest.raises(ValueError, match="INPUT_HASH_INVALID"):
            parse_input_hash("A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2")

    def test_parse_input_hash_rejects_non_hex(self):
        """Non-hex characters rejected."""
        with pytest.raises(ValueError, match="INPUT_HASH_INVALID"):
            parse_input_hash("g1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")

    def test_parse_input_hash_rejects_whitespace(self):
        """Leading/trailing whitespace rejected."""
        with pytest.raises(ValueError, match="INPUT_HASH_INVALID"):
            parse_input_hash(" a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")


class TestCommitHashParsing:
    """Test parse_commit_hash wire-boundary parser."""

    def test_parse_commit_hash_valid(self):
        """Valid commit hash accepted."""
        result = parse_commit_hash("abc123def456")
        assert result == "abc123def456"

    def test_parse_commit_hash_rejects_none(self):
        """None commit_hash rejected."""
        with pytest.raises(ValueError, match="COMMIT_HASH_MISSING"):
            parse_commit_hash(None)

    def test_parse_commit_hash_rejects_empty(self):
        """Empty commit_hash rejected."""
        with pytest.raises(ValueError, match="COMMIT_HASH_MISSING"):
            parse_commit_hash("")


class TestDependencyLockHashParsing:
    """Test parse_dependency_lock_hash wire-boundary parser."""

    def test_parse_dependency_lock_hash_valid(self):
        """Valid lock hash accepted."""
        result = parse_dependency_lock_hash("lockfile_sha256_abc123")
        assert result == "lockfile_sha256_abc123"

    def test_parse_dependency_lock_hash_rejects_none(self):
        """None lock_hash rejected."""
        with pytest.raises(ValueError, match="LOCK_HASH_MISSING"):
            parse_dependency_lock_hash(None)

    def test_parse_dependency_lock_hash_rejects_empty(self):
        """Empty lock_hash rejected."""
        with pytest.raises(ValueError, match="LOCK_HASH_MISSING"):
            parse_dependency_lock_hash("")


class TestLogReferenceSchema:
    """Test LogReference dataclass validation."""

    def test_log_reference_valid(self):
        """Valid LogReference accepted."""
        ref = LogReference(
            log_id="numeric-log-001",
            log_type=LogType.NUMERIC,
            payload_ref="logs/numeric/001.json",
        )
        assert ref.log_id == "numeric-log-001"
        assert ref.log_type == LogType.NUMERIC
        assert ref.payload_ref == "logs/numeric/001.json"

    def test_log_reference_rejects_empty_log_id(self):
        """Empty log_id rejected."""
        with pytest.raises(ValueError, match="LOG_REFERENCE_INVALID"):
            LogReference(
                log_id="",
                log_type=LogType.NUMERIC,
                payload_ref="logs/numeric/001.json",
            )

    def test_log_reference_rejects_empty_payload_ref(self):
        """Empty payload_ref rejected."""
        with pytest.raises(ValueError, match="LOG_REFERENCE_INVALID"):
            LogReference(
                log_id="numeric-log-001",
                log_type=LogType.NUMERIC,
                payload_ref="",
            )

    def test_log_reference_rejects_invalid_log_type(self):
        """Invalid log_type rejected."""
        with pytest.raises(TypeError, match="LOG_REFERENCE_INVALID"):
            LogReference(
                log_id="numeric-log-001",
                log_type="invalid",  # type: ignore
                payload_ref="logs/numeric/001.json",
            )


class TestLogTypeEnum:
    """Test LogType enum values."""

    def test_log_type_numeric(self):
        assert LogType.NUMERIC.value == "numeric"

    def test_log_type_cas(self):
        assert LogType.CAS.value == "cas"

    def test_log_type_retrieval(self):
        assert LogType.RETRIEVAL.value == "retrieval"

    def test_log_type_branch(self):
        assert LogType.BRANCH.value == "branch"

    def test_log_type_failure_localization(self):
        assert LogType.FAILURE_LOCALIZATION.value == "failure_localization"


class TestRunManifestRequiresRunIdAndInputHash:
    """Test run_id and input_hash are required and validated."""

    def test_run_manifest_requires_run_id_and_input_hash(self):
        """Manifest requires valid run_id and input_hash."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        assert len(errors) == 0

    def test_fixture_fail_invalid_run_id(self):
        """FAIL fixture: invalid run_id."""
        data = _load_fixture("gc11_fail_invalid_run_id.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_id(manifest)
        assert len(errors) == 1
        assert errors[0].category == "RUN_ID_INVALID"

    def test_fixture_fail_invalid_input_hash(self):
        """FAIL fixture: invalid input_hash."""
        data = _load_fixture("gc11_fail_invalid_input_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_input_hash(manifest)
        assert len(errors) == 1
        assert errors[0].category == "INPUT_HASH_INVALID"


class TestDeterministicModeRequiresSeedAndTolerancePolicy:
    """Test deterministic_mode enforcement."""

    def test_deterministic_mode_requires_seed_and_tolerance_policy(self):
        """deterministic_mode=true requires seed and tolerance_policy."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_deterministic_mode(manifest)
        assert len(errors) == 0

    def test_non_deterministic_mode_allows_seed_omission(self):
        """deterministic_mode=false allows seed omission."""
        data = _load_fixture("gc11_pass_non_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_deterministic_mode(manifest)
        assert len(errors) == 0

    def test_fixture_fail_deterministic_missing_seed(self):
        """FAIL fixture: deterministic mode missing seed."""
        data = _load_fixture("gc11_fail_deterministic_missing_seed.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_deterministic_mode(manifest)
        assert len(errors) == 1
        assert errors[0].category == "DETERMINISTIC_MODE_MISSING_SEED"

    def test_fixture_fail_deterministic_missing_tolerance(self):
        """FAIL fixture: deterministic mode missing tolerance_policy."""
        data = _load_fixture("gc11_fail_deterministic_missing_tolerance.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_deterministic_mode(manifest)
        assert len(errors) == 1
        assert errors[0].category == "DETERMINISTIC_MODE_MISSING_TOLERANCE_POLICY"


class TestRunManifestRequiresCommitAndLockHash:
    """Test commit_hash and dependency_lock_hash are required."""

    def test_run_manifest_requires_commit_and_lock_hash(self):
        """Manifest requires valid commit_hash and dependency_lock_hash."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_environment(manifest)
        assert len(errors) == 0

    def test_fixture_fail_missing_commit_hash(self):
        """FAIL fixture: missing commit_hash."""
        data = _load_fixture("gc11_fail_missing_commit_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_environment(manifest)
        assert len(errors) == 1
        assert errors[0].category == "COMMIT_HASH_MISSING"

    def test_fixture_fail_missing_lock_hash(self):
        """FAIL fixture: missing dependency_lock_hash."""
        data = _load_fixture("gc11_fail_missing_lock_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_environment(manifest)
        assert len(errors) == 1
        assert errors[0].category == "LOCK_HASH_MISSING"


class TestRunManifestRequiresToolVersions:
    """Test tool_versions validation."""

    def test_run_manifest_requires_tool_versions(self):
        """Manifest requires non-empty tool_versions with python."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_tool_versions(manifest, registry)
        assert len(errors) == 0

    def test_fixture_fail_tool_versions_empty(self):
        """FAIL fixture: tool_versions empty."""
        data = _load_fixture("gc11_fail_tool_versions_empty.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_tool_versions(manifest)
        assert len(errors) == 1
        assert errors[0].category == "TOOL_VERSIONS_MISSING"

    def test_fixture_fail_tool_versions_missing_numpy(self):
        """FAIL fixture: tool_versions missing numpy when numeric logs present."""
        data = _load_fixture("gc11_fail_tool_versions_missing_numpy.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_tool_versions(manifest, registry)
        assert any(e.category == "TOOL_VERSIONS_INCOMPLETE" for e in errors)


class TestManifestLogReferencesTypedAndNonEmpty:
    """Test log_references validation."""

    def test_manifest_log_references_typed_and_non_empty(self):
        """log_references must be non-empty with valid typed entries."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_log_references(manifest, registry)
        assert len(errors) == 0

    def test_fixture_fail_log_reference_invalid(self):
        """FAIL fixture: log_reference has invalid shape."""
        data = _load_fixture("gc11_fail_log_reference_invalid.json")
        # This fixture has empty payload_ref which will fail at LogReference construction
        with pytest.raises(ValueError, match="LOG_REFERENCE_INVALID"):
            _build_manifest_from_fixture(data)


class TestLogReferencesResolveInRegistry:
    """Test log reference resolution in registry."""

    def test_log_references_resolve_in_registry(self):
        """All log_references must resolve in registry."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_log_references(manifest, registry)
        assert len(errors) == 0

    def test_fixture_fail_log_reference_unresolved(self):
        """FAIL fixture: log_reference does not resolve."""
        data = _load_fixture("gc11_fail_log_reference_unresolved.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_log_references(manifest, registry)
        assert len(errors) == 1
        assert errors[0].category == "LOG_REFERENCE_UNRESOLVED"


class TestManifestTimestampsOrdered:
    """Test timestamps validation."""

    def test_manifest_timestamps_ordered(self):
        """ended_at must be >= started_at."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_timestamps(manifest)
        assert len(errors) == 0

    def test_fixture_fail_timestamps_invalid_order(self):
        """FAIL fixture: ended_at before started_at."""
        data = _load_fixture("gc11_fail_timestamps_invalid_order.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_timestamps(manifest)
        assert len(errors) == 1
        assert errors[0].category == "TIMESTAMPS_INVALID_ORDER"


class TestInputHashStableForSameRawInput:
    """Test compute_input_hash determinism."""

    def test_input_hash_stable_for_same_raw_input(self):
        """Same input produces same hash."""
        input_bundle = {"data": "test", "value": 42}
        hash1 = compute_input_hash(input_bundle)
        hash2 = compute_input_hash(input_bundle)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_input_hash_different_for_different_input(self):
        """Different input produces different hash."""
        hash1 = compute_input_hash({"data": "test1"})
        hash2 = compute_input_hash({"data": "test2"})
        assert hash1 != hash2

    def test_input_hash_deterministic_key_order(self):
        """Key order doesn't affect hash (sorted serialization)."""
        hash1 = compute_input_hash({"b": 2, "a": 1})
        hash2 = compute_input_hash({"a": 1, "b": 2})
        assert hash1 == hash2


class TestManifestSeedPropagatesToNumericChecks:
    """Test seed propagation enforcement."""

    def test_manifest_seed_propagates_to_numeric_checks(self):
        """Numeric log seed must match manifest seed in deterministic mode."""
        data = _load_fixture("gc11_pass_deterministic_numeric_seed_match.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_seed_propagation(manifest, registry)
        assert len(errors) == 0

    def test_fixture_fail_numeric_seed_mismatch(self):
        """FAIL fixture: numeric log seed != manifest seed."""
        data = _load_fixture("gc11_fail_numeric_seed_mismatch.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_seed_propagation(manifest, registry)
        assert len(errors) == 1
        assert errors[0].category == "MANIFEST_SEED_MISMATCH_NUMERIC_LOG"


class TestManifestGeneration:
    """Test build_run_manifest and generate_run_id."""

    def test_generate_run_id_produces_valid_uuid_v4(self):
        """generate_run_id produces valid UUID v4."""
        run_id = generate_run_id()
        # Should not raise
        parsed = parse_run_id(run_id)
        assert parsed == run_id.lower()

    def test_build_run_manifest_creates_valid_manifest(self):
        """build_run_manifest creates valid manifest."""
        log_refs = [
            LogReference(
                log_id="branch-log-001",
                log_type=LogType.BRANCH,
                payload_ref="logs/branch/001.json",
            )
        ]
        manifest = build_run_manifest(
            input_bundle={"test": "data"},
            deterministic_mode=False,
            tool_versions={"python": "3.11.0"},
            commit_hash="abc123",
            dependency_lock_hash="lock123",
            started_at="2024-01-15T10:00:00Z",
            ended_at="2024-01-15T10:05:00Z",
            log_references=log_refs,
        )

        assert len(manifest.run_id) == 36  # UUID format
        assert len(manifest.input_hash) == 64  # SHA256 hex
        assert manifest.deterministic_mode is False
        assert manifest.tool_versions == {"python": "3.11.0"}

    def test_build_run_manifest_with_deterministic_mode(self):
        """build_run_manifest with deterministic mode."""
        log_refs = [
            LogReference(
                log_id="numeric-log-001",
                log_type=LogType.NUMERIC,
                payload_ref="logs/numeric/001.json",
            )
        ]
        manifest = build_run_manifest(
            input_bundle={"test": "data"},
            deterministic_mode=True,
            tool_versions={"python": "3.11.0", "numpy": "1.24.0"},
            commit_hash="abc123",
            dependency_lock_hash="lock123",
            started_at="2024-01-15T10:00:00Z",
            ended_at="2024-01-15T10:05:00Z",
            log_references=log_refs,
            seed=42,
            tolerance_policy={"absolute": 1e-10},
        )

        assert manifest.deterministic_mode is True
        assert manifest.seed == 42
        assert manifest.tolerance_policy == {"absolute": 1e-10}


class TestArtifactRegistry:
    """Test ArtifactRegistry functionality."""

    def test_registry_register_and_resolve(self):
        """Register and resolve artifact."""
        registry = ArtifactRegistry()
        artifact = LogArtifact(
            log_id="numeric-log-001",
            log_type=LogType.NUMERIC,
            payload_ref="logs/numeric/001.json",
            seed=42,
        )
        registry.register("numeric-log-001", artifact)

        resolved = registry.resolve("numeric-log-001")
        assert resolved is artifact
        assert resolved.seed == 42

    def test_registry_resolve_not_found(self):
        """Resolve returns None for unknown log_id."""
        registry = ArtifactRegistry()
        resolved = registry.resolve("nonexistent")
        assert resolved is None

    def test_registry_has(self):
        """has() returns True for registered log_id."""
        registry = ArtifactRegistry()
        artifact = LogArtifact(
            log_id="branch-log-001",
            log_type=LogType.BRANCH,
            payload_ref="logs/branch/001.json",
        )
        registry.register("branch-log-001", artifact)

        assert registry.has("branch-log-001") is True
        assert registry.has("nonexistent") is False

    def test_registry_collision_detection(self):
        """Collision detected when same log_id registered with different payload_ref."""
        registry = ArtifactRegistry()
        artifact1 = LogArtifact(
            log_id="log-001",
            log_type=LogType.BRANCH,
            payload_ref="logs/branch/001.json",
        )
        artifact2 = LogArtifact(
            log_id="log-001",
            log_type=LogType.BRANCH,
            payload_ref="logs/branch/002.json",  # Different payload_ref
        )
        registry.register("log-001", artifact1)

        with pytest.raises(ValueError, match="LOG_REFERENCE_COLLISION"):
            registry.register("log-001", artifact2)


class TestPassFixtures:
    """Test all PASS fixtures validate successfully."""

    def test_fixture_pass_deterministic_valid(self):
        """PASS fixture: deterministic manifest valid."""
        data = _load_fixture("gc11_pass_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        assert len(errors) == 0

    def test_fixture_pass_non_deterministic_valid(self):
        """PASS fixture: non-deterministic manifest valid."""
        data = _load_fixture("gc11_pass_non_deterministic_valid.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        assert len(errors) == 0

    def test_fixture_pass_deterministic_numeric_seed_match(self):
        """PASS fixture: deterministic manifest with numeric seed match."""
        data = _load_fixture("gc11_pass_deterministic_numeric_seed_match.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        assert len(errors) == 0


class TestFailFixtures:
    """Test all FAIL fixtures produce expected errors."""

    def test_fixture_fail_deterministic_missing_seed(self):
        """FAIL fixture: deterministic missing seed."""
        data = _load_fixture("gc11_fail_deterministic_missing_seed.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "DETERMINISTIC_MODE_MISSING_SEED" in categories

    def test_fixture_fail_deterministic_missing_tolerance(self):
        """FAIL fixture: deterministic missing tolerance_policy."""
        data = _load_fixture("gc11_fail_deterministic_missing_tolerance.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "DETERMINISTIC_MODE_MISSING_TOLERANCE_POLICY" in categories

    def test_fixture_fail_invalid_run_id(self):
        """FAIL fixture: invalid run_id."""
        data = _load_fixture("gc11_fail_invalid_run_id.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "RUN_ID_INVALID" in categories

    def test_fixture_fail_invalid_input_hash(self):
        """FAIL fixture: invalid input_hash."""
        data = _load_fixture("gc11_fail_invalid_input_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "INPUT_HASH_INVALID" in categories

    def test_fixture_fail_missing_commit_hash(self):
        """FAIL fixture: missing commit_hash."""
        data = _load_fixture("gc11_fail_missing_commit_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "COMMIT_HASH_MISSING" in categories

    def test_fixture_fail_missing_lock_hash(self):
        """FAIL fixture: missing dependency_lock_hash."""
        data = _load_fixture("gc11_fail_missing_lock_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "LOCK_HASH_MISSING" in categories

    def test_fixture_fail_tool_versions_empty(self):
        """FAIL fixture: tool_versions empty."""
        data = _load_fixture("gc11_fail_tool_versions_empty.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_run_manifest(manifest)
        categories = [e.category for e in errors]
        assert "TOOL_VERSIONS_MISSING" in categories

    def test_fixture_fail_tool_versions_missing_numpy(self):
        """FAIL fixture: tool_versions missing numpy."""
        data = _load_fixture("gc11_fail_tool_versions_missing_numpy.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        categories = [e.category for e in errors]
        assert "TOOL_VERSIONS_INCOMPLETE" in categories

    def test_fixture_fail_log_reference_unresolved(self):
        """FAIL fixture: log_reference unresolved."""
        data = _load_fixture("gc11_fail_log_reference_unresolved.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        categories = [e.category for e in errors]
        assert "LOG_REFERENCE_UNRESOLVED" in categories

    def test_fixture_fail_timestamps_invalid_order(self):
        """FAIL fixture: timestamps invalid order."""
        data = _load_fixture("gc11_fail_timestamps_invalid_order.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        categories = [e.category for e in errors]
        assert "TIMESTAMPS_INVALID_ORDER" in categories

    def test_fixture_fail_numeric_seed_mismatch(self):
        """FAIL fixture: numeric seed mismatch."""
        data = _load_fixture("gc11_fail_numeric_seed_mismatch.json")
        manifest = _build_manifest_from_fixture(data)
        registry = _build_registry_from_fixture(data)

        errors = validate_run_manifest(manifest, registry)
        categories = [e.category for e in errors]
        assert "MANIFEST_SEED_MISMATCH_NUMERIC_LOG" in categories
