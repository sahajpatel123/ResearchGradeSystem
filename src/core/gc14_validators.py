"""
GC-14 Validators: RAG Instruction Firewall Validation.

Implements architectural enforcement validators for GC-14.
Ensures retrieved text cannot reach authority channels.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.core.rag_firewall import (
    RAG_INSTRUCTION_FIREWALL_ENABLED,
    FirewallEventCategory,
    InstructionLikeFlag,
    RagFirewallEvent,
    RetrievalResult,
    get_firewall_enabled,
)


@dataclass
class GC14ValidationError:
    """GC-14 validation error with category and message."""
    category: str
    message: str
    field: Optional[str] = None
    is_warning: bool = False


# =============================================================================
# ARCHITECTURAL ENFORCEMENT VALIDATORS
# =============================================================================

def validate_firewall_enabled() -> list[GC14ValidationError]:
    """
    Validate that RAG instruction firewall is enabled.
    
    GC-14: Firewall must be enabled by default.
    If disabled, emit RAG_FIREWALL_POLICY_DISABLED error.
    """
    errors = []
    
    if not get_firewall_enabled():
        errors.append(GC14ValidationError(
            category="RAG_FIREWALL_POLICY_DISABLED",
            message="RAG instruction firewall is disabled. "
                    "Retrieved text may reach authority channels. "
                    "(GC-14: RAG_FIREWALL_POLICY_DISABLED)",
            field="rag_instruction_firewall_enabled",
            is_warning=False,  # Hard error in production
        ))
    
    return errors


def validate_retrieval_result_type(obj: Any) -> list[GC14ValidationError]:
    """
    Validate that retrieval output is properly typed.
    
    GC-14 PRIMARY ENFORCEMENT:
    - Retrieval output must be RetrievalResult, not raw string.
    - Raw strings cannot reach downstream interfaces.
    """
    errors = []
    
    if isinstance(obj, str):
        errors.append(GC14ValidationError(
            category="RAW_STRING_IN_RETRIEVAL_PIPELINE",
            message="Raw string found in retrieval pipeline. "
                    "Must use RetrievalResult type. "
                    "(GC-14: architectural separation)",
            field="retrieval_output",
        ))
    elif not isinstance(obj, RetrievalResult):
        errors.append(GC14ValidationError(
            category="INVALID_RETRIEVAL_TYPE",
            message=f"Invalid retrieval output type: {type(obj).__name__}. "
                    "Must be RetrievalResult. "
                    "(GC-14: architectural separation)",
            field="retrieval_output",
        ))
    
    return errors


def validate_no_authority_channel_access(
    retrieval_result: RetrievalResult,
    tool_router_invoked: bool = False,
    status_changed: bool = False,
    policy_changed: bool = False,
) -> list[GC14ValidationError]:
    """
    Validate that retrieval result did not reach authority channels.
    
    GC-14: Retrieved text cannot change:
    - tool calls
    - status FINAL/INCOMPLETE
    - policy/config
    """
    errors = []
    
    if tool_router_invoked:
        errors.append(GC14ValidationError(
            category="RETRIEVAL_TRIGGERED_TOOL_CALL",
            message="Retrieved text triggered tool invocation. "
                    "This violates GC-14 architectural separation. "
                    "(GC-14: RETRIEVAL_TRIGGERED_TOOL_CALL)",
            field="tool_router",
        ))
    
    if status_changed:
        errors.append(GC14ValidationError(
            category="RETRIEVAL_CHANGED_STATUS",
            message="Retrieved text changed report status. "
                    "This violates GC-14 architectural separation. "
                    "(GC-14: RETRIEVAL_CHANGED_STATUS)",
            field="status",
        ))
    
    if policy_changed:
        errors.append(GC14ValidationError(
            category="RETRIEVAL_CHANGED_POLICY",
            message="Retrieved text changed policy/config. "
                    "This violates GC-14 architectural separation. "
                    "(GC-14: RETRIEVAL_CHANGED_POLICY)",
            field="policy",
        ))
    
    return errors


def validate_firewall_events_logged(
    retrieval_result: RetrievalResult,
    events: list[RagFirewallEvent],
) -> list[GC14ValidationError]:
    """
    Validate that firewall events were logged for detected flags.
    
    GC-14: Instruction-like content must be logged.
    """
    errors = []
    
    if retrieval_result.has_instruction_like_content():
        # Check that events were logged for each flag
        logged_categories = {e.flag_type for e in events}
        
        for flag in retrieval_result.instruction_like_flags:
            expected_category = _get_expected_event_category(flag)
            if expected_category not in logged_categories:
                errors.append(GC14ValidationError(
                    category="FIREWALL_EVENT_NOT_LOGGED",
                    message=f"Instruction-like content ({flag.value}) detected but "
                            f"firewall event not logged. "
                            "(GC-14: FIREWALL_EVENT_NOT_LOGGED)",
                    field="firewall_events",
                    is_warning=True,
                ))
    
    return errors


def _get_expected_event_category(flag: InstructionLikeFlag) -> str:
    """Get expected event category for a flag."""
    mapping = {
        InstructionLikeFlag.PROMPT_INJECTION_PATTERN: "RETRIEVED_INSTRUCTION_IGNORED",
        InstructionLikeFlag.POLICY_OVERRIDE_PATTERN: "RETRIEVED_POLICY_OVERRIDE_IGNORED",
        InstructionLikeFlag.TOOL_TRIGGER_PATTERN: "RETRIEVED_TOOL_TRIGGER_IGNORED",
        InstructionLikeFlag.STATUS_OVERRIDE_PATTERN: "RETRIEVED_STATUS_OVERRIDE_IGNORED",
    }
    return mapping.get(flag, flag.value)


# =============================================================================
# MOCK TOOL ROUTER (for testing architectural separation)
# =============================================================================

class MockToolRouter:
    """
    Mock tool router for testing GC-14 architectural separation.
    
    Records all invocation attempts to prove retrieval cannot trigger tools.
    """
    
    def __init__(self):
        self.invocations: list[dict] = []
        self._invoked = False

    def invoke(self, tool_name: str, args: dict) -> Any:
        """
        Record a tool invocation attempt.
        
        In production, this would execute the tool.
        For testing, we just record the attempt.
        """
        self._invoked = True
        self.invocations.append({
            "tool_name": tool_name,
            "args": args,
        })
        return {"status": "recorded"}

    def was_invoked(self) -> bool:
        """Check if any tool was invoked."""
        return self._invoked

    def reset(self) -> None:
        """Reset invocation state."""
        self.invocations = []
        self._invoked = False


# =============================================================================
# SAFE INTERFACE VALIDATORS
# =============================================================================

def validate_interface_accepts_only_typed_results(
    interface_fn: Callable,
    raw_string: str,
) -> list[GC14ValidationError]:
    """
    Validate that an interface function rejects raw strings.
    
    GC-14: Downstream interfaces must accept only RetrievalResult objects.
    """
    errors = []
    
    try:
        # Attempt to call interface with raw string
        interface_fn([raw_string])
        # If no error, the interface accepted raw string (violation)
        errors.append(GC14ValidationError(
            category="INTERFACE_ACCEPTS_RAW_STRING",
            message="Interface accepted raw string instead of RetrievalResult. "
                    "(GC-14: architectural separation)",
            field="interface",
        ))
    except (TypeError, AttributeError):
        # Expected - interface should reject raw strings
        pass
    
    return errors
