"""
GC-12 Corpus Provenance Schema: Citations + Manifest + Snapshot References.

Defines the CorpusManifest, Citation, and related schemas for making
citations auditable and traceable.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CorpusManifestEntry:
    """
    GC-12 corpus manifest entry.
    
    Each entry represents a source document in the corpus with:
    - source_id: unique identifier for the source
    - title: human-readable title
    - license_permission: license/permission status
    - version_edition: version or edition identifier
    - ingested_at: ISO8601 timestamp of ingestion
    - content_hash: sha256 hex hash of source content
    """
    source_id: str
    title: str
    license_permission: str
    version_edition: str
    ingested_at: str
    content_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str):
            raise TypeError(
                f"source_id must be str, got {type(self.source_id).__name__} "
                "(GC-12: CORPUS_SOURCE_MISSING_FIELD)"
            )
        if self.source_id == "":
            raise ValueError(
                "source_id must be non-empty (GC-12: CORPUS_SOURCE_MISSING_FIELD)"
            )
        if not isinstance(self.title, str):
            raise TypeError(
                f"title must be str, got {type(self.title).__name__} "
                "(GC-12: CORPUS_SOURCE_MISSING_FIELD)"
            )
        if not isinstance(self.license_permission, str):
            raise TypeError(
                f"license_permission must be str, got {type(self.license_permission).__name__} "
                "(GC-12: CORPUS_SOURCE_MISSING_FIELD)"
            )
        if not isinstance(self.version_edition, str):
            raise TypeError(
                f"version_edition must be str, got {type(self.version_edition).__name__} "
                "(GC-12: CORPUS_SOURCE_MISSING_FIELD)"
            )
        if not isinstance(self.ingested_at, str):
            raise TypeError(
                f"ingested_at must be str, got {type(self.ingested_at).__name__} "
                "(GC-12: CORPUS_SOURCE_MISSING_FIELD)"
            )
        if not isinstance(self.content_hash, str):
            raise TypeError(
                f"content_hash must be str, got {type(self.content_hash).__name__} "
                "(GC-12: CORPUS_SOURCE_HASH_INVALID)"
            )
        if self.content_hash == "":
            raise ValueError(
                "content_hash must be non-empty (GC-12: CORPUS_SOURCE_HASH_INVALID)"
            )


@dataclass
class CorpusManifest:
    """
    GC-12 corpus manifest.
    
    Contains all source entries with unique source_ids.
    """
    entries: list[CorpusManifestEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, list):
            raise TypeError(
                f"entries must be list, got {type(self.entries).__name__} "
                "(GC-12: CORPUS_MANIFEST_INVALID)"
            )

    def get_entry(self, source_id: str) -> Optional[CorpusManifestEntry]:
        """Get entry by source_id, or None if not found."""
        for entry in self.entries:
            if entry.source_id == source_id:
                return entry
        return None

    def has_source(self, source_id: str) -> bool:
        """Check if source_id exists in manifest."""
        return self.get_entry(source_id) is not None


@dataclass
class RetrievalSnapshotRef:
    """
    GC-12 retrieval snapshot reference.
    
    Ties a citation to the retrieval/index state at time of retrieval.
    
    Rule: at least one of retrieval_snapshot_id or index_hash REQUIRED.
    Both allowed and preferred when retrieval ran.
    
    Fields:
    - retrieval_snapshot_id: identifier for the retrieval snapshot
    - index_hash: hash of the index state
    - created_at: ISO8601 timestamp when snapshot was created
    """
    retrieval_snapshot_id: Optional[str] = None
    index_hash: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.retrieval_snapshot_id is not None:
            if not isinstance(self.retrieval_snapshot_id, str):
                raise TypeError(
                    f"retrieval_snapshot_id must be str or None, got {type(self.retrieval_snapshot_id).__name__} "
                    "(GC-12: SNAPSHOT_REF_INVALID)"
                )
            if self.retrieval_snapshot_id == "":
                raise ValueError(
                    "retrieval_snapshot_id must be non-empty if provided "
                    "(GC-12: SNAPSHOT_REF_INVALID)"
                )
        if self.index_hash is not None:
            if not isinstance(self.index_hash, str):
                raise TypeError(
                    f"index_hash must be str or None, got {type(self.index_hash).__name__} "
                    "(GC-12: SNAPSHOT_REF_INVALID)"
                )
            if self.index_hash == "":
                raise ValueError(
                    "index_hash must be non-empty if provided "
                    "(GC-12: SNAPSHOT_REF_INVALID)"
                )
        if self.created_at is not None:
            if not isinstance(self.created_at, str):
                raise TypeError(
                    f"created_at must be str or None, got {type(self.created_at).__name__} "
                    "(GC-12: SNAPSHOT_REF_INVALID)"
                )

    def has_required_field(self) -> bool:
        """Check if at least one of retrieval_snapshot_id or index_hash is present."""
        return (
            self.retrieval_snapshot_id is not None or
            self.index_hash is not None
        )


@dataclass
class CitationLocation:
    """
    GC-12 citation location.
    
    Anchors a citation to a specific chunk in the source.
    
    chunk_id is REQUIRED (primary location key).
    Page and character ranges are optional.
    """
    chunk_id: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.chunk_id, str):
            raise TypeError(
                f"chunk_id must be str, got {type(self.chunk_id).__name__} "
                "(GC-12: CITATION_LOCATION_INVALID)"
            )
        if self.chunk_id == "":
            raise ValueError(
                "chunk_id must be non-empty (GC-12: CITATION_LOCATION_INVALID)"
            )
        if self.page_start is not None:
            if isinstance(self.page_start, bool) or not isinstance(self.page_start, int):
                raise TypeError(
                    f"page_start must be int or None, got {type(self.page_start).__name__} "
                    "(GC-12: CITATION_LOCATION_INVALID)"
                )
        if self.page_end is not None:
            if isinstance(self.page_end, bool) or not isinstance(self.page_end, int):
                raise TypeError(
                    f"page_end must be int or None, got {type(self.page_end).__name__} "
                    "(GC-12: CITATION_LOCATION_INVALID)"
                )
        if self.char_start is not None:
            if isinstance(self.char_start, bool) or not isinstance(self.char_start, int):
                raise TypeError(
                    f"char_start must be int or None, got {type(self.char_start).__name__} "
                    "(GC-12: CITATION_LOCATION_INVALID)"
                )
        if self.char_end is not None:
            if isinstance(self.char_end, bool) or not isinstance(self.char_end, int):
                raise TypeError(
                    f"char_end must be int or None, got {type(self.char_end).__name__} "
                    "(GC-12: CITATION_LOCATION_INVALID)"
                )


@dataclass
class Citation:
    """
    GC-12 citation.
    
    Links a claim to a specific location in a source document.
    
    Required fields:
    - citation_id: unique identifier for this citation
    - source_id: references CorpusManifestEntry.source_id
    - location: CitationLocation with chunk_id required
    - snippet_hash: sha256 hex hash of exact snippet bytes (UTF-8, no normalization)
    - snapshot_ref: RetrievalSnapshotRef with at least one field required
    """
    citation_id: str
    source_id: str
    location: CitationLocation
    snippet_hash: str
    snapshot_ref: RetrievalSnapshotRef

    def __post_init__(self) -> None:
        if not isinstance(self.citation_id, str):
            raise TypeError(
                f"citation_id must be str, got {type(self.citation_id).__name__} "
                "(GC-12: CITATION_ID_INVALID)"
            )
        if self.citation_id == "":
            raise ValueError(
                "citation_id must be non-empty (GC-12: CITATION_ID_INVALID)"
            )
        if not isinstance(self.source_id, str):
            raise TypeError(
                f"source_id must be str, got {type(self.source_id).__name__} "
                "(GC-12: CITATION_SOURCE_INVALID)"
            )
        if self.source_id == "":
            raise ValueError(
                "source_id must be non-empty (GC-12: CITATION_SOURCE_INVALID)"
            )
        if not isinstance(self.location, CitationLocation):
            raise TypeError(
                f"location must be CitationLocation, got {type(self.location).__name__} "
                "(GC-12: CITATION_LOCATION_MISSING)"
            )
        if not isinstance(self.snippet_hash, str):
            raise TypeError(
                f"snippet_hash must be str, got {type(self.snippet_hash).__name__} "
                "(GC-12: CITATION_SNIPPET_HASH_MISSING)"
            )
        if self.snippet_hash == "":
            raise ValueError(
                "snippet_hash must be non-empty (GC-12: CITATION_SNIPPET_HASH_MISSING)"
            )
        if not isinstance(self.snapshot_ref, RetrievalSnapshotRef):
            raise TypeError(
                f"snapshot_ref must be RetrievalSnapshotRef, got {type(self.snapshot_ref).__name__} "
                "(GC-12: CITATION_SNAPSHOT_REF_MISSING)"
            )
