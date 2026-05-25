"""Tests for new Agent Table modular components.

Tests strategies, consensus, scoring, hooks, validators, protocol,
and context building modules.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from ralph_mode.agent_table import (
    ROLE_ARBITER,
    ROLE_CRITIC,
    ROLE_DOER,
    AgentMessage,
    AgentTable,
    ConsensusEngine,
    ContextBuilder,
    MessageType,
    Phase,
    ProtocolEngine,
    TrustScoring,
    Vote,
)
from ralph_mode.agent_table.hooks import (
    EVENT_APPROVAL,
    EVENT_ESCALATION,
    EVENT_MESSAGE_SENT,
    EVENT_PLAN_SUBMITTED,
    EVENT_ROUND_START,
    EVENT_TABLE_INITIALIZED,
    HookManager,
)
from ralph_mode.agent_table.roles import AgentRole, RoleRegistry
from ralph_mode.agent_table.scoring import AgentTrustRecord
from ralph_mode.agent_table.strategies import (
    AutocraticStrategy,
    DefaultStrategy,
    DemocraticStrategy,
    LenientStrategy,
    StrictStrategy,
    get_strategy,
    list_strategies,
    register_strategy,
)
from ralph_mode.agent_table.validators import MessageValidator, StateValidator, ValidationResult


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def table(tmp_dir):
    t = AgentTable(ralph_dir=tmp_dir)
    t.initialize("Test task")
    return t


# =====================================================================
# ProtocolEngine Tests
# =====================================================================


class TestProtocolEngine:
    def test_advance_phase_plan_to_implement(self):
        engine = ProtocolEngine()
        state = {"current_phase": Phase.PLAN.value}
        result = engine.advance_phase(state)
        assert result["current_phase"] == Phase.IMPLEMENT.value

    def test_advance_phase_implement_to_resolve(self):
        engine = ProtocolEngine()
        state = {"current_phase": Phase.IMPLEMENT.value}
        result = engine.advance_phase(state)
        assert result["current_phase"] == Phase.RESOLVE.value

    def test_advance_phase_resolve_to_approve(self):
        engine = ProtocolEngine()
        state = {"current_phase": Phase.RESOLVE.value}
        result = engine.advance_phase(state)
        assert result["current_phase"] == Phase.APPROVE.value

    def test_advance_phase_approve_stays(self):
        engine = ProtocolEngine()
        state = {"current_phase": Phase.APPROVE.value}
        result = engine.advance_phase(state)
        assert result["current_phase"] == Phase.APPROVE.value

    def test_valid_transition(self):
        engine = ProtocolEngine()
        assert engine.is_valid_transition("plan", "implement")
        assert engine.is_valid_transition("plan", "resolve")
        assert not engine.is_valid_transition("plan", "approve")

    def test_invalid_phase(self):
        engine = ProtocolEngine()
        assert not engine.is_valid_transition("invalid", "plan")

    def test_message_valid_for_phase(self):
        engine = ProtocolEngine()
        assert engine.is_message_valid_for_phase("plan", "plan")
        assert engine.is_message_valid_for_phase("critique", "plan")
        assert not engine.is_message_valid_for_phase("approval", "plan")

    def test_validate_sender_role(self):
        engine = ProtocolEngine()
        ok, err = engine.validate_sender_role(ROLE_DOER, MessageType.PLAN.value)
        assert ok
        ok, err = engine.validate_sender_role(ROLE_DOER, MessageType.APPROVAL.value)
        assert not ok
        assert "not allowed" in err

    def test_set_phase_valid(self):
        engine = ProtocolEngine()
        state = {"current_phase": "plan"}
        result = engine.set_phase(state, "implement")
        assert result["current_phase"] == "implement"

    def test_set_phase_invalid(self):
        engine = ProtocolEngine()
        state = {"current_phase": "plan"}
        with pytest.raises(ValueError, match="Invalid phase"):
            engine.set_phase(state, "invalid")

    def test_deadlock_detection(self):
        engine = ProtocolEngine(deadlock_threshold=2)
        state = {
            "rounds_summary": [
                {"outcome": "rejected"},
                {"outcome": "rejected"},
            ]
        }
        assert engine.detect_deadlock(state)

    def test_no_deadlock(self):
        engine = ProtocolEngine(deadlock_threshold=3)
        state = {
            "rounds_summary": [
                {"outcome": "rejected"},
                {"outcome": "approved"},
                {"outcome": "rejected"},
            ]
        }
        assert not engine.detect_deadlock(state)

    def test_deadlock_info(self):
        engine = ProtocolEngine(deadlock_threshold=2)
        state = {
            "rounds_summary": [
                {"outcome": "rejected", "reason": "Bad code"},
                {"outcome": "rejected", "reason": "Still bad"},
            ]
        }
        info = engine.get_deadlock_info(state)
        assert info["is_deadlocked"]
        assert info["consecutive_rejections"] == 2
        assert len(info["rejection_reasons"]) == 2

    def test_no_deadlock_empty(self):
        engine = ProtocolEngine()
        assert not engine.detect_deadlock({"rounds_summary": []})


# =====================================================================
# Strategies Tests
# =====================================================================


class TestStrategies:
    def test_list_strategies(self):
        names = list_strategies()
        assert "default" in names
        assert "strict" in names
        assert "lenient" in names
        assert "democratic" in names
        assert "autocratic" in names

    def test_get_strategy(self):
        s = get_strategy("default")
        assert isinstance(s, DefaultStrategy)

    def test_get_unknown_strategy(self):
        with pytest.raises(KeyError, match="Unknown strategy"):
            get_strategy("nonexistent")

    def test_default_strategy_escalate(self):
        s = DefaultStrategy()
        state = {"auto_escalate": True}
        assert s.should_escalate(state, False)
        assert not s.should_escalate(state, True)

    def test_strict_always_escalates(self):
        s = StrictStrategy()
        assert s.should_escalate({}, True)
        assert s.should_escalate({}, False)
        assert not s.can_skip_resolve({})

    def test_lenient_auto_approve(self):
        s = LenientStrategy()
        msgs = [
            AgentMessage(
                ROLE_CRITIC,
                ROLE_DOER,
                MessageType.CRITIQUE.value,
                "Good",
                metadata={"approved": True},
            )
        ]
        assert s.should_auto_approve({}, msgs)

    def test_lenient_no_auto_approve_on_reject(self):
        s = LenientStrategy()
        msgs = [
            AgentMessage(
                ROLE_CRITIC,
                ROLE_DOER,
                MessageType.CRITIQUE.value,
                "Bad",
                metadata={"approved": False},
            )
        ]
        assert not s.should_auto_approve({}, msgs)

    def test_democratic_always_escalates(self):
        s = DemocraticStrategy()
        assert s.should_escalate({}, True)
        assert not s.can_skip_resolve({})

    def test_democratic_majority_vote(self):
        s = DemocraticStrategy()
        msgs = [
            AgentMessage(ROLE_DOER, ROLE_ARBITER, MessageType.VOTE.value, "Yes", metadata={"approved": True}),
            AgentMessage(ROLE_CRITIC, ROLE_ARBITER, MessageType.VOTE.value, "Yes", metadata={"approved": True}),
            AgentMessage(ROLE_ARBITER, ROLE_DOER, MessageType.VOTE.value, "No", metadata={"approved": False}),
        ]
        assert s.should_auto_approve({}, msgs)

    def test_autocratic_always_escalates(self):
        s = AutocraticStrategy()
        assert s.should_escalate({}, True)
        assert not s.should_auto_approve({}, [])

    def test_register_custom_strategy(self):
        class MyStrategy(DefaultStrategy):
            name = "my_custom"
            description = "Custom"

        register_strategy(MyStrategy())
        s = get_strategy("my_custom")
        assert s.name == "my_custom"

    def test_strategy_to_dict(self):
        s = DefaultStrategy()
        d = s.to_dict()
        assert d["name"] == "default"
        assert "max_critique_rounds" in d


# =====================================================================
# ConsensusEngine Tests
# =====================================================================


class TestConsensusEngine:
    def test_simple_majority_approve(self):
        ce = ConsensusEngine(quorum_mode="simple_majority", min_voters=2)
        ce.add_vote(Vote("a", True))
        ce.add_vote(Vote("b", True))
        result = ce.evaluate()
        assert result["approved"]
        assert result["has_quorum"]

    def test_simple_majority_reject(self):
        ce = ConsensusEngine(quorum_mode="simple_majority", min_voters=2)
        ce.add_vote(Vote("a", False))
        ce.add_vote(Vote("b", False))
        result = ce.evaluate()
        assert not result["approved"]

    def test_no_quorum(self):
        ce = ConsensusEngine(min_voters=3)
        ce.add_vote(Vote("a", True))
        result = ce.evaluate()
        assert not result["has_quorum"]
        assert not result["approved"]

    def test_unanimous_approve(self):
        ce = ConsensusEngine(quorum_mode="unanimous", min_voters=2)
        ce.add_vote(Vote("a", True))
        ce.add_vote(Vote("b", True))
        result = ce.evaluate()
        assert result["approved"]

    def test_unanimous_reject(self):
        ce = ConsensusEngine(quorum_mode="unanimous", min_voters=2)
        ce.add_vote(Vote("a", True))
        ce.add_vote(Vote("b", False))
        result = ce.evaluate()
        assert not result["approved"]
        assert "b" in result["dissent"]

    def test_supermajority(self):
        ce = ConsensusEngine(quorum_mode="supermajority", min_voters=3)
        ce.add_vote(Vote("a", True))
        ce.add_vote(Vote("b", True))
        ce.add_vote(Vote("c", False))
        result = ce.evaluate()
        assert result["approved"]  # 2/3

    def test_supermajority_reject(self):
        ce = ConsensusEngine(quorum_mode="supermajority", min_voters=3)
        ce.add_vote(Vote("a", True))
        ce.add_vote(Vote("b", False))
        ce.add_vote(Vote("c", False))
        result = ce.evaluate()
        assert not result["approved"]

    def test_weighted_scoring(self):
        ce = ConsensusEngine(quorum_mode="weighted", min_voters=2)
        ce.add_vote(Vote("a", True, weight=2.0))
        ce.add_vote(Vote("b", False, weight=1.0))
        result = ce.evaluate()
        assert result["approved"]  # 2 - 1 = 1 > 0

    def test_weighted_negative(self):
        ce = ConsensusEngine(quorum_mode="weighted", min_voters=2)
        ce.add_vote(Vote("a", False, weight=2.0))
        ce.add_vote(Vote("b", True, weight=1.0))
        result = ce.evaluate()
        assert not result["approved"]  # -2 + 1 = -1 < 0

    def test_confidence_multiplier(self):
        v = Vote("a", True, confidence="high", weight=1.0)
        assert v.weighted_score == 1.5  # 1.0 * 1.0 * 1.5

    def test_vote_replacement(self):
        ce = ConsensusEngine(min_voters=1)
        ce.add_vote(Vote("a", True))
        ce.add_vote(Vote("a", False))  # Replaces
        assert len(ce.votes) == 1
        assert not ce.votes[0].approved

    def test_clear_votes(self):
        ce = ConsensusEngine(min_voters=1)
        ce.add_vote(Vote("a", True))
        ce.clear_votes()
        assert len(ce.votes) == 0

    def test_summary_line(self):
        ce = ConsensusEngine(min_voters=1)
        ce.add_vote(Vote("a", True))
        line = ce.summary_line()
        assert "Approved" in line

    def test_add_vote_from_message(self):
        ce = ConsensusEngine(min_voters=1)
        msg = AgentMessage(ROLE_CRITIC, ROLE_DOER, MessageType.VOTE.value, "I approve", metadata={"approved": True})
        vote = ce.add_vote_from_message(msg)
        assert vote.approved
        assert vote.voter == ROLE_CRITIC


# =====================================================================
# TrustScoring Tests
# =====================================================================


class TestTrustScoring:
    def test_default_trust(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        assert ts.get_trust(ROLE_DOER) == 1.0

    def test_record_event(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        ts.record_event(ROLE_DOER, "vote", aligned_with_outcome=True)
        record = ts.get_record(ROLE_DOER)
        assert record.total_votes == 1
        assert record.accurate_votes == 1

    def test_trust_decreases_on_override(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        # Record many inaccurate votes to decrease trust
        for _ in range(5):
            ts.record_event(ROLE_CRITIC, "vote", aligned_with_outcome=False)
        assert ts.get_trust(ROLE_CRITIC) < 1.0

    def test_persistence(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        ts.record_event(ROLE_DOER, "approval")
        ts.record_event(ROLE_DOER, "vote", aligned_with_outcome=True)

        # Reload
        ts2 = TrustScoring(tmp_dir)
        record = ts2.get_record(ROLE_DOER)
        assert record.total_votes == 1
        assert record.approvals_given == 1

    def test_summary(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        ts.record_event(ROLE_DOER, "vote")
        summary = ts.summary()
        assert ROLE_DOER in summary
        assert "trust_score" in summary[ROLE_DOER]

    def test_reset(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        ts.record_event(ROLE_DOER, "vote")
        ts.reset()
        assert ts.get_trust(ROLE_DOER) == 1.0

    def test_get_weight(self, tmp_dir):
        ts = TrustScoring(tmp_dir)
        w = ts.get_weight(ROLE_DOER)
        assert w == 1.0

    def test_agent_trust_record_accuracy(self):
        r = AgentTrustRecord("test")
        r.total_votes = 10
        r.accurate_votes = 7
        assert r.accuracy == pytest.approx(0.7)

    def test_agent_trust_record_override_rate(self):
        r = AgentTrustRecord("test")
        r.total_decisions = 5
        r.overridden_decisions = 2
        assert r.override_rate == pytest.approx(0.4)


# =====================================================================
# HookManager Tests
# =====================================================================


class TestHookManager:
    def test_register_and_emit(self):
        hooks = HookManager()
        results = []
        hooks.register("test", lambda **kw: results.append(kw))
        hooks.emit("test", key="value")
        assert len(results) == 1
        assert results[0]["key"] == "value"

    def test_decorator_registration(self):
        hooks = HookManager()
        called = []

        @hooks.on("my_event")
        def handler(**kwargs):
            called.append(True)

        hooks.emit("my_event")
        assert len(called) == 1

    def test_multiple_hooks(self):
        hooks = HookManager()
        count = [0]
        hooks.register("e", lambda **kw: count.__setitem__(0, count[0] + 1))
        hooks.register("e", lambda **kw: count.__setitem__(0, count[0] + 1))
        hooks.emit("e")
        assert count[0] == 2

    def test_global_hook(self):
        hooks = HookManager()
        events = []
        hooks.register_global(lambda event, **kw: events.append(event))
        hooks.emit("a")
        hooks.emit("b")
        assert events == ["a", "b"]

    def test_unregister(self):
        hooks = HookManager()
        fn = lambda **kw: None
        hooks.register("e", fn)
        assert hooks.unregister("e", fn)
        assert not hooks.has_hooks("e")

    def test_unregister_all(self):
        hooks = HookManager()
        hooks.register("a", lambda **kw: None)
        hooks.register("b", lambda **kw: None)
        hooks.unregister_all()
        assert hooks.count_hooks() == 0

    def test_error_handling(self):
        hooks = HookManager()
        hooks.register("e", lambda **kw: 1 / 0)
        hooks.register("e", lambda **kw: "ok")
        results = hooks.emit("e")
        assert isinstance(results[0], ZeroDivisionError)
        assert results[1] == "ok"

    def test_list_events(self):
        hooks = HookManager()
        hooks.register("a", lambda **kw: None)
        hooks.register("b", lambda **kw: None)
        events = hooks.list_events()
        assert "a" in events
        assert "b" in events

    def test_count_hooks(self):
        hooks = HookManager()
        hooks.register("a", lambda **kw: None)
        hooks.register("a", lambda **kw: None)
        assert hooks.count_hooks("a") == 2
        assert hooks.count_hooks("b") == 0


# =====================================================================
# Validator Tests
# =====================================================================


class TestMessageValidator:
    def test_valid_message(self):
        v = MessageValidator()
        msg = AgentMessage(ROLE_DOER, ROLE_CRITIC, MessageType.PLAN.value, "Plan here")
        state = {"active": True, "current_phase": "plan", "current_round": 1}
        result = v.validate_message(msg, state)
        assert result.valid

    def test_empty_content(self):
        v = MessageValidator()
        msg = AgentMessage(ROLE_DOER, ROLE_CRITIC, MessageType.PLAN.value, "")
        state = {"active": True, "current_phase": "plan", "current_round": 1}
        result = v.validate_message(msg, state)
        assert not result.valid
        assert any("empty" in e for e in result.errors)

    def test_wrong_role_strict(self):
        v = MessageValidator()
        msg = AgentMessage(ROLE_DOER, ROLE_CRITIC, MessageType.APPROVAL.value, "I approve")
        state = {"active": True, "current_phase": "approve", "current_round": 1}
        result = v.validate_message(msg, state, strict=True)
        assert not result.valid

    def test_wrong_role_lenient(self):
        v = MessageValidator()
        msg = AgentMessage(ROLE_DOER, ROLE_CRITIC, MessageType.APPROVAL.value, "I approve")
        state = {"active": True, "current_phase": "approve", "current_round": 1}
        result = v.validate_message(msg, state, strict=False)
        assert result.valid  # Warning only
        assert len(result.warnings) > 0

    def test_inactive_table(self):
        v = MessageValidator()
        msg = AgentMessage(ROLE_DOER, ROLE_CRITIC, MessageType.PLAN.value, "Plan")
        state = {"active": False, "current_phase": "plan", "current_round": 1}
        result = v.validate_message(msg, state)
        assert not result.valid

    def test_sender_recipient_same(self):
        v = MessageValidator()
        result = v.validate_sender_recipient(ROLE_DOER, ROLE_DOER)
        assert not result.valid


class TestStateValidator:
    def test_valid_state(self):
        v = StateValidator()
        state = {
            "active": True,
            "task": "Test",
            "current_round": 1,
            "current_phase": "plan",
            "max_rounds": 10,
            "escalation_count": 0,
            "rounds_summary": [],
        }
        result = v.validate_state(state)
        assert result.valid

    def test_missing_keys(self):
        v = StateValidator()
        result = v.validate_state({})
        assert not result.valid
        assert len(result.errors) >= 5

    def test_invalid_phase(self):
        v = StateValidator()
        state = {
            "active": True,
            "task": "Test",
            "current_round": 1,
            "current_phase": "invalid_phase",
            "max_rounds": 10,
        }
        result = v.validate_state(state)
        assert not result.valid

    def test_negative_round(self):
        v = StateValidator()
        state = {
            "active": True,
            "task": "Test",
            "current_round": -1,
            "current_phase": "plan",
            "max_rounds": 10,
        }
        result = v.validate_state(state)
        assert not result.valid


# =====================================================================
# RoleRegistry Tests
# =====================================================================


class TestRoleRegistry:
    def test_default_roles(self):
        reg = RoleRegistry()
        assert reg.get(ROLE_DOER) is not None
        assert reg.get(ROLE_CRITIC) is not None
        assert reg.get(ROLE_ARBITER) is not None

    def test_add_custom_role(self):
        reg = RoleRegistry()
        role = AgentRole(
            name="tester",
            display_name="Tester",
            emoji="🧪",
            description="Runs tests",
        )
        reg.register(role)
        assert reg.get("tester").display_name == "Tester"

    def test_remove_role(self):
        reg = RoleRegistry()
        role = AgentRole(name="temp", display_name="Temp", emoji="")
        reg.register(role)
        assert reg.remove("temp")
        assert reg.get("temp") is None

    def test_list_roles(self):
        reg = RoleRegistry()
        roles = reg.all_roles()
        assert len(roles) >= 3
        names = [r.name for r in roles]
        assert ROLE_DOER in names

    def test_arbiter_can_decide(self):
        reg = RoleRegistry()
        arbiter = reg.get(ROLE_ARBITER)
        assert arbiter.can_decide

    def test_doer_cannot_decide(self):
        reg = RoleRegistry()
        doer = reg.get(ROLE_DOER)
        assert not doer.can_decide


# =====================================================================
# Integration: Hooks with AgentTable
# =====================================================================


class TestHooksIntegration:
    def test_init_fires_hook(self, tmp_dir):
        table = AgentTable(ralph_dir=tmp_dir)
        events = []
        table.hooks.register(EVENT_TABLE_INITIALIZED, lambda **kw: events.append(True))
        table.initialize("Test task")
        assert len(events) == 1

    def test_plan_fires_hook(self, table):
        events = []
        table.hooks.register(EVENT_PLAN_SUBMITTED, lambda **kw: events.append(kw))
        table.new_round()
        table.submit_plan("My plan")
        assert len(events) == 1
        assert events[0]["message"].content == "My plan"

    def test_escalation_fires_hook(self, table):
        events = []
        table.hooks.register(EVENT_ESCALATION, lambda **kw: events.append(True))
        table.new_round()
        table.escalate("Need help")
        assert len(events) == 1

    def test_round_start_fires_hook(self, table):
        events = []
        table.hooks.register(EVENT_ROUND_START, lambda **kw: events.append(True))
        table.new_round()
        assert len(events) == 1

    def test_approval_fires_hook(self, table):
        events = []
        table.hooks.register(EVENT_APPROVAL, lambda **kw: events.append(True))
        table.new_round()
        table.submit_approval("All good")
        assert len(events) == 1


# =====================================================================
# Integration: Strategy with AgentTable
# =====================================================================


class TestStrategyIntegration:
    def test_set_strategy_by_name(self, table):
        table.set_strategy("strict")
        assert isinstance(table.strategy, StrictStrategy)

    def test_set_strategy_object(self, table):
        table.strategy = LenientStrategy()
        assert isinstance(table.strategy, LenientStrategy)

    def test_strategy_property(self, table):
        assert isinstance(table.strategy, DefaultStrategy)


# =====================================================================
# Integration: Trust Scoring with AgentTable
# =====================================================================


class TestTrustIntegration:
    def test_escalation_records_trust(self, table):
        table.new_round()
        table.escalate("Critic rejected")
        record = table.trust.get_record(ROLE_CRITIC)
        assert record.escalations_caused >= 1

    def test_decision_records_trust(self, table):
        table.new_round()
        table.submit_decision("Side with doer", side_with=ROLE_DOER)
        record = table.trust.get_record(ROLE_CRITIC)
        assert record.total_decisions >= 1

    def test_approval_records_trust(self, table):
        table.new_round()
        table.submit_approval("Good work")
        record = table.trust.get_record(ROLE_ARBITER)
        assert record.approvals_given >= 1


# =====================================================================
# ValidationResult Tests
# =====================================================================


class TestValidationResult:
    def test_bool_true(self):
        r = ValidationResult(True)
        assert bool(r)

    def test_bool_false(self):
        r = ValidationResult(False, errors=["Error"])
        assert not bool(r)

    def test_to_dict(self):
        r = ValidationResult(True, warnings=["Warn"])
        d = r.to_dict()
        assert d["valid"]
        assert d["warnings"] == ["Warn"]


# =====================================================================
# Consensus + Arbiter Weight
# =====================================================================


class TestArbiterWeight:
    def test_arbiter_gets_extra_weight(self):
        ce = ConsensusEngine(quorum_mode="weighted", min_voters=2, arbiter_weight=2.0)
        msg = AgentMessage(ROLE_ARBITER, ROLE_DOER, MessageType.VOTE.value, "I approve", metadata={"approved": True})
        vote = ce.add_vote_from_message(msg)
        assert vote.weight == 2.0

    def test_non_arbiter_normal_weight(self):
        ce = ConsensusEngine(arbiter_weight=2.0)
        msg = AgentMessage(ROLE_CRITIC, ROLE_DOER, MessageType.VOTE.value, "I approve", metadata={"approved": True})
        vote = ce.add_vote_from_message(msg)
        assert vote.weight == 1.0
