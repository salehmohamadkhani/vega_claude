"""Finite State Machine — formal state machine for protocol transitions.

Provides a general-purpose FSM with:
- Named states and transitions
- Guard conditions on transitions
- Side-effect actions when entering/exiting states
- Event-driven transitions
- Transition history logging
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class Transition:
    """A valid transition between two states.

    Attributes:
        source: The state to transition from.
        target: The state to transition to.
        event: The event that triggers this transition.
        guard: Optional callable that must return True for the
            transition to be allowed.  Receives (context_dict).
        action: Optional callable to execute during the transition.
            Receives (context_dict).
        description: Human-readable description.
        priority: Higher priority transitions are checked first when
            multiple transitions share the same source and event.
    """

    source: str
    target: str
    event: str
    guard: Optional[Callable[[Dict[str, Any]], bool]] = None
    action: Optional[Callable[[Dict[str, Any]], None]] = None
    description: str = ""
    priority: int = 0

    def is_allowed(self, context: Dict[str, Any]) -> bool:
        """Check if this transition's guard allows it."""
        if self.guard is None:
            return True
        try:
            return self.guard(context)
        except Exception:
            return False


@dataclass
class TransitionRecord:
    """Log entry for a state transition."""

    from_state: str
    to_state: str
    event: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context_snapshot: Optional[Dict[str, Any]] = None


class FSMError(Exception):
    """Raised when a state machine operation is invalid."""


