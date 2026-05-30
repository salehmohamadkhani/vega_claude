"""Agent Council V2 — Runtime Gate Configuration.

Small deterministic config model for controlling Agent Council evidence
gate enforcement at runtime.

No env reads. No LLM/API calls. No shell commands.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeGateConfig:
    """Configuration for Agent Council evidence gate enforcement at runtime.

    Default values preserve old behavior: gates are disabled and
    enforcement is non-strict.
    """

    use_agent_council_gates: bool = False
    strict_agent_council_gates: bool = False
    project_type: str | None = None
    project_goal: str | None = None

    @property
    def is_enabled(self) -> bool:
        """True if any council gate feature is active."""
        return self.use_agent_council_gates

    @property
    def is_strict(self) -> bool:
        """True if strict mode AND gates are enabled."""
        return self.use_agent_council_gates and self.strict_agent_council_gates


def runtime_gate_config_to_dict(config: RuntimeGateConfig) -> dict[str, object]:
    """Convert a RuntimeGateConfig to a JSON-serializable dict."""
    return {
        "use_agent_council_gates": config.use_agent_council_gates,
        "strict_agent_council_gates": config.strict_agent_council_gates,
        "project_type": config.project_type or "",
        "project_goal": config.project_goal or "",
        "is_enabled": config.is_enabled,
        "is_strict": config.is_strict,
    }


def runtime_gate_config_from_options(
    use_agent_council_gates: bool = False,
    strict_agent_council_gates: bool = False,
    project_type: str | None = None,
    project_goal: str | None = None,
) -> RuntimeGateConfig:
    """Build a RuntimeGateConfig from individual options.

    Enforces: --strict-agent-council-gates implies --use-agent-council-gates.
    """
    effective_use = use_agent_council_gates or strict_agent_council_gates
    return RuntimeGateConfig(
        use_agent_council_gates=effective_use,
        strict_agent_council_gates=strict_agent_council_gates and effective_use,
        project_type=project_type,
        project_goal=project_goal,
    )


# Type alias for convenience
GateConfigDict = dict[str, object]
