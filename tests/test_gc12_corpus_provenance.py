"""
GC-12 Corpus Provenance Tests: Citation Traceability + Manifest Validation.

Tests all validation rules for GC-12:
- CorpusManifest entry validation
- Citation source resolution
- Citation location with chunk_id required
- Snapshot ref at-least-one rule
- Snippet hash definition (exact bytes)
- Citation evidence linkage
- RunManifest retrieval ref linkage
"""

import json
from pathlib import Path

import pytest

from src.core.corpus_manifest import (
    Citation,
    CitationLocation,
    CorpusManifest,
    CorpusManifestEntry,
    RetrievalSnapshotRef,
)
from src.core.gc12_parsers import (
    compute_snippet_hash,
    parse_chunk_id,
    parse_citation_id,
    parse_content_hash,
    parse_index_hash,
    parse_retrieval_snapshot_id,
    parse_snippet_hash,
    parse_source_id,
)
from src.core.gc12_validators import (
    GC12ValidationError,
    validate_citation,
    validate_citation_evidence_linkage,
    validate_citations,
    validate_corpus_manifest,
    validate_corpus_manifest_entry,
    validate_corpus_provenance,
    validate_runmanifest_retrieval_linkage,
    validate_snapshot_ref,
)
from src.core.run_manifest import LogReference, LogType, RunManifest


