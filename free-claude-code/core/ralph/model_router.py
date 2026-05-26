"""Model role routing — maps abstract Ralph ModelRole values to FCC-resolved models.

The ModelRoleRouter is the bridge between Ralph's abstract role system and
FCC's concrete provider/model configuration. It uses FCC Settings methods
(resolve_model, resolve_thinking, parse_provider_type, parse_model_name)
without importing providers or making network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .roles import AGENT_TO_MODEL_ROLE, AgentRole, ModelRole


class ModelRoleRoutingError(ValueError):
    """Raised when a model role cannot be resolved."""


# ---------------------------------------------------------------------------
# Settings protocol — defines the FCC Settings surface we consume
# ---------------------------------------------------------------------------


class SettingsLike(Protocol):
    """Minimal protocol for the FCC Settings methods ModelRoleRouter needs.

    Tests should pass a fake implementing this protocol instead of the
    real Pydantic Settings class to avoid env-file side effects.
    """

    def resolve_model(self, claude_model_name: str) -> str: ...
    def resolve_thinking(self, claude_model_name: str) -> bool: ...

    @staticmethod
    def parse_provider_type(model_string: str) -> str: ...

    @staticmethod
    def parse_model_name(model_string: str) -> str: ...


# ---------------------------------------------------------------------------
# Default routing policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelRoleRoutingPolicy:
    """Default Claude-tier mapping for each ModelRole.

    Each value is a Claude-compatible tier hint (e.g. "opus", "sonnet", "haiku")
    that FCC's ``Settings.resolve_model()`` uses to find the configured model.
    """

    planner_model_name: str = "haiku"
    doer_model_name: str = "sonnet"
    critic_model_name: str = "opus"
    debugger_model_name: str = "sonnet"
    summarizer_model_name: str = "haiku"

    def tier_for_role(self, role: ModelRole) -> str:
        """Return the Claude-tier hint for a model role."""
        mapping: dict[ModelRole, str] = {
            ModelRole.PLANNER: self.planner_model_name,
            ModelRole.DOER: self.doer_model_name,
            ModelRole.CRITIC: self.critic_model_name,
            ModelRole.DEBUGGER: self.debugger_model_name,
            ModelRole.SUMMARIZER: self.summarizer_model_name,
        }
        try:
            return mapping[role]
        except KeyError:
            msg = f"No tier mapping defined for ModelRole.{role.name}"
            raise ModelRoleRoutingError(msg) from None


# ---------------------------------------------------------------------------
# Resolution result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelRoleResolution:
    """Resolved model information for a single ModelRole.

    This mirrors FCC's ``ResolvedModel`` but lives in the Ralph Runtime
    layer and is derived from ``ModelRole`` rather than an incoming
    Claude model name string.
    """

    model_role: ModelRole
    claude_model_name: str
    provider_model_ref: str
    provider_id: str
    provider_model: str
    thinking_enabled: bool
    source: str = "role_policy"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ModelRoleRouter:
    """Resolve abstract Ralph ``ModelRole`` values through FCC model configuration.

    Usage::

        router = ModelRoleRouter(settings)
        resolution = router.resolve(ModelRole.DOER)
        all_resolutions = router.resolve_all()
    """

    def __init__(
        self,
        settings: SettingsLike,
        policy: ModelRoleRoutingPolicy | None = None,
    ) -> None:
        self._settings = settings
        self._policy = policy or ModelRoleRoutingPolicy()

    def resolve(self, model_role: ModelRole) -> ModelRoleResolution:
        """Resolve a single ``ModelRole`` through FCC settings."""
        tier = self._policy.tier_for_role(model_role)
        return self._resolve_tier(model_role, tier)

    def resolve_agent_role(self, agent_role: AgentRole) -> ModelRoleResolution:
        """Resolve an ``AgentRole`` by first mapping it to ``ModelRole``.

        Uses the ``AGENT_TO_MODEL_ROLE`` mapping from ``roles.py``.
        """
        try:
            model_role = AGENT_TO_MODEL_ROLE[agent_role]
        except KeyError:
            role_name = (
                agent_role.name if hasattr(agent_role, "name") else str(agent_role)
            )
            msg = f"No ModelRole mapping for AgentRole.{role_name}"
            raise ModelRoleRoutingError(msg) from None
        return self.resolve(model_role)

    def resolve_all(self) -> dict[ModelRole, ModelRoleResolution]:
        """Resolve every ``ModelRole`` and return a dict keyed by role."""
        return {role: self.resolve(role) for role in ModelRole}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_tier(self, model_role: ModelRole, tier: str) -> ModelRoleResolution:
        """Resolve a Claude tier hint through FCC settings."""
        provider_model_ref = self._settings.resolve_model(tier)
        provider_id = self._settings.parse_provider_type(provider_model_ref)
        provider_model = self._settings.parse_model_name(provider_model_ref)
        thinking_enabled = self._settings.resolve_thinking(tier)
        return ModelRoleResolution(
            model_role=model_role,
            claude_model_name=tier,
            provider_model_ref=provider_model_ref,
            provider_id=provider_id,
            provider_model=provider_model,
            thinking_enabled=thinking_enabled,
            source="role_policy",
        )
