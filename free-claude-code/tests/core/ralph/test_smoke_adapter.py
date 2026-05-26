"""Tests for core.ralph.smoke_adapter."""

from __future__ import annotations

from core.ralph.smoke_adapter import FCCSmokeAdapter, SmokePlan


class TestFCCSmokeAdapter:
    def test_known_targets_populated(self) -> None:
        adapter = FCCSmokeAdapter()
        assert "providers" in adapter.known_targets
        assert "api" in adapter.known_targets
        assert "cli" in adapter.known_targets
        assert "telegram" in adapter.known_targets
        assert "discord" in adapter.known_targets

    def test_is_known_returns_true_for_known(self) -> None:
        adapter = FCCSmokeAdapter()
        assert adapter.is_known("providers") is True

    def test_is_known_returns_false_for_unknown(self) -> None:
        adapter = FCCSmokeAdapter()
        assert adapter.is_known("nonexistent_target") is False

    def test_validate_targets_all_known(self) -> None:
        adapter = FCCSmokeAdapter()
        known, unknown = adapter.validate_targets(["providers", "api"])
        assert len(known) == 2
        assert len(unknown) == 0

    def test_validate_targets_mixed(self) -> None:
        adapter = FCCSmokeAdapter()
        known, unknown = adapter.validate_targets(["providers", "bogus_target", "api"])
        assert len(known) == 2
        assert unknown == ["bogus_target"]

    def test_build_smoke_plan_empty(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan([])
        assert isinstance(plan, SmokePlan)
        assert plan.targets == ()
        assert len(plan.commands) == 1
        assert plan.commands[0] == "uv run pytest smoke --collect-only -q"
        assert plan.unknown_targets == ()
        assert plan.requires_live_provider is False

    def test_build_smoke_plan_single(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["providers"])
        assert "providers" in plan.targets
        assert len(plan.commands) == 1
        assert plan.commands[0].startswith("uv run pytest")
        assert "providers" in plan.commands[0]

    def test_build_smoke_plan_multiple(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["api", "cli", "config"])
        assert len(plan.targets) == 3
        assert len(plan.commands) == 3

    def test_build_smoke_plan_unknown_targets(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["providers", "fake_target"])
        assert len(plan.targets) == 1
        assert plan.unknown_targets == ("fake_target",)

    def test_requires_live_provider_for_providers(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["providers"])
        assert plan.requires_live_provider is True

    def test_requires_live_provider_for_api(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["api"])
        assert plan.requires_live_provider is True

    def test_no_live_provider_for_config(self) -> None:
        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["config"])
        assert plan.requires_live_provider is False

    def test_custom_known_targets(self) -> None:
        adapter = FCCSmokeAdapter(known_targets={"custom": "pytest custom"})
        assert adapter.is_known("custom") is True
        assert adapter.is_known("providers") is False

    def test_build_smoke_plan_all_known_fcc_targets(self) -> None:
        """All known FCC targets should produce valid uv run pytest --collect-only commands."""
        adapter = FCCSmokeAdapter()
        for target in adapter.known_targets:
            plan = adapter.build_smoke_plan([target])
            assert len(plan.targets) == 1
            assert plan.commands[0].startswith("uv run pytest")
            assert "--collect-only" in plan.commands[0]
            assert "-q" in plan.commands[0]

    def test_all_known_targets_match_features_inventory(self) -> None:
        """The known target set must stay in sync with smoke/features.py."""
        adapter = FCCSmokeAdapter()
        # Extracted from FEATURE_INVENTORY smoke_targets across all entries:
        # providers, api, cli, clients, nvidia_nim_cli, openrouter_free_cli,
        # config, messaging, tools, voice, rate_limit, auth, extensibility,
        # lmstudio, llamacpp, ollama, telegram, discord
        expected = {
            "providers", "api", "cli", "clients",
            "nvidia_nim_cli", "openrouter_free_cli",
            "config", "messaging", "tools", "voice",
            "rate_limit", "auth", "extensibility",
            "lmstudio", "llamacpp", "ollama",
            "telegram", "discord",
        }
        assert adapter.known_targets == expected
