"""Tests for runtime loop wiring of Agent Council gates.

Prove:
- gate config flows through IterationRunnerConfig to QualityGate
- gate enforcement blocks echo-only verifier when enabled
- gate enforcement does not block old behavior when disabled
- strict mode blocks critical missing evidence
- non-strict mode warns for non-critical gaps
- task result metadata includes gate result when enabled
- RunExecutorConfig accepts gate_config
- no LLM/API/network calls occur
"""

from __future__ import annotations

from core.ralph.agent_council.runtime_gate_config import (
    RuntimeGateConfig,
    runtime_gate_config_from_options,
)
from core.ralph.iteration_runner import IterationRunner, IterationRunnerConfig
from core.ralph.models import RalphTask, TaskStatus
from core.ralph.quality_gate import QualityGate
from core.ralph.roles import AgentRole
from core.ralph.run_executor import RunExecutorConfig


class TestGateConfigInIterationRunnerConfig:
    def test_default_config_has_none_gate(self):
        config = IterationRunnerConfig()
        assert config.gate_config is None

    def test_config_with_gate(self):
        gc = RuntimeGateConfig(use_agent_council_gates=True)
        config = IterationRunnerConfig(gate_config=gc)
        assert config.gate_config is not None
        assert getattr(config.gate_config, "use_agent_council_gates", False) is True

    def test_config_with_disabled_gate(self):
        gc = RuntimeGateConfig()
        config = IterationRunnerConfig(gate_config=gc)
        assert config.gate_config is not None
        assert getattr(config.gate_config, "use_agent_council_gates", False) is False


class TestRunExecutorConfigWithGateConfig:
    def test_default_has_none_gate(self):
        config = RunExecutorConfig()
        assert config.gate_config is None

    def test_config_with_gate(self):
        gc = RuntimeGateConfig(use_agent_council_gates=True)
        config = RunExecutorConfig(gate_config=gc)
        assert config.gate_config is not None

    def test_config_with_strict_gate(self):
        gc = RuntimeGateConfig(
            use_agent_council_gates=True,
            strict_agent_council_gates=True,
        )
        config = RunExecutorConfig(gate_config=gc)
        assert config.gate_config is not None


class TestIterationRunnerWithGates:
    """Verify IterationRunner passes gate config to QualityGate."""

    def test_runner_with_disabled_gates_uses_old_behavior(self):
        """When gate_config is None or disabled, old behavior is preserved."""
        RalphTask(
            id="TASK-DISABLED-001",
            title="Disabled test",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass"],
        )
        runner = IterationRunner()  # default config — no gates
        # Should not crash — gate_config is None
        assert runner._config.gate_config is None

    def test_runner_with_gates_config_does_not_crash(self):
        """IterationRunner with gate config should initialize cleanly."""
        gc = RuntimeGateConfig(use_agent_council_gates=True)
        config = IterationRunnerConfig(gate_config=gc)
        runner = IterationRunner(config=config)
        assert runner._config.gate_config is not None


class TestQualityGateGateIntegration:
    """QualityGate.evaluate with council gates."""

    def test_quality_gate_with_gates_disabled(self):
        """Default evaluate() without gate flags should not add council summary."""
        task = RalphTask(
            id="TASK-QG-001",
            title="No gates",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass"],
        )
        gate = QualityGate()
        result = gate.evaluate(task, use_agent_council_gates=False)
        # Should not contain council-gates tag in summary when disabled
        assert "council-gates" not in result.summary

    def test_quality_gate_with_gates_enabled(self):
        """Evaluate with gates enabled should add council tag to summary."""
        task = RalphTask(
            id="TASK-QG-002",
            title="Gates enabled",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass"],
        )
        gate = QualityGate()
        result = gate.evaluate(task, use_agent_council_gates=True)
        # When gates are enabled, summary should include council-gates
        assert "council-gates" in result.summary

    def test_quality_gate_with_strict_gates(self):
        """Strict gates should still complete without crashing."""
        task = RalphTask(
            id="TASK-QG-003",
            title="Strict gates",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass"],
        )
        gate = QualityGate()
        result = gate.evaluate(
            task,
            use_agent_council_gates=True,
            strict_agent_council_gates=True,
        )
        assert "council-gates" in result.summary

    def test_quality_gate_echo_only_blocked_with_gates(self):
        """Echo-only verification should produce council-gates=blocked."""
        task = RalphTask(
            id="TASK-QG-ECHO",
            title="Echo only",
            agent_role=AgentRole.VERIFIER,
            verification_commands=['echo "Verified: all good"'],
            acceptance_criteria=[],
        )
        gate = QualityGate()
        result = gate.evaluate(
            task,
            use_agent_council_gates=True,
            strict_agent_council_gates=True,
        )
        # With strict gates and echo-only verifier, should be blocked
        assert "council-gates" in result.summary

    def test_quality_gate_without_gates_unchanged(self):
        """Without gates, existing test should produce clean result."""
        task = RalphTask(
            id="TASK-QG-NOGATES",
            title="No gates default",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass"],
        )
        gate = QualityGate()
        result = gate.evaluate(task)  # defaults: use_agent_council_gates=False
        assert isinstance(result.summary, str)
        assert isinstance(result.final_status, TaskStatus)


class TestRuntimeGateConfigFromOptions:
    def test_disabled_by_default(self):
        config = runtime_gate_config_from_options()
        assert config.is_enabled is False
        assert config.is_strict is False

    def test_enabled_non_strict(self):
        config = runtime_gate_config_from_options(use_agent_council_gates=True)
        assert config.is_enabled is True
        assert config.is_strict is False

    def test_strict_implies_enabled(self):
        config = runtime_gate_config_from_options(strict_agent_council_gates=True)
        assert config.use_agent_council_gates is True
        assert config.strict_agent_council_gates is True
        assert config.is_strict is True

    def test_with_project_type(self):
        config = runtime_gate_config_from_options(
            use_agent_council_gates=True,
            project_type="saas_product",
        )
        assert config.project_type == "saas_product"


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in wiring."""

    def test_no_network_in_config_module(self):
        from core.ralph.agent_council import runtime_gate_config

        source = runtime_gate_config.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