def _load_fixture(name: str) -> dict:
    """Load a GC-12 fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / name
    with open(fixture_path, "r") as f:
        return json.load(f)


def _build_manifest_from_fixture(data: dict) -> CorpusManifest:
    """Build CorpusManifest from fixture data."""
    entries = []
    for entry_data in data["corpus_manifest"]["entries"]:
        entries.append(CorpusManifestEntry(
            source_id=entry_data["source_id"],
            title=entry_data["title"],
            license_permission=entry_data["license_permission"],
            version_edition=entry_data["version_edition"],
            ingested_at=entry_data["ingested_at"],
            content_hash=entry_data["content_hash"],
        ))
    return CorpusManifest(entries=entries)


def _build_citations_from_fixture(data: dict) -> list[Citation]:
    """Build list of Citations from fixture data."""
    citations = []
    for cit_data in data.get("citations", []):
        loc_data = cit_data["location"]
        location = CitationLocation(
            chunk_id=loc_data["chunk_id"],
            page_start=loc_data.get("page_start"),
            page_end=loc_data.get("page_end"),
            char_start=loc_data.get("char_start"),
            char_end=loc_data.get("char_end"),
        )
        snap_data = cit_data["snapshot_ref"]
        snapshot_ref = RetrievalSnapshotRef(
            retrieval_snapshot_id=snap_data.get("retrieval_snapshot_id"),
            index_hash=snap_data.get("index_hash"),
            created_at=snap_data.get("created_at"),
        )
        citations.append(Citation(
            citation_id=cit_data["citation_id"],
            source_id=cit_data["source_id"],
            location=location,
            snippet_hash=cit_data["snippet_hash"],
            snapshot_ref=snapshot_ref,
        ))
    return citations


class TestSourceIdParsing:
    """Test parse_source_id wire-boundary parser."""

    def test_parse_source_id_valid(self):
        """Valid source_id accepted."""
        result = parse_source_id("source-001")
        assert result == "source-001"

    def test_parse_source_id_rejects_none(self):
        """None source_id rejected."""
        with pytest.raises(ValueError, match="CORPUS_SOURCE_MISSING_FIELD"):
            parse_source_id(None)

    def test_parse_source_id_rejects_empty(self):
        """Empty source_id rejected."""
        with pytest.raises(ValueError, match="CORPUS_SOURCE_MISSING_FIELD"):
            parse_source_id("")

    def test_parse_source_id_rejects_whitespace(self):
        """Leading/trailing whitespace rejected."""
        with pytest.raises(ValueError, match="CORPUS_SOURCE_MISSING_FIELD"):
            parse_source_id(" source-001")


class TestCitationIdParsing:
    """Test parse_citation_id wire-boundary parser."""

    def test_parse_citation_id_valid(self):
        """Valid citation_id accepted."""
        result = parse_citation_id("cit-001")
        assert result == "cit-001"

    def test_parse_citation_id_rejects_none(self):
        """None citation_id rejected."""
        with pytest.raises(ValueError, match="CITATION_ID_INVALID"):
            parse_citation_id(None)

    def test_parse_citation_id_rejects_empty(self):
        """Empty citation_id rejected."""
        with pytest.raises(ValueError, match="CITATION_ID_INVALID"):
            parse_citation_id("")


class TestChunkIdParsing:
    """Test parse_chunk_id wire-boundary parser."""

    def test_parse_chunk_id_valid(self):
        """Valid chunk_id accepted."""
        result = parse_chunk_id("chunk-001")
        assert result == "chunk-001"

    def test_parse_chunk_id_rejects_none(self):
        """None chunk_id rejected."""
        with pytest.raises(ValueError, match="CITATION_LOCATION_INVALID"):
            parse_chunk_id(None)

    def test_parse_chunk_id_rejects_empty(self):
        """Empty chunk_id rejected."""
        with pytest.raises(ValueError, match="CITATION_LOCATION_INVALID"):
            parse_chunk_id("")

    def test_parse_chunk_id_rejects_whitespace(self):
        """Leading/trailing whitespace rejected."""
        with pytest.raises(ValueError, match="CITATION_LOCATION_INVALID"):
            parse_chunk_id(" chunk-001")


class TestContentHashParsing:
    """Test parse_content_hash wire-boundary parser."""

    def test_parse_content_hash_valid(self):
        """Valid 64-char lowercase hex accepted."""
        valid_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        result = parse_content_hash(valid_hash)
        assert result == valid_hash

    def test_parse_content_hash_rejects_none(self):
        """None content_hash rejected."""
        with pytest.raises(ValueError, match="CORPUS_SOURCE_HASH_INVALID"):
            parse_content_hash(None)

    def test_parse_content_hash_rejects_short(self):
        """Too short hash rejected."""
        with pytest.raises(ValueError, match="CORPUS_SOURCE_HASH_INVALID"):
            parse_content_hash("abc123")

    def test_parse_content_hash_rejects_uppercase(self):
        """Uppercase hex rejected."""
        with pytest.raises(ValueError, match="CORPUS_SOURCE_HASH_INVALID"):
            parse_content_hash("A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2")


class TestSnippetHashParsing:
    """Test parse_snippet_hash wire-boundary parser."""

    def test_parse_snippet_hash_valid(self):
        """Valid 64-char lowercase hex accepted."""
        valid_hash = "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
        result = parse_snippet_hash(valid_hash)
        assert result == valid_hash

    def test_parse_snippet_hash_rejects_none(self):
        """None snippet_hash rejected."""
        with pytest.raises(ValueError, match="CITATION_SNIPPET_HASH_INVALID"):
            parse_snippet_hash(None)

    def test_parse_snippet_hash_rejects_short(self):
        """Too short hash rejected."""
        with pytest.raises(ValueError, match="CITATION_SNIPPET_HASH_INVALID"):
            parse_snippet_hash("abc123")


class TestIndexHashParsing:
    """Test parse_index_hash wire-boundary parser."""

    def test_parse_index_hash_valid(self):
        """Valid 64-char lowercase hex accepted."""
        valid_hash = "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        result = parse_index_hash(valid_hash)
        assert result == valid_hash

    def test_parse_index_hash_rejects_none(self):
        """None index_hash rejected."""
        with pytest.raises(ValueError, match="SNAPSHOT_REF_INVALID"):
            parse_index_hash(None)

    def test_parse_index_hash_rejects_short(self):
        """Too short hash rejected."""
        with pytest.raises(ValueError, match="SNAPSHOT_REF_INVALID"):
            parse_index_hash("abc123")


class TestSnippetHashDefinitionIsExactBytes:
    """
    Test snippet_hash definition is exact bytes.
    
    GC-12 FROZEN DEFINITION:
    snippet_hash = sha256(exact snippet bytes encoded as UTF-8)
    NO normalization, truncation, or UI rendering.
    """

    def test_snippet_hash_definition_is_exact_bytes(self):
        """Snippet hash is computed from exact UTF-8 bytes."""
        # Known snippet and expected hash
        snippet = "The quick brown fox jumps over the lazy dog"
        expected_hash = "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592"
        
        result = compute_snippet_hash(snippet)
        assert result == expected_hash

    def test_snippet_hash_preserves_whitespace(self):
        """Snippet hash preserves leading/trailing whitespace."""
        snippet1 = "hello"
        snippet2 = " hello"
        snippet3 = "hello "
        
        hash1 = compute_snippet_hash(snippet1)
        hash2 = compute_snippet_hash(snippet2)
        hash3 = compute_snippet_hash(snippet3)
        
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_snippet_hash_preserves_newlines(self):
        """Snippet hash preserves newlines exactly."""
        snippet1 = "line1\nline2"
        snippet2 = "line1\r\nline2"
        
        hash1 = compute_snippet_hash(snippet1)
        hash2 = compute_snippet_hash(snippet2)
        
        assert hash1 != hash2

    def test_snippet_hash_handles_unicode(self):
        """Snippet hash handles unicode correctly."""
        snippet = "Hello, 世界! 🌍"
        result = compute_snippet_hash(snippet)
        
        # Should be valid 64-char hex
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_snippet_hash_empty_string(self):
        """Snippet hash of empty string is valid."""
        snippet = ""
        expected_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        
        result = compute_snippet_hash(snippet)
        assert result == expected_hash


class TestCitationSourceIdMustResolveToManifest:
    """Test citation source_id must resolve to manifest."""

    def test_citation_source_id_must_resolve_to_manifest(self):
        """Citation source_id must exist in manifest."""
        data = _load_fixture("gc12_pass_valid_manifest_citation_index_hash.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        assert len(errors) == 0

    def test_fixture_fail_citation_source_unresolved(self):
        """FAIL fixture: citation source_id not in manifest."""
        data = _load_fixture("gc12_fail_citation_source_unresolved.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        categories = [e.category for e in errors]
        assert "CITATION_SOURCE_UNRESOLVED" in categories


class TestCitationRequiresChunkLocationAndSnippetHash:
    """Test citation requires chunk location and snippet_hash."""

    def test_citation_requires_chunk_location_and_snippet_hash(self):
        """Citation must have valid chunk_id and snippet_hash."""
        data = _load_fixture("gc12_pass_citation_chunk_page_range.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        assert len(errors) == 0

    def test_fixture_fail_missing_chunk_id(self):
        """FAIL fixture: citation location missing chunk_id."""
        data = _load_fixture("gc12_fail_missing_chunk_id.json")
        # This will fail at CitationLocation construction
        with pytest.raises(ValueError, match="CITATION_LOCATION_INVALID"):
            _build_citations_from_fixture(data)

    def test_fixture_fail_missing_snippet_hash(self):
        """FAIL fixture: citation missing snippet_hash."""
        data = _load_fixture("gc12_fail_missing_snippet_hash.json")
        # This will fail at Citation construction
        with pytest.raises(ValueError, match="CITATION_SNIPPET_HASH_MISSING"):
            _build_citations_from_fixture(data)


class TestSnapshotRefRequiresIndexHashOrSnapshotId:
    """Test snapshot_ref requires at least one of index_hash or retrieval_snapshot_id."""

    def test_snapshot_ref_requires_index_hash_or_snapshot_id(self):
        """Snapshot ref must have at least one field."""
        data = _load_fixture("gc12_pass_citation_both_snapshot_refs.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        assert len(errors) == 0

    def test_snapshot_ref_with_index_hash_only(self):
        """Snapshot ref with index_hash only is valid."""
        snapshot_ref = RetrievalSnapshotRef(
            index_hash="c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        )
        errors = validate_snapshot_ref(snapshot_ref)
        assert len(errors) == 0

    def test_snapshot_ref_with_retrieval_snapshot_id_only(self):
        """Snapshot ref with retrieval_snapshot_id only is valid."""
        snapshot_ref = RetrievalSnapshotRef(
            retrieval_snapshot_id="snapshot-2024-01-15-001"
        )
        errors = validate_snapshot_ref(snapshot_ref)
        assert len(errors) == 0

    def test_fixture_fail_missing_both_snapshot_refs(self):
        """FAIL fixture: snapshot_ref missing both fields."""
        data = _load_fixture("gc12_fail_missing_both_snapshot_refs.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        categories = [e.category for e in errors]
        assert "CITATION_SNAPSHOT_REF_MISSING" in categories

    def test_fixture_fail_invalid_snapshot_tokens(self):
        """FAIL fixture: snapshot_ref has invalid index_hash."""
        data = _load_fixture("gc12_fail_invalid_snapshot_tokens.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        categories = [e.category for e in errors]
        assert "SNAPSHOT_REF_INVALID" in categories


class TestCorpusManifestSourceIdsUnique:
    """Test corpus manifest source_ids must be unique."""

    def test_corpus_manifest_source_ids_unique(self):
        """Manifest source_ids must be unique."""
        data = _load_fixture("gc12_pass_multiple_citations_unique.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_corpus_manifest(manifest)
        assert len(errors) == 0

    def test_fixture_fail_duplicate_source_id(self):
        """FAIL fixture: duplicate source_id in manifest."""
        data = _load_fixture("gc12_fail_duplicate_source_id.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_corpus_manifest(manifest)
        categories = [e.category for e in errors]
        assert "CORPUS_SOURCE_ID_DUPLICATE" in categories


class TestCitationIdsUnique:
    """Test citation_ids must be unique."""

    def test_citation_ids_unique(self):
        """Citation ids must be unique."""
        data = _load_fixture("gc12_pass_multiple_citations_unique.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        assert len(errors) == 0

    def test_fixture_fail_duplicate_citation_id(self):
        """FAIL fixture: duplicate citation_id."""
        data = _load_fixture("gc12_fail_duplicate_citation_id.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_citations(citations, manifest)
        categories = [e.category for e in errors]
        assert "CITATION_ID_DUPLICATE" in categories


class TestCitedEvidenceReferencesResolveToCitationId:
    """Test citation evidence references resolve to citation_id."""

    def test_cited_evidence_references_resolve_to_citation_id(self):
        """Citation evidence must reference existing citation_id."""
        data = _load_fixture("gc12_pass_valid_manifest_citation_index_hash.json")
        citations = _build_citations_from_fixture(data)
        evidence_citation_ids = ["cit-001"]

        errors = validate_citation_evidence_linkage(evidence_citation_ids, citations)
        assert len(errors) == 0

    def test_fixture_fail_citation_evidence_unresolved(self):
        """FAIL fixture: citation evidence references missing citation_id."""
        data = _load_fixture("gc12_fail_citation_evidence_unresolved.json")
        citations = _build_citations_from_fixture(data)
        evidence_citation_ids = data["evidence_citation_ids"]

        errors = validate_citation_evidence_linkage(evidence_citation_ids, citations)
        categories = [e.category for e in errors]
        assert "CITATION_ID_UNRESOLVED" in categories


class TestRunManifestCarriesRetrievalRefWhenCitationsPresent:
    """Test RunManifest carries retrieval ref when citations present."""

    def test_run_manifest_carries_retrieval_ref_when_citations_present(self):
        """RunManifest should have retrieval log ref when citations have snapshot_ref."""
        citations = [
            Citation(
                citation_id="cit-001",
                source_id="source-001",
                location=CitationLocation(chunk_id="chunk-001"),
                snippet_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                snapshot_ref=RetrievalSnapshotRef(
                    index_hash="b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
                ),
            )
        ]
        run_manifest = RunManifest(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            input_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            deterministic_mode=False,
            tool_versions={"python": "3.11.0"},
            commit_hash="abc123",
            dependency_lock_hash="lock123",
            started_at="2024-01-15T10:00:00Z",
            ended_at="2024-01-15T10:05:00Z",
            log_references=[
                LogReference(
                    log_id="retrieval-log-001",
                    log_type=LogType.RETRIEVAL,
                    payload_ref="logs/retrieval/001.json",
                )
            ],
        )

        errors = validate_runmanifest_retrieval_linkage(run_manifest, citations)
        assert len(errors) == 0

    def test_run_manifest_missing_retrieval_ref_warning(self):
        """Warning when citations have snapshot_ref but RunManifest has no retrieval ref."""
        citations = [
            Citation(
                citation_id="cit-001",
                source_id="source-001",
                location=CitationLocation(chunk_id="chunk-001"),
                snippet_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                snapshot_ref=RetrievalSnapshotRef(
                    index_hash="b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
                ),
            )
        ]
        run_manifest = RunManifest(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            input_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            deterministic_mode=False,
            tool_versions={"python": "3.11.0"},
            commit_hash="abc123",
            dependency_lock_hash="lock123",
            started_at="2024-01-15T10:00:00Z",
            ended_at="2024-01-15T10:05:00Z",
            log_references=[
                LogReference(
                    log_id="branch-log-001",
                    log_type=LogType.BRANCH,
                    payload_ref="logs/branch/001.json",
                )
            ],
        )

        errors = validate_runmanifest_retrieval_linkage(run_manifest, citations)
        assert len(errors) == 1
        assert errors[0].category == "RUNMANIFEST_MISSING_RETRIEVAL_REF_WARNING"
        assert errors[0].is_warning is True


class TestCorpusManifestEntryValidation:
    """Test CorpusManifestEntry validation."""

    def test_valid_entry(self):
        """Valid entry passes validation."""
        entry = CorpusManifestEntry(
            source_id="source-001",
            title="Test Title",
            license_permission="CC-BY-4.0",
            version_edition="1st Edition",
            ingested_at="2024-01-15T10:00:00Z",
            content_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        )
        errors = validate_corpus_manifest_entry(entry)
        assert len(errors) == 0

    def test_fixture_fail_invalid_content_hash(self):
        """FAIL fixture: invalid content_hash."""
        data = _load_fixture("gc12_fail_invalid_content_hash.json")
        manifest = _build_manifest_from_fixture(data)

        errors = validate_corpus_manifest(manifest)
        categories = [e.category for e in errors]
        assert "CORPUS_SOURCE_HASH_INVALID" in categories


class TestCitationLocationSchema:
    """Test CitationLocation schema validation."""

    def test_valid_location_with_chunk_only(self):
        """Valid location with chunk_id only."""
        location = CitationLocation(chunk_id="chunk-001")
        assert location.chunk_id == "chunk-001"
        assert location.page_start is None

    def test_valid_location_with_page_range(self):
        """Valid location with page range."""
        location = CitationLocation(
            chunk_id="chunk-001",
            page_start=10,
            page_end=15,
        )
        assert location.page_start == 10
        assert location.page_end == 15

    def test_location_rejects_empty_chunk_id(self):
        """Empty chunk_id rejected."""
        with pytest.raises(ValueError, match="CITATION_LOCATION_INVALID"):
            CitationLocation(chunk_id="")


class TestRetrievalSnapshotRefSchema:
    """Test RetrievalSnapshotRef schema validation."""

    def test_valid_snapshot_ref_with_both(self):
        """Valid snapshot_ref with both fields."""
        ref = RetrievalSnapshotRef(
            retrieval_snapshot_id="snapshot-001",
            index_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        )
        assert ref.has_required_field() is True

    def test_snapshot_ref_with_neither(self):
        """Snapshot ref with neither field fails has_required_field."""
        ref = RetrievalSnapshotRef(created_at="2024-01-15T10:00:00Z")
        assert ref.has_required_field() is False

    def test_snapshot_ref_rejects_empty_retrieval_snapshot_id(self):
        """Empty retrieval_snapshot_id rejected."""
        with pytest.raises(ValueError, match="SNAPSHOT_REF_INVALID"):
            RetrievalSnapshotRef(retrieval_snapshot_id="")


class TestPassFixtures:
    """Test all PASS fixtures validate successfully."""

    def test_fixture_pass_valid_manifest_citation_index_hash(self):
        """PASS fixture: valid manifest + citation with index_hash."""
        data = _load_fixture("gc12_pass_valid_manifest_citation_index_hash.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        assert len(errors) == 0

    def test_fixture_pass_citation_both_snapshot_refs(self):
        """PASS fixture: citation with both snapshot refs."""
        data = _load_fixture("gc12_pass_citation_both_snapshot_refs.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        assert len(errors) == 0

    def test_fixture_pass_citation_chunk_page_range(self):
        """PASS fixture: citation with chunk + page range."""
        data = _load_fixture("gc12_pass_citation_chunk_page_range.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        assert len(errors) == 0

    def test_fixture_pass_multiple_citations_unique(self):
        """PASS fixture: multiple citations with unique ids."""
        data = _load_fixture("gc12_pass_multiple_citations_unique.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        assert len(errors) == 0


class TestFailFixtures:
    """Test all FAIL fixtures produce expected errors."""

    def test_fixture_fail_citation_source_unresolved(self):
        """FAIL fixture: citation source_id not in manifest."""
        data = _load_fixture("gc12_fail_citation_source_unresolved.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "CITATION_SOURCE_UNRESOLVED" in categories

    def test_fixture_fail_duplicate_source_id(self):
        """FAIL fixture: duplicate source_id."""
        data = _load_fixture("gc12_fail_duplicate_source_id.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "CORPUS_SOURCE_ID_DUPLICATE" in categories

    def test_fixture_fail_duplicate_citation_id(self):
        """FAIL fixture: duplicate citation_id."""
        data = _load_fixture("gc12_fail_duplicate_citation_id.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "CITATION_ID_DUPLICATE" in categories

    def test_fixture_fail_whitespace_chunk_id(self):
        """FAIL fixture: whitespace in chunk_id."""
        data = _load_fixture("gc12_fail_whitespace_chunk_id.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "CITATION_LOCATION_INVALID" in categories

    def test_fixture_fail_missing_both_snapshot_refs(self):
        """FAIL fixture: missing both snapshot refs."""
        data = _load_fixture("gc12_fail_missing_both_snapshot_refs.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "CITATION_SNAPSHOT_REF_MISSING" in categories

    def test_fixture_fail_invalid_snapshot_tokens(self):
        """FAIL fixture: invalid snapshot tokens."""
        data = _load_fixture("gc12_fail_invalid_snapshot_tokens.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "SNAPSHOT_REF_INVALID" in categories

    def test_fixture_fail_invalid_content_hash(self):
        """FAIL fixture: invalid content_hash."""
        data = _load_fixture("gc12_fail_invalid_content_hash.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)

        errors = validate_corpus_provenance(manifest, citations)
        categories = [e.category for e in errors]
        assert "CORPUS_SOURCE_HASH_INVALID" in categories

    def test_fixture_fail_citation_evidence_unresolved(self):
        """FAIL fixture: citation evidence unresolved."""
        data = _load_fixture("gc12_fail_citation_evidence_unresolved.json")
        manifest = _build_manifest_from_fixture(data)
        citations = _build_citations_from_fixture(data)
        evidence_citation_ids = data["evidence_citation_ids"]

        errors = validate_corpus_provenance(
            manifest, citations, evidence_citation_ids=evidence_citation_ids
        )
        categories = [e.category for e in errors]
        assert "CITATION_ID_UNRESOLVED" in categories
