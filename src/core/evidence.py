"""
GC-4 Evidence Object Schema

Minimal evidence schema for GC-4. Evidence type semantics enforced in GC-5+.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EvidenceObject:
    """
    GC-4: Minimal evidence object for claim support.
    
    GC-4 enforces ONLY that evidence_ids resolve to real entries.
    Evidence type correctness and content richness enforced in GC-5+.
    
    Fields:
    - evidence_id: Unique identifier (REQUIRED)
    - evidence_type: Optional type hint (not validated in GC-4)
    - content: Optional evidence content (not validated in GC-4)
    - source: Optional source information (not validated in GC-4)
    """
    evidence_id: str
    evidence_type: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    
    def __post_init__(self):
        # GC-4: evidence_id must be non-empty
        if not self.evidence_id:
            raise ValueError("EvidenceObject: evidence_id must be non-empty (GC-4)")
        
        # GC-4 WIRE-BOUNDARY HARDENING: NO TRIMMING
        # Reject whitespace-only or whitespace variants
        if not self.evidence_id.strip():
            raise ValueError("EvidenceObject: evidence_id is whitespace-only (GC-4)")
        
        if self.evidence_id != self.evidence_id.strip():
            raise ValueError(
                f"EvidenceObject: evidence_id {repr(self.evidence_id)} has leading/trailing "
                f"whitespace (GC-4: whitespace variants rejected)"
            )
