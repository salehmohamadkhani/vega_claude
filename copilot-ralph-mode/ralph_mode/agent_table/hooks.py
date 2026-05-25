"""Hook manager — event-driven callbacks for Agent Table lifecycle events."""

from typing import Any, Callable, Dict, List, Optional

from .models import AgentMessage

# Type alias for hook callbacks
HookCallback = Callable[..., None]

# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

# Phase events
EVENT_PHASE_CHANGE = "phase_change"
EVENT_ROUND_START = "round_start"
EVENT_ROUND_END = "round_end"

# Message events
EVENT_MESSAGE_SENT = "message_sent"
EVENT_PLAN_SUBMITTED = "plan_submitted"
EVENT_CRITIQUE_SUBMITTED = "critique_submitted"
EVENT_IMPLEMENTATION_SUBMITTED = "implementation_submitted"
EVENT_REVIEW_SUBMITTED = "review_submitted"

# Escalation events
EVENT_ESCALATION = "escalation"
EVENT_DECISION = "decision"

# Approval events
EVENT_APPROVAL = "approval"
EVENT_REJECTION = "rejection"

# Session events
EVENT_TABLE_INITIALIZED = "table_initialized"
EVENT_TABLE_FINALIZED = "table_finalized"
EVENT_TABLE_RESET = "table_reset"

# Consensus events
EVENT_VOTE_CAST = "vote_cast"
EVENT_CONSENSUS_REACHED = "consensus_reached"

# Deadlock events
EVENT_DEADLOCK_DETECTED = "deadlock_detected"

ALL_EVENTS = [
    EVENT_PHASE_CHANGE,
    EVENT_ROUND_START,
    EVENT_ROUND_END,
    EVENT_MESSAGE_SENT,
    EVENT_PLAN_SUBMITTED,
    EVENT_CRITIQUE_SUBMITTED,
    EVENT_IMPLEMENTATION_SUBMITTED,
    EVENT_REVIEW_SUBMITTED,
    EVENT_ESCALATION,
    EVENT_DECISION,
    EVENT_APPROVAL,
    EVENT_REJECTION,
    EVENT_TABLE_INITIALIZED,
    EVENT_TABLE_FINALIZED,
    EVENT_TABLE_RESET,
    EVENT_VOTE_CAST,
    EVENT_CONSENSUS_REACHED,
    EVENT_DEADLOCK_DETECTED,
]


# ---------------------------------------------------------------------------
# HookManager
# ---------------------------------------------------------------------------


class HookManager:
    """Registry and dispatcher for event hooks.

    Example::

        hooks = HookManager()

        @hooks.on("plan_submitted")
        def log_plan(message):
            print(f"Plan received: {message.content[:80]}")

        # Later, when a plan is submitted:
        hooks.emit("plan_submitted", message=msg)
    """

    def __init__(self) -> None:
        self._hooks: Dict[str, List[HookCallback]] = {}
        self._global_hooks: List[HookCallback] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def on(self, event: str) -> Callable:
        """Decorator to register a hook for an event.

        Usage::

            @hooks.on("escalation")
            def handle_escalation(**kwargs):
                ...
        """

        def decorator(fn: HookCallback) -> HookCallback:
            self.register(event, fn)
            return fn

        return decorator

    def register(self, event: str, callback: HookCallback) -> None:
        """Register a callback for a specific event."""
        self._hooks.setdefault(event, []).append(callback)

    def register_global(self, callback: HookCallback) -> None:
        """Register a callback that fires on ALL events."""
        self._global_hooks.append(callback)

    def unregister(self, event: str, callback: HookCallback) -> bool:
        """Remove a specific callback. Returns True if found and removed."""
        hooks = self._hooks.get(event, [])
        if callback in hooks:
            hooks.remove(callback)
            return True
        return False

    def unregister_all(self, event: Optional[str] = None) -> None:
        """Clear hooks for a specific event, or all hooks if None."""
        if event is None:
            self._hooks.clear()
            self._global_hooks.clear()
        else:
            self._hooks.pop(event, None)

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, event: str, **kwargs: Any) -> List[Any]:
        """Fire all callbacks registered for *event*.

        Callbacks receive keyword arguments. Exceptions are caught
        and collected — a failing hook does not block others.

        Returns:
            List of results (or exception objects for failed hooks).
        """
        results: List[Any] = []

        # Event-specific hooks
        for cb in self._hooks.get(event, []):
            try:
                results.append(cb(**kwargs))
            except Exception as exc:
                results.append(exc)

        # Global hooks
        for cb in self._global_hooks:
            try:
                results.append(cb(event=event, **kwargs))
            except Exception as exc:
                results.append(exc)

        return results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_events(self) -> List[str]:
        """List all events that have at least one registered hook."""
        return list(self._hooks.keys())

    def count_hooks(self, event: Optional[str] = None) -> int:
        """Count hooks for a specific event, or total if None."""
        if event is not None:
            return len(self._hooks.get(event, []))
        return sum(len(h) for h in self._hooks.values()) + len(self._global_hooks)

    def has_hooks(self, event: str) -> bool:
        """Return True if there are hooks for *event*."""
        return bool(self._hooks.get(event)) or bool(self._global_hooks)