class FiniteStateMachine:
    """A general-purpose finite state machine.

    Supports:
    - Named states with on_enter/on_exit callbacks
    - Guard conditions on transitions
    - Action callbacks during transitions
    - Event-driven state changes
    - Full transition history
    - Introspection (available transitions, reachable states, etc.)

    Example::

        fsm = FiniteStateMachine("plan")
        fsm.add_state("plan", on_enter=lambda c: print("Planning..."))
        fsm.add_state("implement")
        fsm.add_state("resolve")
        fsm.add_state("approve")

        fsm.add_transition("plan", "implement", "plan_accepted")
        fsm.add_transition("plan", "resolve", "plan_rejected",
                          guard=lambda c: c.get("auto_escalate", False))
        fsm.add_transition("implement", "resolve", "review_rejected")
        fsm.add_transition("resolve", "approve", "decision_made")
        fsm.add_transition("approve", "plan", "rejected")  # New round

        fsm.trigger("plan_accepted", context={"task": "..."})
        print(fsm.current_state)  # "implement"
    """

    def __init__(self, initial_state: str) -> None:
        self._current = initial_state
        self._states: Dict[str, Dict[str, Any]] = {}
        self._transitions: List[Transition] = []
        self._history: List[TransitionRecord] = []
        self._on_any_transition: Optional[Callable] = None

        # Register initial state
        self.add_state(initial_state)

    # ------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------

    def add_state(
        self,
        name: str,
        *,
        on_enter: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_exit: Optional[Callable[[Dict[str, Any]], None]] = None,
        is_terminal: bool = False,
    ) -> None:
        """Register a state.

        Args:
            name: Unique state name.
            on_enter: Called when entering this state.
            on_exit: Called when leaving this state.
            is_terminal: If True, no transitions out are allowed.
        """
        self._states[name] = {
            "on_enter": on_enter,
            "on_exit": on_exit,
            "is_terminal": is_terminal,
        }

    @property
    def current_state(self) -> str:
        return self._current

    @property
    def states(self) -> Set[str]:
        return set(self._states.keys())

    @property
    def history(self) -> List[TransitionRecord]:
        return list(self._history)

    @property
    def transition_count(self) -> int:
        return len(self._history)

    # ------------------------------------------------------------------
    # Transition Management
    # ------------------------------------------------------------------

    def add_transition(
        self,
        source: str,
        target: str,
        event: str,
        *,
        guard: Optional[Callable[[Dict[str, Any]], bool]] = None,
        action: Optional[Callable[[Dict[str, Any]], None]] = None,
        description: str = "",
        priority: int = 0,
    ) -> Transition:
        """Register a valid transition.

        Returns:
            The created Transition object.
        """
        # Auto-register states
        if source not in self._states:
            self.add_state(source)
        if target not in self._states:
            self.add_state(target)

        t = Transition(
            source=source,
            target=target,
            event=event,
            guard=guard,
            action=action,
            description=description,
            priority=priority,
        )
        self._transitions.append(t)
        return t

    def on_any_transition(self, callback: Callable) -> None:
        """Register a callback fired on every state transition."""
        self._on_any_transition = callback

    # ------------------------------------------------------------------
    # Event Processing
    # ------------------------------------------------------------------

    def trigger(
        self,
        event: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Trigger an event, potentially causing a state transition.

        Args:
            event: The event name.
            context: Context dict passed to guards and actions.

        Returns:
            The new state after transition.

        Raises:
            FSMError: If the current state is terminal, or no valid
                transition exists for this event from the current state.
        """
        ctx = context or {}

        # Check terminal
        state_info = self._states.get(self._current, {})
        if state_info.get("is_terminal"):
            raise FSMError(f"State '{self._current}' is terminal — no transitions allowed.")

        # Find matching transitions (same source + event)
        candidates = [t for t in self._transitions if t.source == self._current and t.event == event]

        if not candidates:
            raise FSMError(
                f"No transition for event '{event}' from state '{self._current}'. "
                f"Available events: {self.available_events()}"
            )

        # Sort by priority (descending) and check guards
        candidates.sort(key=lambda t: t.priority, reverse=True)

        for t in candidates:
            if t.is_allowed(ctx):
                return self._execute_transition(t, ctx)

        raise FSMError(
            f"Event '{event}' from state '{self._current}' exists but "
            f"guard conditions blocked all {len(candidates)} transition(s)."
        )

    def can_trigger(
        self,
        event: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if an event can be triggered from the current state."""
        ctx = context or {}
        state_info = self._states.get(self._current, {})
        if state_info.get("is_terminal"):
            return False

        candidates = [t for t in self._transitions if t.source == self._current and t.event == event]
        return any(t.is_allowed(ctx) for t in candidates)

    def try_trigger(
        self,
        event: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Like trigger() but returns None instead of raising."""
        try:
            return self.trigger(event, context=context)
        except FSMError:
            return None

    def _execute_transition(
        self,
        transition: Transition,
        context: Dict[str, Any],
    ) -> str:
        old_state = self._current

        # on_exit callback
        exit_cb = self._states.get(old_state, {}).get("on_exit")
        if exit_cb:
            exit_cb(context)

        # Transition action
        if transition.action:
            transition.action(context)

        # Change state
        self._current = transition.target

        # on_enter callback
        enter_cb = self._states.get(self._current, {}).get("on_enter")
        if enter_cb:
            enter_cb(context)

        # Record history
        self._history.append(
            TransitionRecord(
                from_state=old_state,
                to_state=self._current,
                event=transition.event,
            )
        )

        # Global callback
        if self._on_any_transition:
            self._on_any_transition(old_state, self._current, transition.event, context)

        return self._current

    # ------------------------------------------------------------------
    # Force (for backward compat with set_phase)
    # ------------------------------------------------------------------

    def force_state(self, state: str) -> None:
        """Force the FSM into a specific state, bypassing guards.

        Use sparingly — this is for backward compatibility.
        """
        if state not in self._states:
            self.add_state(state)
        self._history.append(
            TransitionRecord(
                from_state=self._current,
                to_state=state,
                event="_force",
            )
        )
        self._current = state

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def available_events(self) -> List[str]:
        """List events available from the current state."""
        return list({t.event for t in self._transitions if t.source == self._current})

    def available_transitions(self, *, context: Optional[Dict[str, Any]] = None) -> List[Transition]:
        """List transitions available from the current state.

        If context is provided, also checks guard conditions.
        """
        ctx = context or {}
        return [t for t in self._transitions if t.source == self._current and (context is None or t.is_allowed(ctx))]

    def reachable_states(self) -> Set[str]:
        """BFS to find all states reachable from current state."""
        visited: Set[str] = set()
        queue = [self._current]
        while queue:
            state = queue.pop(0)
            if state in visited:
                continue
            visited.add(state)
            for t in self._transitions:
                if t.source == state and t.target not in visited:
                    queue.append(t.target)
        return visited

    def is_in_state(self, state: str) -> bool:
        return self._current == state

    def get_transition_map(self) -> Dict[str, List[Dict[str, str]]]:
        """Get a map of state → list of possible transitions."""
        result: Dict[str, List[Dict[str, str]]] = {}
        for t in self._transitions:
            result.setdefault(t.source, []).append(
                {
                    "event": t.event,
                    "target": t.target,
                    "description": t.description,
                    "has_guard": t.guard is not None,
                }
            )
        return result


def build_protocol_fsm() -> FiniteStateMachine:
    """Build the standard Agent Table protocol FSM.

    States: plan, implement, resolve, approve, finalized
    Transitions follow the deliberation protocol with guards
    for escalation and strategy-dependent routing.

    Returns:
        Configured FiniteStateMachine ready for use.
    """
    fsm = FiniteStateMachine("plan")

    # States
    fsm.add_state("plan")
    fsm.add_state("implement")
    fsm.add_state("resolve")
    fsm.add_state("approve")
    fsm.add_state("finalized", is_terminal=True)

    # --- Plan Phase Transitions ---
    fsm.add_transition(
        "plan",
        "implement",
        "plan_approved",
        description="Critic approved the plan → move to implementation",
    )
    fsm.add_transition(
        "plan",
        "resolve",
        "plan_rejected",
        guard=lambda c: c.get("auto_escalate", False),
        description="Critic rejected with auto-escalate → Arbiter resolves",
        priority=10,
    )
    fsm.add_transition(
        "plan",
        "plan",
        "plan_rejected",
        guard=lambda c: not c.get("auto_escalate", False),
        description="Critic rejected without auto-escalate → Doer revises",
        priority=0,
    )

    # --- Implement Phase Transitions ---
    fsm.add_transition(
        "implement",
        "approve",
        "review_approved",
        description="Critic approved implementation → Arbiter gives final approval",
    )
    fsm.add_transition(
        "implement",
        "resolve",
        "review_rejected",
        guard=lambda c: c.get("auto_escalate", False),
        description="Critic rejected review with auto-escalate → Arbiter resolves",
        priority=10,
    )
    fsm.add_transition(
        "implement",
        "implement",
        "review_rejected",
        guard=lambda c: not c.get("auto_escalate", False),
        description="Critic rejected review → Doer revises implementation",
        priority=0,
    )
    fsm.add_transition(
        "implement",
        "resolve",
        "escalated",
        description="Manual escalation to Arbiter",
        priority=100,
    )

    # --- Resolve Phase Transitions ---
    fsm.add_transition(
        "resolve",
        "approve",
        "decision_made",
        description="Arbiter made a decision → move to approval",
    )
    fsm.add_transition(
        "resolve",
        "plan",
        "decision_restart",
        description="Arbiter decides to restart from planning",
    )

    # --- Approve Phase Transitions ---
    fsm.add_transition(
        "approve",
        "finalized",
        "approved",
        description="Arbiter approved → task complete",
    )
    fsm.add_transition(
        "approve",
        "plan",
        "rejected",
        description="Arbiter rejected → start new round from plan",
    )

    # --- Direct Escalation from any phase ---
    for source in ("plan", "implement"):
        fsm.add_transition(
            source,
            "resolve",
            "force_escalate",
            description=f"Force escalation from {source} to Arbiter",
            priority=50,
        )

    return fsm
