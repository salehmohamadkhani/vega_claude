"""Tests for RuntimeGateConfig (runtime_gate_config.py).

Prove:
- default config disables gates
- strict mode implies gates
- is_enabled only True when use_agent_council_gates=True
- is_strict only True when both flags are True
- dict conversion produces correct keys
- from_options enforces strict implies gates
- no LLM/API/network calls occur
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from core.ralph.agent_council.runtime_gate_config import (
    RuntimeGateConfig,
    runtime_gate_config_from_options,
    runtime_gate_config_to_dict,
)


class TestRuntimeGateConfig:
    def test_default_disables_gates(self):
        config = RuntimeGateConfig()
        assert config.use_agent_council_gates is False
        assert config.strict_agent_council_gates is False
        assert config.is_enabled is False
        assert config.is_strict is False

    def test_is_enabled_returns_false_by_default(self):
        assert RuntimeGateConfig().is_enabled is False

    def test_is_enabled_true_when_use_agent_council_gates(self):
        config = RuntimeGateConfig(use_agent_council_gates=True)
        assert config.is_enabled is True
        assert config.is_strict is False

    def test_is_strict_only_when_both_flags_on(self):
        config = RuntimeGateConfig(
            use_agent_council_gates=True,
            strict_agent_council_gates=True,
        )
        assert config.is_enabled is True
        assert config.is_strict is True

    def test_is_strict_false_when_gates_disabled(self):
        """Strict without use_agent_council_gates should not be possible."""
        config = RuntimeGateConfig(
            use_agent_council_gates=False,
            strict_agent_council_gates=True,
        )
        # Config itself doesn't enforce — that's from_options responsibility
        assert config.use_agent_council_gates is False
        assert config.strict_agent_council_gates is True
        # But runtime should check is_enabled
        assert config.is_enabled is False

    def test_project_type_defaults_to_none(self):
        config = RuntimeGateConfig()
        assert config.project_type is None
        assert config.project_goal is None

    def test_frozen_dataclass(self):
        config = RuntimeGateConfig(project_type="landing_page")
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.project_type = "other"  # type: ignore[misc]


class TestDictConversion:
    def test_to_dict_has_required_keys(self):
        config = RuntimeGateConfig()
        d = runtime_gate_config_to_dict(config)
        assert d["use_agent_council_gates"] is False
        assert d["strict_agent_council_gates"] is False
        assert d["is_enabled"] is False
        assert d["is_strict"] is False
        assert d["project_type"] == ""
        assert d["project_goal"] == ""

    def test_to_dict_with_values(self):
        config = RuntimeGateConfig(
            use_agent_council_gates=True,
            strict_agent_council_gates=True,
            project_type="full_stack_app",
            project_goal="Build a CRM",
        )
        d = runtime_gate_config_to_dict(config)
        assert d["use_agent_council_gates"] is True
        assert d["strict_agent_council_gates"] is True
        assert d["is_enabled"] is True
        assert d["is_strict"] is True
        assert d["project_type"] == "full_stack_app"

    def test_json_serializable(self):
        d = runtime_gate_config_to_dict(RuntimeGateConfig())
        assert json.dumps(d) is not None


class TestFromOptions:
    def test_defaults_disable(self):
        config = runtime_gate_config_from_options()
        assert config.use_agent_council_gates is False
        assert config.strict_agent_council_gates is False

    def test_strict_implies_gates(self):
        """--strict-agent-council-gates implies --use-agent-council-gates."""
        config = runtime_gate_config_from_options(
            strict_agent_council_gates=True,
        )
        assert config.use_agent_council_gates is True
        assert config.strict_agent_council_gates is True
        assert config.is_enabled is True
        assert config.is_strict is True

    def test_explicit_gates_without_strict(self):
        config = runtime_gate_config_from_options(
            use_agent_council_gates=True,
        )
        assert config.use_agent_council_gates is True
        assert config.strict_agent_council_gates is False
        assert config.is_enabled is True
        assert config.is_strict is False

    def test_with_project_type(self):
        config = runtime_gate_config_from_options(
            use_agent_council_gates=True,
            project_type="landing_page",
        )
        assert config.project_type == "landing_page"

    def test_with_project_goal(self):
        config = runtime_gate_config_from_options(
            use_agent_council_gates=True,
            project_goal="Build a CRM",
        )
        assert config.project_goal == "Build a CRM"


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in gate config module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import runtime_gate_config

        source = runtime_gate_config.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content
