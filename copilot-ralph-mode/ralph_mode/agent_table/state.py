"""Table state persistence and round management."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Phase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TABLE_DIR = "table"
ROUNDS_DIR = "rounds"
TABLE_STATE_FILE = "table-state.json"


# ---------------------------------------------------------------------------
# TableState
# ---------------------------------------------------------------------------


class TableState:
    """Manages the persistent state of an Agent Table session.

    State is stored as JSON in `.ralph-mode/table/table-state.json`.
    Round directories are created under `.ralph-mode/table/rounds/`.
    """

    def __init__(self, ralph_dir: Path) -> None:
        self.ralph_dir = Path(ralph_dir)
        self.table_dir = self.ralph_dir / TABLE_DIR
        self.rounds_dir = self.table_dir / ROUNDS_DIR
        self.state_file = self.table_dir / TABLE_STATE_FILE

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        task: str,
        *,
        max_rounds: int = 10,
        require_unanimous: bool = False,
        auto_escalate: bool = True,
        strategy: str = "default",
    ) -> Dict[str, Any]:
        """Create a new table state."""
        self.table_dir.mkdir(parents=True, exist_ok=True)
        self.rounds_dir.mkdir(parents=True, exist_ok=True)

        state: Dict[str, Any] = {
            "active": True,
            "task": task,
            "current_round": 0,
            "current_phase": Phase.PLAN.value,
            "max_rounds": max_rounds,
            "require_unanimous": require_unanimous,
            "auto_escalate": auto_escalate,
            "strategy": strategy,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "outcome": None,
            "total_messages": 0,
            "escalation_count": 0,
            "deadlock_count": 0,
            "rounds_summary": [],
            "agent_stats": {},
            "consensus_history": [],
        }
        self.save(state)
        return state

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        """Check if state file exists."""
        return self.state_file.exists()

    # Aliases for backward compatibility with table.py
    def is_active(self) -> bool:
        """Check if an Agent Table session is active."""
        return self.state_file.exists()

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current table state."""
        return self.load()

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save state (alias for save)."""
        self.save(state)

    def _round_dir(self, round_number: int) -> Path:
        """Get round directory (alias for round_dir)."""
        return self.round_dir(round_number)

    def load(self) -> Optional[Dict[str, Any]]:
        """Load state from disk."""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save(self, state: Dict[str, Any]) -> None:
        """Save state to disk."""
        self.table_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def load_or_raise(self) -> Dict[str, Any]:
        """Load state or raise ValueError if not found."""
        state = self.load()
        if state is None:
            raise ValueError("Agent Table is not active. Call initialize() first.")
        return state

    def load_active_or_raise(self) -> Dict[str, Any]:
        """Load state and ensure it's active."""
        state = self.load_or_raise()
        if not state.get("active"):
            raise ValueError("Agent Table is not active.")
        return state

    # ------------------------------------------------------------------
    # Round Management
    # ------------------------------------------------------------------

    def new_round(self) -> Dict[str, Any]:
        """Start a new deliberation round.

        Returns:
            Updated state.

        Raises:
            ValueError: If not active or max rounds reached.
        """
        state = self.load_active_or_raise()

        if state["current_round"] >= state["max_rounds"]:
            state["outcome"] = "max_rounds_reached"
            state["active"] = False
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
            self.save(state)
            raise ValueError(f"Maximum rounds ({state['max_rounds']}) reached. " "Table session ended.")

        state["current_round"] += 1
        state["current_phase"] = Phase.PLAN.value
        self.save(state)

        # Create round directory
        round_dir = self.round_dir(state["current_round"])
        round_dir.mkdir(parents=True, exist_ok=True)

        return state

    def round_dir(self, round_number: int) -> Path:
        """Get the directory for a specific round."""
        return self.rounds_dir / f"round-{round_number:03d}"

    def current_round_dir(self) -> Path:
        """Get the directory for the current round."""
        state = self.load()
        rn = state["current_round"] if state else 1
        return self.round_dir(rn)

    # ------------------------------------------------------------------
    # State Mutations
    # ------------------------------------------------------------------

    def increment_messages(self) -> int:
        """Increment message counter, return new count."""
        state = self.load_active_or_raise()
        state["total_messages"] = state.get("total_messages", 0) + 1
        self.save(state)
        return state["total_messages"]

    def increment_escalations(self) -> int:
        """Increment escalation counter, return new count."""
        state = self.load_active_or_raise()
        state["escalation_count"] = state.get("escalation_count", 0) + 1
        self.save(state)
        return state["escalation_count"]

    def increment_deadlocks(self) -> int:
        """Increment deadlock counter, return new count."""
        state = self.load_active_or_raise()
        state["deadlock_count"] = state.get("deadlock_count", 0) + 1
        self.save(state)
        return state["deadlock_count"]

    def set_phase(self, phase: str) -> Dict[str, Any]:
        """Set the current phase."""
        if phase not in [p.value for p in Phase]:
            raise ValueError(f"Invalid phase: {phase}. " f"Must be one of {[p.value for p in Phase]}")
        state = self.load_active_or_raise()
        state["current_phase"] = phase
        self.save(state)
        return state

    def add_round_summary(self, outcome: str, reason: str = "") -> Dict[str, Any]:
        """Record a round's outcome."""
        state = self.load_active_or_raise()
        summary: Dict[str, Any] = {
            "round": state["current_round"],
            "outcome": outcome,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if reason:
            summary["reason"] = reason
        state.setdefault("rounds_summary", []).append(summary)
        self.save(state)
        return state

    def update_agent_stats(self, agent: str, key: str, increment: int = 1) -> None:
        """Increment a specific stat for an agent."""
        state = self.load_active_or_raise()
        stats = state.setdefault("agent_stats", {})
        agent_stats = stats.setdefault(agent, {})
        agent_stats[key] = agent_stats.get(key, 0) + increment
        self.save(state)

    def finalize(self, outcome: str = "approved") -> Dict[str, Any]:
        """Mark session as complete."""
        state = self.load_or_raise()
        state["active"] = False
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        state["outcome"] = outcome
        self.save(state)
        return state

    def reset(self) -> None:
        """Remove all table data."""
        import shutil

        if self.table_dir.exists():
            shutil.rmtree(self.table_dir)
