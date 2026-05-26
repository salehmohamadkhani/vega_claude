"""Tests for core.ralph.agent_profiles."""
from __future__ import annotations

from core.ralph.agent_profiles import AgentProfile, AgentProfileRegistry
from core.ralph.roles import AgentRole
from core.ralph.workspace import RalphWorkspace


class TestAgentProfileRegistry:
    def make_registry(self, tmp_path=None) -> AgentProfileRegistry:
        if tmp_path:
            ws = RalphWorkspace(tmp_path)
            ws.initialize()
            return AgentProfileRegistry(ws)
        return AgentProfileRegistry()

    def test_default_profiles_exist_for_all_roles(self) -> None:
        registry = self.make_registry()
        profiles = registry.default_profiles()
        role_values = {r.value for r in AgentRole}
        profile_roles = {p.agent_role for p in profiles}
        assert profile_roles == role_values

    def test_get_profile_by_agent_role(self) -> None:
        registry = self.make_registry()
        profile = registry.get_profile(AgentRole.DOER)
        assert profile.agent_role == "doer"
        assert profile.name == "Doer"
        assert len(profile.responsibilities) > 0

    def test_get_profile_for_all_roles(self) -> None:
        registry = self.make_registry()
        for role in AgentRole:
            profile = registry.get_profile(role)
            assert profile.agent_role == role.value
            assert len(profile.name) > 0

    def test_model_roles_are_abstract(self) -> None:
        registry = self.make_registry()
        for profile in registry.default_profiles():
            assert profile.model_role in {
                "planner", "doer", "critic", "debugger", "summarizer"
            }

    def test_no_copied_github_agents_dependency(self) -> None:
        """Profiles are FCC-native, not copied from .github/agents."""
        registry = self.make_registry()
        for profile in registry.default_profiles():
            assert profile.name is not None
            # No reference to .github in any field
            assert ".github" not in (profile.description or "")
            assert ".github" not in (profile.prompt_template or "")

    def test_profiles_can_be_saved(self, tmp_path) -> None:
        registry = self.make_registry(tmp_path)
        paths = registry.save_profiles()
        assert len(paths) == len(AgentRole)
        for p in paths:
            assert p.exists()

    def test_profile_id_unique(self) -> None:
        registry = self.make_registry()
        ids = {p.id for p in registry.default_profiles()}
        assert len(ids) == len(AgentRole)

    def test_list_profiles(self) -> None:
        registry = self.make_registry()
        profiles = registry.list_profiles()
        assert len(profiles) == len(AgentRole)

    def test_profile_dataclass(self) -> None:
        profile = AgentProfile(
            agent_role="test",
            model_role="test",
            name="Tester",
            responsibilities=["test"],
        )
        assert profile.name == "Tester"
        assert profile.id is not None
