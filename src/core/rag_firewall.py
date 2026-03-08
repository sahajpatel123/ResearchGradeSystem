"""
GC-14 RAG Instruction Firewall: Retrieved Text Is Data, Not Authority.

PRIMARY ENFORCEMENT: Architectural separation.
- Retrieved text is typed content-only (RetrievalResult).
- Planner/executor interfaces do NOT accept raw snippet_text as commands.
- Tool invocation layer is not callable from retrieval pipeline.

SECONDARY ENFORCEMENT: Detection hooks for logging/observability.
- detect_instruction_like_content() flags suspicious patterns.
- Flags produce metadata + event logs only.
- Even if flags empty, retrieved text still cannot gain authority.

GC-14 ensures retrieved text cannot change:
- tool calls
- planner directives
- policy overrides
- status FINAL/INCOMPLETE (GC-13)
- confidence overrides
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# =============================================================================
# FIREWALL CONFIG (enabled by default)
# =============================================================================

RAG_INSTRUCTION_FIREWALL_ENABLED: bool = True


class FirewallMode(Enum):
    """Firewall operation mode."""
    ENABLED = "ENABLED"
    DISABLED_DEV = "DISABLED_DEV"  # Dev mode - emits warning


def get_firewall_enabled() -> bool:
    """Get current firewall enabled state."""
    return RAG_INSTRUCTION_FIREWALL_ENABLED


def set_firewall_enabled(enabled: bool) -> list["RagFirewallEvent"]:
    """
    Set firewall enabled state.
    
    If disabling, emits RAG_FIREWALL_POLICY_DISABLED event.
    
    Returns:
        List of events emitted (empty if enabling, one event if disabling)
    """
    global RAG_INSTRUCTION_FIREWALL_ENABLED
    events = []
    
    if not enabled and RAG_INSTRUCTION_FIREWALL_ENABLED:
        # Disabling firewall - emit warning event
        events.append(RagFirewallEvent(
            event_id=f"fw-{uuid.uuid4().hex[:12]}",
            run_id=None,
            source_id=None,
            location=None,
            snippet_hash=None,
            flag_type="RAG_FIREWALL_POLICY_DISABLED",
            action_taken="firewall_disabled",
            created_at=datetime.now(timezone.utc).isoformat(),
            seq=0,
        ))
    
    RAG_INSTRUCTION_FIREWALL_ENABLED = enabled
    return events


# =============================================================================
# DETECTION FLAGS (v0 frozen set)
# =============================================================================

class InstructionLikeFlag(Enum):
    """
    GC-14 instruction-like content flags.
    
    These are SECONDARY enforcement - for logging/observability only.
    Even if no flags detected, retrieved text has no authority.
    """
    PROMPT_INJECTION_PATTERN = "PROMPT_INJECTION_PATTERN"
    POLICY_OVERRIDE_PATTERN = "POLICY_OVERRIDE_PATTERN"
    TOOL_TRIGGER_PATTERN = "TOOL_TRIGGER_PATTERN"
    STATUS_OVERRIDE_PATTERN = "STATUS_OVERRIDE_PATTERN"


# Detection patterns (case-insensitive)
_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
    r"ignore\s+all\s+previous\s+instructions?",
    r"disregard\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
    r"forget\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)",
    r"you\s+are\s+now\s+",
    r"new\s+instructions?:",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"<<SYS>>",
]

_POLICY_OVERRIDE_PATTERNS = [
    r"override\s+policy",
    r"bypass\s+(safety|policy|rules?)",
    r"disable\s+(safety|policy|rules?)",
    r"ignore\s+(safety|policy|rules?)",
    r"set\s+policy\s*=",
    r"policy\s*:\s*disabled",
]

_TOOL_TRIGGER_PATTERNS = [
    r"execute\s+(tool|function|command)",
    r"run\s+(tool|function|command)",
    r"call\s+(tool|function)",
    r"invoke\s+(tool|function)",
    r"<tool_call>",
    r"<function_call>",
    r"\{\s*\"tool\"",
    r"\{\s*\"function\"",
]

_STATUS_OVERRIDE_PATTERNS = [
    r"set\s+status\s*=\s*(FINAL|INCOMPLETE)",
    r"status\s*:\s*(FINAL|INCOMPLETE)",
    r"mark\s+(as\s+)?(FINAL|INCOMPLETE)",
    r"override\s+status",
    r"force\s+status",
    r"missing_artifacts\s*=\s*\[\s*\]",
    r"confidence\s*=\s*(HIGH|MEDIUM|LOW)",
]


def detect_instruction_like_content(snippet_text: str) -> list[InstructionLikeFlag]:
    """
    Detect instruction-like content in retrieved text.
    
    GC-14 SECONDARY ENFORCEMENT:
    - This is for logging/observability only.
    - Even if no flags detected, retrieved text has no authority.
    - Flags produce metadata + event logs.
    
    Args:
        snippet_text: The retrieved text to scan
        
    Returns:
        List of detected flags (may be empty)
    """
    if not isinstance(snippet_text, str):
        return []
    
    flags = []
    text_lower = snippet_text.lower()
    
    # Check prompt injection patterns
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            flags.append(InstructionLikeFlag.PROMPT_INJECTION_PATTERN)
            break
    
    # Check policy override patterns
    for pattern in _POLICY_OVERRIDE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            flags.append(InstructionLikeFlag.POLICY_OVERRIDE_PATTERN)
            break
    
    # Check tool trigger patterns
    for pattern in _TOOL_TRIGGER_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            flags.append(InstructionLikeFlag.TOOL_TRIGGER_PATTERN)
            break
    
    # Check status override patterns
    for pattern in _STATUS_OVERRIDE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            flags.append(InstructionLikeFlag.STATUS_OVERRIDE_PATTERN)
            break
    
    return flags


# =============================================================================
# RETRIEVAL RESULT (typed content-only output)
# =============================================================================

@dataclass
class RetrievalLocation:
    """Location within a retrieved source."""
    chunk_id: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


@dataclass
class RetrievalSnapshotRef:
    """Snapshot reference for retrieval provenance (GC-12)."""
    retrieval_snapshot_id: Optional[str] = None
    index_hash: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class RetrievalResult:
    """
    GC-14 typed retrieval output (content-only).
    
    PRIMARY ENFORCEMENT:
    - This is the ONLY way retrieved text enters the system.
    - Planner/executor interfaces accept ONLY RetrievalResult objects.
    - Raw snippet_text CANNOT reach authority channels.
    
    Fields:
    - source_id: Source document identifier
    - location: Chunk/page/char location
    - snippet_text: The retrieved text content (DATA, not AUTHORITY)
    - snippet_hash: SHA256 hash of snippet_text (GC-12)
    - snapshot_ref: Retrieval snapshot reference (GC-12)
    - instruction_like_flags: Detected flags (metadata only)
    - firewall_ignored_segments: Segments ignored operationally (metadata only)
    """
    source_id: str
    location: RetrievalLocation
    snippet_text: str
    snippet_hash: str
    snapshot_ref: Optional[RetrievalSnapshotRef] = None
    instruction_like_flags: list[InstructionLikeFlag] = field(default_factory=list)
    firewall_ignored_segments: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or self.source_id.strip() == "":
            raise ValueError("source_id must be non-empty string")
        if not isinstance(self.location, RetrievalLocation):
            raise TypeError("location must be RetrievalLocation")
        if not isinstance(self.snippet_text, str):
            raise TypeError("snippet_text must be str")
        if not isinstance(self.snippet_hash, str) or len(self.snippet_hash) != 64:
            raise ValueError("snippet_hash must be 64-char hex string")

    def has_instruction_like_content(self) -> bool:
        """Check if any instruction-like flags were detected."""
        return len(self.instruction_like_flags) > 0

    def get_safe_content_for_citation(self) -> str:
        """
        Get snippet text for citation purposes.
        
        GC-14: Retrieved text can inform citations.
        This is safe because citations are DATA, not AUTHORITY.
        """
        return self.snippet_text

    def get_safe_content_for_display(self) -> str:
        """
        Get snippet text for human display.
        
        GC-14: Retrieved text can be displayed to humans.
        This is safe because display is DATA, not AUTHORITY.
        """
        return self.snippet_text


# =============================================================================
# FIREWALL EVENT LOGGING
# =============================================================================

class FirewallEventCategory(Enum):
    """GC-14 firewall event categories."""
    RETRIEVED_INSTRUCTION_IGNORED = "RETRIEVED_INSTRUCTION_IGNORED"
    RETRIEVED_POLICY_OVERRIDE_IGNORED = "RETRIEVED_POLICY_OVERRIDE_IGNORED"
    RETRIEVED_TOOL_TRIGGER_IGNORED = "RETRIEVED_TOOL_TRIGGER_IGNORED"
    RETRIEVED_STATUS_OVERRIDE_IGNORED = "RETRIEVED_STATUS_OVERRIDE_IGNORED"
    RAG_FIREWALL_POLICY_DISABLED = "RAG_FIREWALL_POLICY_DISABLED"


# Map flags to event categories
_FLAG_TO_EVENT_CATEGORY = {
    InstructionLikeFlag.PROMPT_INJECTION_PATTERN: FirewallEventCategory.RETRIEVED_INSTRUCTION_IGNORED,
    InstructionLikeFlag.POLICY_OVERRIDE_PATTERN: FirewallEventCategory.RETRIEVED_POLICY_OVERRIDE_IGNORED,
    InstructionLikeFlag.TOOL_TRIGGER_PATTERN: FirewallEventCategory.RETRIEVED_TOOL_TRIGGER_IGNORED,
    InstructionLikeFlag.STATUS_OVERRIDE_PATTERN: FirewallEventCategory.RETRIEVED_STATUS_OVERRIDE_IGNORED,
}


@dataclass
class RagFirewallEvent:
    """
    GC-14 firewall event for audit logging.
    
    Emitted when instruction-like content is detected in retrieved text.
    """
    event_id: str
    run_id: Optional[str]
    source_id: Optional[str]
    location: Optional[RetrievalLocation]
    snippet_hash: Optional[str]
    flag_type: str
    action_taken: str
    created_at: str
    seq: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "source_id": self.source_id,
            "location": {
                "chunk_id": self.location.chunk_id,
                "page_start": self.location.page_start,
                "page_end": self.location.page_end,
            } if self.location else None,
            "snippet_hash": self.snippet_hash,
            "flag_type": self.flag_type,
            "action_taken": self.action_taken,
            "created_at": self.created_at,
            "seq": self.seq,
        }


class FirewallEventLog:
    """GC-14 firewall event log for a run."""
    
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id
        self.events: list[RagFirewallEvent] = []
        self._seq_counter = 0

    def emit_event(
        self,
        flag: InstructionLikeFlag,
        source_id: str,
        location: RetrievalLocation,
        snippet_hash: str,
    ) -> RagFirewallEvent:
        """
        Emit a firewall event for detected instruction-like content.
        
        Args:
            flag: The detected flag
            source_id: Source document ID
            location: Location in source
            snippet_hash: Hash of snippet
            
        Returns:
            The emitted event
        """
        category = _FLAG_TO_EVENT_CATEGORY.get(flag)
        if category is None:
            category_str = flag.value
        else:
            category_str = category.value
        
        event = RagFirewallEvent(
            event_id=f"fw-{uuid.uuid4().hex[:12]}",
            run_id=self.run_id,
            source_id=source_id,
            location=location,
            snippet_hash=snippet_hash,
            flag_type=category_str,
            action_taken="ignored_operationally",
            created_at=datetime.now(timezone.utc).isoformat(),
            seq=self._seq_counter,
        )
        self._seq_counter += 1
        self.events.append(event)
        return event

    def get_events(self) -> list[RagFirewallEvent]:
        """Get all logged events."""
        return self.events.copy()


# =============================================================================
# RETRIEVAL PIPELINE (safe-by-construction)
# =============================================================================

def process_retrieval(
    source_id: str,
    location: RetrievalLocation,
    snippet_text: str,
    snippet_hash: str,
    snapshot_ref: Optional[RetrievalSnapshotRef] = None,
    event_log: Optional[FirewallEventLog] = None,
) -> RetrievalResult:
    """
    Process retrieved text through the GC-14 firewall.
    
    PRIMARY ENFORCEMENT (architectural):
    - Returns typed RetrievalResult, not raw string.
    - Downstream can only access content through RetrievalResult methods.
    - Planner/executor interfaces cannot accept raw snippet_text.
    
    SECONDARY ENFORCEMENT (detection):
    - Scans for instruction-like content.
    - Logs firewall events for detected patterns.
    - Flags are metadata only; text still has no authority.
    
    Args:
        source_id: Source document identifier
        location: Location in source
        snippet_text: The retrieved text
        snippet_hash: SHA256 hash of snippet_text
        snapshot_ref: Optional retrieval snapshot reference
        event_log: Optional event log for firewall events
        
    Returns:
        RetrievalResult with detected flags as metadata
    """
    # Detect instruction-like content (secondary enforcement)
    flags = detect_instruction_like_content(snippet_text)
    
    # Log firewall events for detected flags
    if event_log is not None and flags:
        for flag in flags:
            event_log.emit_event(
                flag=flag,
                source_id=source_id,
                location=location,
                snippet_hash=snippet_hash,
            )
    
    # Return typed result (primary enforcement)
    # The snippet_text is DATA, not AUTHORITY
    return RetrievalResult(
        source_id=source_id,
        location=location,
        snippet_text=snippet_text,
        snippet_hash=snippet_hash,
        snapshot_ref=snapshot_ref,
        instruction_like_flags=flags,
        firewall_ignored_segments=[],  # Could be populated by more sophisticated parsing
    )


# =============================================================================
# STRUCTURED OUTPUT EXTRACTORS (safe downstream interfaces)
# =============================================================================

@dataclass
class CitationCandidate:
    """
    Citation candidate extracted from retrieval.
    
    GC-14: This is a safe downstream output.
    Contains only structured data for citation purposes.
    """
    source_id: str
    location: RetrievalLocation
    snippet_hash: str
    snippet_text: str  # For display/verification only


@dataclass
class FactualCandidate:
    """
    Factual candidate extracted from retrieval.
    
    GC-14: This is a safe downstream output.
    Contains only structured data for factual claims.
    """
    source_id: str
    location: RetrievalLocation
    snippet_hash: str
    factual_text: str  # For display/verification only


def extract_citation_candidates(
    results: list[RetrievalResult]
) -> list[CitationCandidate]:
    """
    Extract citation candidates from retrieval results.
    
    GC-14: Safe downstream interface.
    - Accepts only typed RetrievalResult objects.
    - Returns structured CitationCandidate objects.
    - Cannot trigger tool calls or policy changes.
    """
    candidates = []
    for result in results:
        candidates.append(CitationCandidate(
            source_id=result.source_id,
            location=result.location,
            snippet_hash=result.snippet_hash,
            snippet_text=result.get_safe_content_for_citation(),
        ))
    return candidates


def extract_factual_candidates(
    results: list[RetrievalResult]
) -> list[FactualCandidate]:
    """
    Extract factual candidates from retrieval results.
    
    GC-14: Safe downstream interface.
    - Accepts only typed RetrievalResult objects.
    - Returns structured FactualCandidate objects.
    - Cannot trigger tool calls or policy changes.
    """
    candidates = []
    for result in results:
        candidates.append(FactualCandidate(
            source_id=result.source_id,
            location=result.location,
            snippet_hash=result.snippet_hash,
            factual_text=result.get_safe_content_for_display(),
        ))
    return candidates
