"""Tests for core.ralph.verification_profiles."""

from __future__ import annotations

from core.ralph.verification_profiles import (
    ProfileDecision,
    VerificationProfile,
    make_profile_decision,
    profile_from_string,
    select_profile_for_goal,
)


class TestSelectProfileForGoal:
    """Auto-detection of verification profiles from goal text."""

    def test_calculator_goal_detects_throwaway(self) -> None:
        """Calculator goal should auto-detect as THROWAWAY_APP."""
        decision = select_profile_for_goal(
            title="Build a tiny browser calculator app",
            description="HTML, CSS, and JavaScript calculator",
        )
        assert decision.profile == VerificationProfile.THROWAWAY_APP
        assert "throwaway" in decision.reason.lower()

    def test_browser_app_detects_throwaway(self) -> None:
        """Browser app with HTML/CSS/JS should detect as THROWAWAY_APP."""
        decision = select_profile_for_goal(
            title="Build a landing page",
            description="Create an HTML/CSS/JS landing page",
            kpis=["Files stay inside the workspace"],
        )
        assert decision.profile == VerificationProfile.THROWAWAY_APP

    def test_standalone_app_detects_throwaway(self) -> None:
        """Standalone app should detect as THROWAWAY_APP."""
        decision = select_profile_for_goal(
            title="Create a standalone JS app",
        )
        assert decision.profile == VerificationProfile.THROWAWAY_APP

    def test_ralph_runtime_goal_detects_ralph_runtime(self) -> None:
        """Ralph Runtime goal should detect as RALPH_RUNTIME."""
        decision = select_profile_for_goal(
            title="Add new provider routing",
            description="Extend the Ralph Runtime to support a new provider",
        )
        assert decision.profile == VerificationProfile.RALPH_RUNTIME

    def test_core_cli_goal_detects_ralph_runtime(self) -> None:
        """CLI/core goal should detect as RALPH_RUNTIME."""
        decision = select_profile_for_goal(
            title="Add new CLI command to the Ralph Runtime",
        )
        assert decision.profile == VerificationProfile.RALPH_RUNTIME

    def test_documentation_goal_detects_documentation(self) -> None:
        """Documentation goal should detect as DOCUMENTATION."""
        decision = select_profile_for_goal(
            title="Update project documentation",
            description="Write docs for the new API feature",
        )
        assert decision.profile == VerificationProfile.DOCUMENTATION

    def test_readme_goal_detects_documentation(self) -> None:
        """README goal should detect as DOCUMENTATION."""
        decision = select_profile_for_goal(
            title="Write a README for the project",
        )
        assert decision.profile == VerificationProfile.DOCUMENTATION

    def test_generic_goal_falls_back_to_generic(self) -> None:
        """Unrecognized goal should fall back to GENERIC."""
        decision = select_profile_for_goal(
            title="Do something vague",
            description="An unspecified task",
            constraints=[],
            kpis=[],
        )
        assert decision.profile == VerificationProfile.GENERIC

    def test_generic_does_not_have_pytest(self) -> None:
        """GENERIC profile should not include pytest commands."""
        decision = select_profile_for_goal(
            title="Unclear task",
        )
        commands = decision.recommended_commands
        for role_cmds in commands.values():
            assert not any("pytest" in cmd for cmd in role_cmds)

    def test_throwaway_does_not_have_pytest(self) -> None:
        """THROWAWAY_APP profile should not include pytest commands."""
        decision = select_profile_for_goal(
            title="Build a calculator app",
        )
        commands = decision.recommended_commands
        for role_cmds in commands.values():
            assert not any("pytest" in cmd for cmd in role_cmds)
            assert not any("ruff" in cmd for cmd in role_cmds)
            assert not any("ty " in cmd for cmd in role_cmds)


class TestProfileDecision:
    """ProfileDecision dataclass structure."""

    def test_profile_decision_has_profile(self) -> None:
        decision = select_profile_for_goal(title="Add provider routing")
        assert isinstance(decision, ProfileDecision)
        assert isinstance(decision.profile, VerificationProfile)
        assert isinstance(decision.reason, str)

    def test_profile_decision_has_recommendations(self) -> None:
        decision = select_profile_for_goal(title="Build a calculator")
        assert isinstance(decision.recommended_commands, dict)
        assert isinstance(decision.recommended_kpis, dict)

    def test_profile_decision_all_roles_present(self) -> None:
        decision = select_profile_for_goal(title="Any goal")
        for role in ("architect", "doer", "verifier"):
            assert role in decision.recommended_commands
            assert role in decision.recommended_kpis


class TestProfileFromString:
    """String-to-profile conversion."""

    def test_valid_profile_name(self) -> None:
        assert profile_from_string("throwaway-app") == VerificationProfile.THROWAWAY_APP

    def test_valid_ralph_runtime(self) -> None:
        assert profile_from_string("ralph-runtime") == VerificationProfile.RALPH_RUNTIME

    def test_valid_documentation(self) -> None:
        assert profile_from_string("documentation") == VerificationProfile.DOCUMENTATION

    def test_valid_generic(self) -> None:
        assert profile_from_string("generic") == VerificationProfile.GENERIC

    def test_invalid_profile_raises(self) -> None:
        import pytest as _pytest

        with _pytest.raises(ValueError):
            profile_from_string("invalid-profile")


class TestMakeProfileDecision:
    """Explicit profile decision creation."""

    def test_make_throwaway(self) -> None:
        decision = make_profile_decision(VerificationProfile.THROWAWAY_APP)
        assert decision.profile == VerificationProfile.THROWAWAY_APP
        # Should not include pytest commands
        for role_cmds in decision.recommended_commands.values():
            assert not any("pytest" in cmd for cmd in role_cmds)

    def test_make_ralph_runtime(self) -> None:
        decision = make_profile_decision(VerificationProfile.RALPH_RUNTIME)
        assert decision.profile == VerificationProfile.RALPH_RUNTIME

    def test_make_documentation(self) -> None:
        decision = make_profile_decision(VerificationProfile.DOCUMENTATION)
        assert decision.profile == VerificationProfile.DOCUMENTATION

    def test_make_generic(self) -> None:
        decision = make_profile_decision(VerificationProfile.GENERIC)
        assert decision.profile == VerificationProfile.GENERIC
