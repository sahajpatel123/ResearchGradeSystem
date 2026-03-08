"""
GC-12 Validators: Corpus Provenance + Citation Traceability.

Implements all validation rules for GC-12 Corpus Provenance Contract.
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.corpus_manifest import (
    Citation,
    CitationLocation,
    CorpusManifest,
    CorpusManifestEntry,
    RetrievalSnapshotRef,
)
from src.core.gc12_parsers import (
    parse_chunk_id,
    parse_citation_id,
    parse_content_hash,
    parse_index_hash,
    parse_retrieval_snapshot_id,
    parse_snippet_hash,
    parse_source_id,
)
from src.core.run_manifest import LogType, RunManifest


@dataclass
class GC12ValidationError:
    """GC-12 validation error with category and message."""
    category: str
    message: str
    field: Optional[str] = None
    is_warning: bool = False


def validate_corpus_manifest_entry(entry: CorpusManifestEntry) -> list[GC12ValidationError]:
    """Validate a single CorpusManifestEntry."""
    errors = []
    
    # Validate source_id
    try:
        parse_source_id(entry.source_id)
    except (ValueError, TypeError) as e:
        errors.append(GC12ValidationError(
            category="CORPUS_SOURCE_MISSING_FIELD",
            message=str(e),
            field="source_id"
        ))
    
    # Validate required string fields are non-empty
    if entry.title == "":
        errors.append(GC12ValidationError(
            category="CORPUS_SOURCE_MISSING_FIELD",
            message="title must be non-empty (GC-12: CORPUS_SOURCE_MISSING_FIELD)",
            field="title"
        ))
    
    if entry.license_permission == "":
        errors.append(GC12ValidationError(
            category="CORPUS_SOURCE_MISSING_FIELD",
            message="license_permission must be non-empty (GC-12: CORPUS_SOURCE_MISSING_FIELD)",
            field="license_permission"
        ))
    
    if entry.version_edition == "":
        errors.append(GC12ValidationError(
            category="CORPUS_SOURCE_MISSING_FIELD",
            message="version_edition must be non-empty (GC-12: CORPUS_SOURCE_MISSING_FIELD)",
            field="version_edition"
        ))
    
    if entry.ingested_at == "":
        errors.append(GC12ValidationError(
            category="CORPUS_SOURCE_MISSING_FIELD",
            message="ingested_at must be non-empty (GC-12: CORPUS_SOURCE_MISSING_FIELD)",
            field="ingested_at"
        ))
    
    # Validate content_hash
    try:
        parse_content_hash(entry.content_hash)
    except (ValueError, TypeError) as e:
        errors.append(GC12ValidationError(
            category="CORPUS_SOURCE_HASH_INVALID",
            message=str(e),
            field="content_hash"
        ))
    
    return errors


def validate_corpus_manifest(manifest: CorpusManifest) -> list[GC12ValidationError]:
    """
    Validate CorpusManifest.
    
    Rules:
    - All entries must be valid
    - source_id must be unique across entries
    """
    errors = []
    
    # Validate each entry
    for i, entry in enumerate(manifest.entries):
        entry_errors = validate_corpus_manifest_entry(entry)
        for err in entry_errors:
            err.field = f"entries[{i}].{err.field}"
            errors.append(err)
    
    # Check source_id uniqueness
    seen_source_ids: dict[str, int] = {}
    for i, entry in enumerate(manifest.entries):
        if entry.source_id in seen_source_ids:
            errors.append(GC12ValidationError(
                category="CORPUS_SOURCE_ID_DUPLICATE",
                message=f"source_id '{entry.source_id}' is duplicate "
                        f"(first at index {seen_source_ids[entry.source_id]}, again at {i}) "
                        "(GC-12: CORPUS_SOURCE_ID_DUPLICATE)",
                field=f"entries[{i}].source_id"
            ))
        else:
            seen_source_ids[entry.source_id] = i
    
    return errors


def validate_snapshot_ref(snapshot_ref: RetrievalSnapshotRef) -> list[GC12ValidationError]:
    """
    Validate RetrievalSnapshotRef.
    
    Rules:
    - At least one of retrieval_snapshot_id or index_hash required
    - If provided, tokens must be valid
    """
    errors = []
    
    # Check at-least-one rule
    if not snapshot_ref.has_required_field():
        errors.append(GC12ValidationError(
            category="CITATION_SNAPSHOT_REF_MISSING",
            message="snapshot_ref must have at least one of retrieval_snapshot_id or index_hash "
                    "(GC-12: CITATION_SNAPSHOT_REF_MISSING)",
            field="snapshot_ref"
        ))
        return errors
    
    # Validate retrieval_snapshot_id if provided
    if snapshot_ref.retrieval_snapshot_id is not None:
        try:
            parse_retrieval_snapshot_id(snapshot_ref.retrieval_snapshot_id)
        except (ValueError, TypeError) as e:
            errors.append(GC12ValidationError(
                category="SNAPSHOT_REF_INVALID",
                message=str(e),
                field="snapshot_ref.retrieval_snapshot_id"
            ))
    
    # Validate index_hash if provided
    if snapshot_ref.index_hash is not None:
        try:
            parse_index_hash(snapshot_ref.index_hash)
        except (ValueError, TypeError) as e:
            errors.append(GC12ValidationError(
                category="SNAPSHOT_REF_INVALID",
                message=str(e),
                field="snapshot_ref.index_hash"
            ))
    
    return errors


def validate_citation_location(location: CitationLocation) -> list[GC12ValidationError]:
    """
    Validate CitationLocation.
    
    Rules:
    - chunk_id is required and must be valid strict token
    """
    errors = []
    
    try:
        parse_chunk_id(location.chunk_id)
    except (ValueError, TypeError) as e:
        errors.append(GC12ValidationError(
            category="CITATION_LOCATION_INVALID",
            message=str(e),
            field="location.chunk_id"
        ))
    
    return errors


def validate_citation(
    citation: Citation,
    manifest: CorpusManifest
) -> list[GC12ValidationError]:
    """
    Validate a single Citation.
    
    Rules:
    - citation_id must be valid strict token
    - source_id must resolve to manifest
    - location must be valid with chunk_id
    - snippet_hash must be valid
    - snapshot_ref must have at least one field
    """
    errors = []
    
    # Validate citation_id
    try:
        parse_citation_id(citation.citation_id)
    except (ValueError, TypeError) as e:
        errors.append(GC12ValidationError(
            category="CITATION_ID_INVALID",
            message=str(e),
            field="citation_id"
        ))
    
    # Validate source_id resolves to manifest
    try:
        parse_source_id(citation.source_id)
        if not manifest.has_source(citation.source_id):
            errors.append(GC12ValidationError(
                category="CITATION_SOURCE_UNRESOLVED",
                message=f"source_id '{citation.source_id}' not found in corpus manifest "
                        "(GC-12: CITATION_SOURCE_UNRESOLVED)",
                field="source_id"
            ))
    except (ValueError, TypeError) as e:
        errors.append(GC12ValidationError(
            category="CITATION_SOURCE_UNRESOLVED",
            message=str(e),
            field="source_id"
        ))
    
    # Validate location
    location_errors = validate_citation_location(citation.location)
    errors.extend(location_errors)
    
    # Validate snippet_hash
    try:
        parse_snippet_hash(citation.snippet_hash)
    except (ValueError, TypeError) as e:
        if "missing" in str(e).lower():
            errors.append(GC12ValidationError(
                category="CITATION_SNIPPET_HASH_MISSING",
                message=str(e),
                field="snippet_hash"
            ))
        else:
            errors.append(GC12ValidationError(
                category="CITATION_SNIPPET_HASH_INVALID",
                message=str(e),
                field="snippet_hash"
            ))
    
    # Validate snapshot_ref
    snapshot_errors = validate_snapshot_ref(citation.snapshot_ref)
    errors.extend(snapshot_errors)
    
    return errors


def validate_citations(
    citations: list[Citation],
    manifest: CorpusManifest
) -> list[GC12ValidationError]:
    """
    Validate a list of Citations.
    
    Rules:
    - All citations must be valid
    - citation_id must be unique across citations
    """
    errors = []
    
    # Validate each citation
    for i, citation in enumerate(citations):
        citation_errors = validate_citation(citation, manifest)
        for err in citation_errors:
            err.field = f"citations[{i}].{err.field}"
            errors.append(err)
    
    # Check citation_id uniqueness
    seen_citation_ids: dict[str, int] = {}
    for i, citation in enumerate(citations):
        if citation.citation_id in seen_citation_ids:
            errors.append(GC12ValidationError(
                category="CITATION_ID_DUPLICATE",
                message=f"citation_id '{citation.citation_id}' is duplicate "
                        f"(first at index {seen_citation_ids[citation.citation_id]}, again at {i}) "
                        "(GC-12: CITATION_ID_DUPLICATE)",
                field=f"citations[{i}].citation_id"
            ))
        else:
            seen_citation_ids[citation.citation_id] = i
    
    return errors


def validate_citation_evidence_linkage(
    evidence_citation_ids: list[str],
    citations: list[Citation]
) -> list[GC12ValidationError]:
    """
    Validate that citation evidence references resolve to citation_ids.
    
    Args:
        evidence_citation_ids: List of citation_ids referenced by EvidenceObjects
        citations: List of Citation objects in the report
        
    Returns:
        List of validation errors for unresolved citation references
    """
    errors = []
    
    citation_id_set = {c.citation_id for c in citations}
    
    for i, cit_id in enumerate(evidence_citation_ids):
        if cit_id not in citation_id_set:
            errors.append(GC12ValidationError(
                category="CITATION_ID_UNRESOLVED",
                message=f"citation evidence references citation_id '{cit_id}' "
                        "which is not in citations list "
                        "(GC-12: CITATION_ID_UNRESOLVED)",
                field=f"evidence_citation_ids[{i}]"
            ))
    
    return errors


def validate_runmanifest_retrieval_linkage(
    run_manifest: RunManifest,
    citations: list[Citation]
) -> list[GC12ValidationError]:
    """
    Validate RunManifest carries retrieval ref when citations present.
    
    If citations have snapshot_ref with retrieval_snapshot_id or index_hash,
    RunManifest should include a retrieval log reference.
    
    This is a WARNING (not hard fail) for v0.
    """
    errors = []
    
    if not citations:
        return errors
    
    # Check if any citation has snapshot_ref with retrieval info
    has_retrieval_snapshot = any(
        c.snapshot_ref.retrieval_snapshot_id is not None or
        c.snapshot_ref.index_hash is not None
        for c in citations
    )
    
    if not has_retrieval_snapshot:
        return errors
    
    # Check if RunManifest has retrieval log reference
    has_retrieval_log = any(
        ref.log_type == LogType.RETRIEVAL
        for ref in run_manifest.log_references
    )
    
    if not has_retrieval_log:
        errors.append(GC12ValidationError(
            category="RUNMANIFEST_MISSING_RETRIEVAL_REF_WARNING",
            message="Citations have snapshot_ref but RunManifest has no retrieval log reference "
                    "(GC-12: RUNMANIFEST_MISSING_RETRIEVAL_REF_WARNING)",
            field="log_references",
            is_warning=True
        ))
    
    return errors


def validate_corpus_provenance(
    manifest: CorpusManifest,
    citations: list[Citation],
    evidence_citation_ids: Optional[list[str]] = None,
    run_manifest: Optional[RunManifest] = None
) -> list[GC12ValidationError]:
    """
    Validate complete corpus provenance.
    
    Validates:
    - CorpusManifest entries
    - Citations with source resolution
    - Citation evidence linkage (if provided)
    - RunManifest retrieval linkage (if provided)
    """
    errors = []
    
    # Validate manifest
    errors.extend(validate_corpus_manifest(manifest))
    
    # Validate citations
    errors.extend(validate_citations(citations, manifest))
    
    # Validate citation evidence linkage
    if evidence_citation_ids is not None:
        errors.extend(validate_citation_evidence_linkage(evidence_citation_ids, citations))
    
    # Validate RunManifest retrieval linkage
    if run_manifest is not None:
        errors.extend(validate_runmanifest_retrieval_linkage(run_manifest, citations))
    
    return errors
