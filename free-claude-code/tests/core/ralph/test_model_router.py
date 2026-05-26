"""Tests for core.ralph.model_router."""

from __future__ import annotations

import pytest

from core.ralph.model_router import (
    ModelRoleResolution,
    ModelRoleRouter,
    ModelRoleRoutingError,
    ModelRoleRoutingPolicy,
)
from core.ralph.roles import AGENT_TO_MODEL_ROLE, AgentRole, ModelRole

# ---------------------------------------------------------------------------
# Fake settings — implements SettingsLike protocol without env side effects
# ---------------------------------------------------------------------------


class FakeSettings:
    """Minimal settings stub that mimics the FCC Settings surface we need."""

    def __init__(self) -> None:
        self._mock: dict[str, str] = {
            "opus": "openrouter/anthropic/claude-opus-4",
            "sonnet": "openrouter/anthropic/claude-sonnet-4",
            "haiku": "openrouter/anthropic/claude-haiku-4",
        }

    def resolve_model(self, claude_model_name: str) -> str:
        name = claude_model_name.lower()
        if "opus" in name:
            return self._mock["opus"]
        if "sonnet" in name:
            return self._mock["sonnet"]
        if "haiku" in name:
            return self._mock["haiku"]
        # fallback — use sonnet
        return self._mock["sonnet"]

    def resolve_thinking(self, claude_model_name: str) -> bool:
        return "opus" in claude_model_name.lower()

    @staticmethod
    def parse_provider_type(model_string: str) -> str:
        return model_string.split("/", 1)[0]

    @staticmethod
    def parse_model_name(model_string: str) -> str:
        return model_string.split("/", 1)[1]


class TestModelRoleRoutingPolicy:
    def test_tier_for_role_planner(self) -> None:
        policy = ModelRoleRoutingPolicy()
        assert policy.tier_for_role(ModelRole.PLANNER) == "haiku"

    def test_tier_for_role_doer(self) -> None:
        policy = ModelRoleRoutingPolicy()
        assert policy.tier_for_role(ModelRole.DOER) == "sonnet"

    def test_tier_for_role_critic(self) -> None:
        policy = ModelRoleRoutingPolicy()
        assert policy.tier_for_role(ModelRole.CRITIC) == "opus"

    def test_tier_for_role_debugger(self) -> None:
        policy = ModelRoleRoutingPolicy()
        assert policy.tier_for_role(ModelRole.DEBUGGER) == "sonnet"

    def test_tier_for_role_summarizer(self) -> None:
        policy = ModelRoleRoutingPolicy()
        assert policy.tier_for_role(ModelRole.SUMMARIZER) == "haiku"

    def test_tier_for_role_raises_for_unknown(self) -> None:
        # Invalid roles should not exist, but guard against future additions
        class BogusRole:
            name = "BOGUS"

        policy = ModelRoleRoutingPolicy()
        with pytest.raises(ModelRoleRoutingError):
            policy.tier_for_role(BogusRole)  # type: ignore[arg-type]


class TestModelRoleRouter:
    def make_router(
        self,
        settings: FakeSettings | None = None,
        policy: ModelRoleRoutingPolicy | None = None,
    ) -> ModelRoleRouter:
        return ModelRoleRouter(
            settings=settings or FakeSettings(),
            policy=policy,
        )

    # --- resolve() ---

    def test_resolve_planner_uses_haiku(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.PLANNER)
        assert isinstance(resolved, ModelRoleResolution)
        assert resolved.model_role == ModelRole.PLANNER
        assert resolved.claude_model_name == "haiku"
        assert "haiku" in resolved.provider_model

    def test_resolve_doer_uses_sonnet(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.DOER)
        assert resolved.model_role == ModelRole.DOER
        assert resolved.claude_model_name == "sonnet"

    def test_resolve_critic_prefers_opus(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.CRITIC)
        assert resolved.model_role == ModelRole.CRITIC
        assert resolved.claude_model_name == "opus"
        assert "opus" in resolved.provider_model

    def test_resolve_debugger_uses_sonnet(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.DEBUGGER)
        assert resolved.model_role == ModelRole.DEBUGGER
        assert resolved.claude_model_name == "sonnet"

    def test_resolve_summarizer_uses_haiku(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.SUMMARIZER)
        assert resolved.model_role == ModelRole.SUMMARIZER
        assert resolved.claude_model_name == "haiku"

    # --- provider info ---

    def test_resolve_includes_provider_id_and_model(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.DOER)
        assert resolved.provider_id == "openrouter"
        assert resolved.provider_model is not None
        assert resolved.provider_model_ref is not None

    # --- thinking ---

    def test_opus_enables_thinking(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.CRITIC)
        assert resolved.thinking_enabled is True

    def test_haiku_disables_thinking(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.PLANNER)
        assert resolved.thinking_enabled is False

    def test_sonnet_disables_thinking(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.DOER)
        assert resolved.thinking_enabled is False

    # --- resolve_agent_role() ---

    def test_resolve_agent_role_uses_mapping(self) -> None:
        router = self.make_router()
        for agent_role, expected_model_role in AGENT_TO_MODEL_ROLE.items():
            resolved = router.resolve_agent_role(agent_role)
            assert resolved.model_role == expected_model_role

    def test_resolve_agent_role_architect(self) -> None:
        router = self.make_router()
        resolved = router.resolve_agent_role(AgentRole.ARCHITECT)
        assert resolved.model_role == ModelRole.PLANNER

    def test_resolve_agent_role_arbiter(self) -> None:
        router = self.make_router()
        resolved = router.resolve_agent_role(AgentRole.ARBITER)
        assert resolved.model_role == ModelRole.CRITIC

    def test_resolve_agent_role_raises_for_unmapped(self) -> None:
        router = self.make_router()
        with pytest.raises(ModelRoleRoutingError):
            router.resolve_agent_role("UNKNOWN")  # type: ignore[arg-type]

    # --- resolve_all() ---

    def test_resolve_all_returns_all_roles(self) -> None:
        router = self.make_router()
        all_resolved = router.resolve_all()
        assert set(all_resolved.keys()) == set(ModelRole)
        for role, resolution in all_resolved.items():
            assert resolution.model_role == role

    # --- safety ---

    def test_no_provider_modules_imported(self) -> None:
        import sys

        provider_modules = [
            mod for mod in sys.modules if mod.startswith("providers.")
        ]
        assert not any(
            mod.startswith("providers.") for mod in provider_modules
        ), f"Provider modules should not be imported: {provider_modules}"

    def test_no_api_modules_imported(self) -> None:
        import sys

        api_modules = [mod for mod in sys.modules if mod.startswith("api.")]
        # Settings from config is fine; api/model_router should NOT be imported
        assert not any(
            mod.startswith("api.") for mod in api_modules
        ), f"API modules should not be imported from ralph: {api_modules}"

    # --- custom policy ---

    def test_custom_policy_overrides_default(self) -> None:
        policy = ModelRoleRoutingPolicy(planner_model_name="sonnet")
        router = self.make_router(policy=policy)
        resolved = router.resolve(ModelRole.PLANNER)
        assert resolved.claude_model_name == "sonnet"

    # --- source field ---

    def test_resolution_has_source(self) -> None:
        router = self.make_router()
        resolved = router.resolve(ModelRole.DOER)
        assert resolved.source == "role_policy"
