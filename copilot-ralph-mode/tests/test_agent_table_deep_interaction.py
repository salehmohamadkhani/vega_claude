"""Deep interaction tests for the Agent Table.

Tests the full interaction model:
- Conversation threading (message_id, reply_to, thread_id)
- InteractionGraph (threads, relationship matrix, unanswered messages)
- NegotiationManager (multi-turn dialogues, deadlock, escalation callbacks)
- MessageRouter (routing rules, recipient resolution)
- FiniteStateMachine (protocol transitions, guards, history)
- Strategy-based escalation (wired into submit_critique/submit_review)
- Trust-weighted consensus (wired into context)
- Validation in send_message
- New methods: submit_response, request_clarification,
  submit_counter_proposal, submit_objection, submit_acknowledgment
- ContextBuilder with trust, threads, negotiations
"""

import json
import os
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
    InteractionType,
    MessageType,
    Phase,
)
from ralph_mode.agent_table.fsm import FiniteStateMachine, FSMError, build_protocol_fsm
from ralph_mode.agent_table.interaction import ConversationThread, InteractionGraph
from ralph_mode.agent_table.negotiation import Negotiation, NegotiationManager, NegotiationRound, NegotiationStatus
from ralph_mode.agent_table.router import MessageRouter, RoutingRule

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def tmp_ralph(tmp_path):
    """Provide a temp .ralph-mode directory."""
    ralph_dir = tmp_path / ".ralph-mode"
    ralph_dir.mkdir()
    return ralph_dir


@pytest.fixture
def table(tmp_ralph):
    """Provide an initialized AgentTable."""
    t = AgentTable(ralph_dir=tmp_ralph)
    t.initialize("Test task for deep interaction", max_rounds=10, auto_escalate=True)
    return t


@pytest.fixture
def table_with_round(table):
    """AgentTable with one round started."""
    table.new_round()
    return table


# =====================================================================
# 1. Conversation Threading
# =====================================================================


class TestConversationThreading:
    """Test that messages are properly threaded."""

    def test_plan_creates_thread_root(self, table_with_round):
        msg = table_with_round.submit_plan("My plan")
        assert msg.is_thread_root
        assert msg.thread_id == msg.message_id
        assert msg.reply_to is None

    def test_critique_replies_to_plan(self, table_with_round):
        plan = table_with_round.submit_plan("My plan")
        critique = table_with_round.submit_critique("Looks bad", approved=False)
        assert critique.reply_to == plan.message_id
        assert critique.thread_id == plan.thread_id
        assert critique.is_reply

    def test_implementation_creates_new_thread(self, table_with_round):
        table_with_round.submit_plan("My plan")
        table_with_round.submit_critique("OK", approved=True)
        impl = table_with_round.submit_implementation("Done implementing")
        # Implementation starts a new thread
        assert impl.is_thread_root
        assert impl.thread_id == impl.message_id

    def test_review_replies_to_implementation(self, table_with_round):
        table_with_round.submit_plan("My plan")
        table_with_round.submit_critique("OK", approved=True)
        impl = table_with_round.submit_implementation("Done")
        review = table_with_round.submit_review("LGTM", approved=True)
        assert review.reply_to == impl.message_id
        assert review.thread_id == impl.thread_id

    def test_create_reply_preserves_thread(self):
        original = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan X",
            round_number=1,
            phase=Phase.PLAN.value,
        )
        reply = original.create_reply(
            sender=ROLE_CRITIC,
            msg_type=MessageType.CRITIQUE.value,
            content="I disagree",
        )
        assert reply.reply_to == original.message_id
        assert reply.thread_id == original.thread_id
        assert reply.sender == ROLE_CRITIC
        assert reply.recipient == ROLE_DOER

    def test_message_id_uniqueness(self, table_with_round):
        m1 = table_with_round.submit_plan("Plan 1")
        # Start new round
        table_with_round.submit_critique("ok", approved=True)
        table_with_round.submit_approval("Approved")
        table_with_round.new_round()
        m2 = table_with_round.submit_plan("Plan 2")
        assert m1.message_id != m2.message_id


# =====================================================================
# 2. InteractionGraph
# =====================================================================


class TestInteractionGraph:
    """Test the interaction graph module."""

    def test_register_creates_thread(self):
        graph = InteractionGraph()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        thread = graph.register_message(msg)
        assert thread.thread_id == msg.thread_id
        assert thread.depth == 1
        assert ROLE_DOER in thread.participants

    def test_reply_joins_same_thread(self):
        graph = InteractionGraph()
        msg1 = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        graph.register_message(msg1)
        msg2 = msg1.create_reply(ROLE_CRITIC, MessageType.CRITIQUE.value, "Bad")
        thread = graph.register_message(msg2)
        assert thread.depth == 2
        assert {ROLE_DOER, ROLE_CRITIC} == thread.participants

    def test_edge_counts(self):
        graph = InteractionGraph()
        for _ in range(3):
            graph.register_message(
                AgentMessage(
                    sender=ROLE_DOER,
                    recipient=ROLE_CRITIC,
                    msg_type=MessageType.PLAN.value,
                    content="x",
                )
            )
        assert graph.interaction_count(ROLE_DOER, ROLE_CRITIC) == 3
        assert graph.interaction_count(ROLE_CRITIC, ROLE_DOER) == 0

    def test_active_threads(self):
        graph = InteractionGraph()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        graph.register_message(msg)
        assert len(graph.get_active_threads()) == 1
        # Resolve it
        ack = msg.create_reply(ROLE_CRITIC, MessageType.ACKNOWLEDGMENT.value, "OK")
        graph.register_message(ack)
        assert len(graph.get_active_threads()) == 0

    def test_disputed_threads(self):
        graph = InteractionGraph()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
            metadata={},
        )
        graph.register_message(msg)
        # Critique with approved=True
        c1 = msg.create_reply(ROLE_CRITIC, MessageType.CRITIQUE.value, "ok", metadata={"approved": True})
        graph.register_message(c1)
        # Then a rejection
        c2 = c1.create_reply(ROLE_DOER, MessageType.CRITIQUE.value, "no", metadata={"approved": False})
        graph.register_message(c2)
        assert len(graph.get_disputed_threads()) == 1

    def test_relationship_matrix(self):
        graph = InteractionGraph()
        graph.register_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="x",
            )
        )
        graph.register_message(
            AgentMessage(
                sender=ROLE_CRITIC,
                recipient=ROLE_DOER,
                msg_type=MessageType.CRITIQUE.value,
                content="y",
            )
        )
        matrix = graph.get_relationship_matrix()
        assert matrix[ROLE_DOER][ROLE_CRITIC] == 1
        assert matrix[ROLE_CRITIC][ROLE_DOER] == 1

    def test_conversation_flow(self):
        graph = InteractionGraph()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan A",
            round_number=1,
        )
        graph.register_message(msg)
        flow = graph.get_conversation_flow(round_number=1)
        assert len(flow) == 1
        assert flow[0]["sender"] == ROLE_DOER

    def test_most_active_pair(self):
        graph = InteractionGraph()
        for _ in range(5):
            graph.register_message(
                AgentMessage(
                    sender=ROLE_DOER,
                    recipient=ROLE_CRITIC,
                    msg_type=MessageType.PLAN.value,
                    content="x",
                )
            )
        assert graph.most_active_pair() == (ROLE_DOER, ROLE_CRITIC)

    def test_table_wires_interaction_graph(self, table_with_round):
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Bad", approved=False)
        graph = table_with_round.interaction
        assert graph.thread_count >= 1
        assert graph.interaction_count(ROLE_DOER, ROLE_CRITIC) >= 1


# =====================================================================
# 3. NegotiationManager
# =====================================================================


class TestNegotiationManager:
    """Test multi-turn negotiation flows."""

    def test_start_negotiation(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = mgr.start_negotiation(msg, subject="test plan")
        assert neg.initiator == ROLE_DOER
        assert neg.respondent == ROLE_CRITIC
        assert neg.status == NegotiationStatus.AWAITING_RESPONSE.value
        assert neg.round_count == 1

    def test_approve_resolves_negotiation(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = mgr.start_negotiation(msg)
        ack = msg.create_reply(ROLE_CRITIC, MessageType.APPROVAL.value, "OK")
        result = mgr.process_response(ack)
        assert result.status == NegotiationStatus.RESOLVED_ACCEPTED.value

    def test_critique_rejection_keeps_open(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = mgr.start_negotiation(msg)
        crit = msg.create_reply(
            ROLE_CRITIC,
            MessageType.CRITIQUE.value,
            "Bad",
            metadata={"approved": False},
        )
        result = mgr.process_response(crit)
        assert result.status == NegotiationStatus.AWAITING_RESPONSE.value

    def test_counter_proposal_creates_new_round(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = mgr.start_negotiation(msg)
        counter = msg.create_reply(
            ROLE_CRITIC,
            MessageType.COUNTER_PROPOSAL.value,
            "My alt",
        )
        result = mgr.process_response(counter)
        assert result.round_count == 2

    def test_deadlock_detection(self):
        deadlocked = []
        mgr = NegotiationManager(max_negotiation_rounds=2)
        mgr.on_deadlock(lambda n: deadlocked.append(n))

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = mgr.start_negotiation(msg)

        # Round 1: counter
        c1 = msg.create_reply(
            ROLE_CRITIC,
            MessageType.COUNTER_PROPOSAL.value,
            "Alt 1",
        )
        mgr.process_response(c1)

        # Round 2: another counter → deadlock
        c2 = c1.create_reply(
            ROLE_DOER,
            MessageType.COUNTER_PROPOSAL.value,
            "Alt 2",
        )
        result = mgr.process_response(c2)
        assert result.status == NegotiationStatus.DEADLOCKED.value
        assert len(deadlocked) >= 1

    def test_objection_triggers_escalation(self):
        escalated = []
        mgr = NegotiationManager()
        mgr.on_escalate(lambda n: escalated.append(n))

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        mgr.start_negotiation(msg)
        obj = msg.create_reply(
            ROLE_CRITIC,
            MessageType.OBJECTION.value,
            "Fundamental flaw",
        )
        result = mgr.process_response(obj)
        assert result.status == NegotiationStatus.ESCALATED.value
        assert len(escalated) == 1

    def test_clarification_flow(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = mgr.start_negotiation(msg)

        # Clarification request
        clar = msg.create_reply(
            ROLE_CRITIC,
            MessageType.CLARIFICATION.value,
            "What about X?",
        )
        result = mgr.process_response(clar)
        assert result.status == NegotiationStatus.CLARIFICATION_NEEDED.value

        # Clarification response
        resp = clar.create_reply(
            ROLE_DOER,
            MessageType.CLARIFICATION_RESPONSE.value,
            "X is handled by...",
        )
        result = mgr.process_response(resp)
        assert result.status == NegotiationStatus.AWAITING_RESPONSE.value

    def test_negotiation_summary(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        mgr.start_negotiation(msg)
        summary = mgr.summary()
        assert summary["total"] == 1
        assert summary["active"] == 1

    def test_get_awaiting_response_from(self):
        mgr = NegotiationManager()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        mgr.start_negotiation(msg)
        awaiting = mgr.get_awaiting_response_from(ROLE_CRITIC)
        assert len(awaiting) == 1

    def test_table_wires_negotiation(self, table_with_round):
        plan = table_with_round.submit_plan("Plan")
        negs = table_with_round.negotiation.all_negotiations
        assert len(negs) == 1
        assert negs[0].initiator == ROLE_DOER


# =====================================================================
# 4. MessageRouter
# =====================================================================


class TestMessageRouter:
    """Test the message routing system."""

    def test_doer_plan_routes_to_critic(self):
        router = MessageRouter()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient="",
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        state = {"auto_escalate": True, "current_phase": Phase.PLAN.value}
        recipient = router.resolve_recipient(msg, state)
        assert recipient == ROLE_CRITIC

    def test_escalation_routes_to_arbiter(self):
        router = MessageRouter()
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient="",
            msg_type=MessageType.ESCALATION.value,
            content="Help",
        )
        state = {"auto_escalate": True, "current_phase": Phase.RESOLVE.value}
        recipient = router.resolve_recipient(msg, state)
        assert recipient == ROLE_ARBITER

    def test_arbiter_decision_routes_to_doer(self):
        router = MessageRouter()
        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient="",
            msg_type=MessageType.DECISION.value,
            content="Decide",
        )
        state = {"current_phase": Phase.RESOLVE.value}
        recipient = router.resolve_recipient(msg, state)
        assert recipient == ROLE_DOER

    def test_custom_rule(self):
        router = MessageRouter()
        rule = RoutingRule(
            "custom_rule",
            lambda m, s: m.msg_type == "custom_type",
            ROLE_ARBITER,
            priority=200,
        )
        router.add_rule(rule)
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient="",
            msg_type="custom_type",
            content="Custom",
        )
        recipient = router.resolve_recipient(msg, {})
        assert recipient == ROLE_ARBITER

    def test_remove_rule(self):
        router = MessageRouter()
        assert router.remove_rule("plan_to_critic") is True
        assert router.remove_rule("nonexistent") is False

    def test_critic_rejection_to_arbiter_with_escalate(self):
        router = MessageRouter()
        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient="",
            msg_type=MessageType.CRITIQUE.value,
            content="Bad",
            metadata={"approved": False},
        )
        state = {"auto_escalate": True, "current_phase": Phase.PLAN.value}
        recipient = router.resolve_recipient(msg, state)
        assert recipient == ROLE_ARBITER


# =====================================================================
# 5. FiniteStateMachine
# =====================================================================


class TestFiniteStateMachine:
    """Test the protocol FSM."""

    def test_initial_state(self):
        fsm = build_protocol_fsm()
        assert fsm.current_state == "plan"

    def test_plan_approved(self):
        fsm = build_protocol_fsm()
        new = fsm.trigger("plan_approved")
        assert new == "implement"

    def test_plan_rejected_with_escalate(self):
        fsm = build_protocol_fsm()
        new = fsm.trigger("plan_rejected", context={"auto_escalate": True})
        assert new == "resolve"

    def test_plan_rejected_without_escalate(self):
        fsm = build_protocol_fsm()
        new = fsm.trigger("plan_rejected", context={"auto_escalate": False})
        assert new == "plan"  # Stays in plan

    def test_full_happy_path(self):
        fsm = build_protocol_fsm()
        fsm.trigger("plan_approved")
        assert fsm.current_state == "implement"
        fsm.trigger("review_approved")
        assert fsm.current_state == "approve"
        fsm.trigger("approved")
        assert fsm.current_state == "finalized"

    def test_finalized_is_terminal(self):
        fsm = build_protocol_fsm()
        fsm.trigger("plan_approved")
        fsm.trigger("review_approved")
        fsm.trigger("approved")
        with pytest.raises(FSMError, match="terminal"):
            fsm.trigger("anything")

    def test_can_trigger(self):
        fsm = build_protocol_fsm()
        assert fsm.can_trigger("plan_approved")
        assert not fsm.can_trigger("review_approved")

    def test_try_trigger_returns_none_on_invalid(self):
        fsm = build_protocol_fsm()
        assert fsm.try_trigger("nonexistent") is None

    def test_force_state(self):
        fsm = build_protocol_fsm()
        fsm.force_state("resolve")
        assert fsm.current_state == "resolve"

    def test_transition_history(self):
        fsm = build_protocol_fsm()
        fsm.trigger("plan_approved")
        assert len(fsm.history) == 1
        assert fsm.history[0].from_state == "plan"
        assert fsm.history[0].to_state == "implement"

    def test_available_events(self):
        fsm = build_protocol_fsm()
        events = fsm.available_events()
        assert "plan_approved" in events
        assert "plan_rejected" in events

    def test_reachable_states(self):
        fsm = build_protocol_fsm()
        reachable = fsm.reachable_states()
        assert "plan" in reachable
        assert "implement" in reachable
        assert "resolve" in reachable
        assert "approve" in reachable
        assert "finalized" in reachable

    def test_guard_blocks_transition(self):
        fsm = FiniteStateMachine("start")
        fsm.add_state("end")
        fsm.add_transition("start", "end", "go", guard=lambda c: c.get("allowed", False))
        with pytest.raises(FSMError, match="guard"):
            fsm.trigger("go", context={"allowed": False})
        # Allowed when guard passes
        fsm.trigger("go", context={"allowed": True})
        assert fsm.current_state == "end"

    def test_transition_action(self):
        effects = []
        fsm = FiniteStateMachine("a")
        fsm.add_state("b")
        fsm.add_transition("a", "b", "go", action=lambda c: effects.append("fired"))
        fsm.trigger("go")
        assert effects == ["fired"]

    def test_on_enter_on_exit(self):
        log = []
        fsm = FiniteStateMachine("a")
        fsm.add_state("a", on_exit=lambda c: log.append("exit_a"))
        fsm.add_state("b", on_enter=lambda c: log.append("enter_b"))
        fsm.add_transition("a", "b", "go")
        fsm.trigger("go")
        assert log == ["exit_a", "enter_b"]

    def test_get_transition_map(self):
        fsm = build_protocol_fsm()
        tmap = fsm.get_transition_map()
        assert "plan" in tmap
        assert any(t["event"] == "plan_approved" for t in tmap["plan"])


# =====================================================================
# 6. Strategy-Based Escalation
# =====================================================================


class TestStrategyEscalation:
    """Test that strategy controls escalation behavior."""

    def test_default_strategy_escalates_on_rejection(self, table_with_round):
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Bad", approved=False)
        # Default strategy with auto_escalate=True should have escalated
        msgs = table_with_round.get_messages(msg_type=MessageType.ESCALATION.value)
        assert len(msgs) >= 1

    def test_lenient_strategy_no_escalate_on_approval(self, table_with_round):
        table_with_round.set_strategy("lenient")
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Looks good", approved=True)
        msgs = table_with_round.get_messages(msg_type=MessageType.ESCALATION.value)
        assert len(msgs) == 0

    def test_strict_strategy_always_escalates(self, table_with_round):
        table_with_round.set_strategy("strict")
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Fine", approved=True)
        msgs = table_with_round.get_messages(msg_type=MessageType.ESCALATION.value)
        assert len(msgs) >= 1  # Strict escalates even on approval


# =====================================================================
# 7. New Interaction Methods
# =====================================================================


class TestNewInteractionMethods:
    """Test submit_response, request_clarification, etc."""

    def test_submit_response(self, table_with_round):
        plan = table_with_round.submit_plan("Plan")
        resp = table_with_round.submit_response(
            ROLE_CRITIC,
            "I see what you mean",
            in_reply_to=plan,
        )
        assert resp.msg_type == MessageType.RESPONSE.value
        assert resp.reply_to == plan.message_id
        assert resp.thread_id == plan.thread_id

    def test_submit_response_without_reply(self, table_with_round):
        resp = table_with_round.submit_response(
            ROLE_DOER,
            "FYI update",
        )
        assert resp.msg_type == MessageType.RESPONSE.value
        assert resp.recipient == ROLE_CRITIC  # Doer → Critic by default

    def test_request_clarification(self, table_with_round):
        plan = table_with_round.submit_plan("Plan")
        clar = table_with_round.request_clarification(
            ROLE_CRITIC,
            "What about edge case X?",
            in_reply_to=plan,
        )
        assert clar.msg_type == MessageType.CLARIFICATION.value
        assert clar.reply_to == plan.message_id

    def test_submit_clarification_response(self, table_with_round):
        plan = table_with_round.submit_plan("Plan")
        clar = table_with_round.request_clarification(
            ROLE_CRITIC,
            "What about X?",
            in_reply_to=plan,
        )
        resp = table_with_round.submit_clarification_response(
            ROLE_DOER,
            "X is handled by Y",
            in_reply_to=clar,
        )
        assert resp.msg_type == MessageType.CLARIFICATION_RESPONSE.value
        assert resp.reply_to == clar.message_id
        assert resp.thread_id == plan.thread_id  # Same thread

    def test_submit_counter_proposal(self, table_with_round):
        plan = table_with_round.submit_plan("Plan A")
        counter = table_with_round.submit_counter_proposal(
            ROLE_CRITIC,
            "How about Plan B instead?",
            in_reply_to=plan,
        )
        assert counter.msg_type == MessageType.COUNTER_PROPOSAL.value
        assert counter.interaction_type == InteractionType.NEGOTIATION.value

    def test_submit_objection(self, table_with_round):
        plan = table_with_round.submit_plan("Plan")
        objection = table_with_round.submit_objection(
            ROLE_CRITIC,
            "This approach is fundamentally wrong",
            in_reply_to=plan,
        )
        assert objection.msg_type == MessageType.OBJECTION.value
        assert objection.interaction_type == InteractionType.CHALLENGE.value

    def test_submit_acknowledgment(self, table_with_round):
        plan = table_with_round.submit_plan("Plan")
        ack = table_with_round.submit_acknowledgment(
            ROLE_CRITIC,
            "Got it",
            in_reply_to=plan,
        )
        assert ack.msg_type == MessageType.ACKNOWLEDGMENT.value
        assert ack.interaction_type == InteractionType.CONCESSION.value

    def test_clarification_roundtrip_flow(self, table_with_round):
        """Full clarification flow: plan → question → answer → critique."""
        plan = table_with_round.submit_plan("Use async I/O")
        q = table_with_round.request_clarification(
            ROLE_CRITIC,
            "Which async library?",
            in_reply_to=plan,
        )
        a = table_with_round.submit_clarification_response(
            ROLE_DOER,
            "We'll use asyncio with aiohttp",
            in_reply_to=q,
        )
        critique = table_with_round.submit_critique("Good choice, approved", approved=True)
        # All four messages in same thread
        thread = table_with_round.interaction.get_thread(plan.thread_id)
        assert thread is not None
        assert thread.depth >= 3  # plan, question, answer at minimum


# =====================================================================
# 8. Validation in send_message
# =====================================================================


class TestSendMessageValidation:
    """Test that send_message validates messages."""

    def test_rejects_empty_content(self, table_with_round):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="",
        )
        with pytest.raises(ValueError, match="validation failed"):
            table_with_round.send_message(msg)

    def test_rejects_missing_sender(self, table_with_round):
        msg = AgentMessage(
            sender="",
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        with pytest.raises(ValueError, match="validation failed"):
            table_with_round.send_message(msg)

    def test_accepts_valid_message(self, table_with_round):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Valid plan",
        )
        result = table_with_round.send_message(msg)
        assert result.content == "Valid plan"


# =====================================================================
# 9. Context Builder with Trust/Threads/Negotiations
# =====================================================================


class TestEnhancedContext:
    """Test that context includes trust, threads, and negotiation info."""

    def test_doer_context_includes_trust(self, table_with_round):
        ctx = table_with_round.build_doer_context()
        assert "Trust Score" in ctx

    def test_critic_context_includes_trust(self, table_with_round):
        ctx = table_with_round.build_critic_context()
        assert "Trust Score" in ctx

    def test_arbiter_context_includes_agent_trust_scores(self, table_with_round):
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Bad", approved=False)
        ctx = table_with_round.build_arbiter_context()
        assert "Agent Trust Scores" in ctx

    def test_doer_context_after_negotiation(self, table_with_round):
        table_with_round.submit_plan("Plan A")
        table_with_round.request_clarification(ROLE_CRITIC, "Why A?")
        ctx = table_with_round.build_doer_context()
        # Context should include conversation history
        assert "Conversation History" in ctx

    def test_critic_context_includes_role_instructions(self, table_with_round):
        ctx = table_with_round.build_critic_context()
        assert "COUNTER-PROPOSE" in ctx
        assert "REQUEST CLARIFICATION" in ctx


# =====================================================================
# 10. Status Enhancement
# =====================================================================


class TestEnhancedStatus:
    """Test enhanced status output."""

    def test_status_includes_strategy(self, table_with_round):
        status = table_with_round.status()
        assert status["strategy"] == "default"

    def test_status_includes_negotiations(self, table_with_round):
        table_with_round.submit_plan("Plan")
        status = table_with_round.status()
        assert "negotiations" in status
        assert status["negotiations"]["total"] >= 1

    def test_status_includes_threads(self, table_with_round):
        table_with_round.submit_plan("Plan")
        status = table_with_round.status()
        assert "threads" in status
        assert status["threads"]["total"] >= 1

    def test_status_includes_fsm_state(self, table_with_round):
        status = table_with_round.status()
        assert "fsm_state" in status
        assert status["fsm_state"] == "plan"


# =====================================================================
# 11. Sub-module Access Properties
# =====================================================================


class TestSubModuleAccess:
    """Test that all sub-modules are accessible via properties."""

    def test_interaction_property(self, table_with_round):
        assert isinstance(table_with_round.interaction, InteractionGraph)

    def test_negotiation_property(self, table_with_round):
        assert isinstance(table_with_round.negotiation, NegotiationManager)

    def test_router_property(self, table_with_round):
        assert isinstance(table_with_round.router, MessageRouter)

    def test_fsm_property(self, table_with_round):
        assert isinstance(table_with_round.fsm, FiniteStateMachine)


# =====================================================================
# 12. End-to-End Deep Interaction Scenarios
# =====================================================================


class TestE2EDeepInteraction:
    """End-to-end scenarios testing the full interaction model."""

    def test_full_negotiation_flow(self, table_with_round):
        """Plan → Critique(reject) → Counter-proposal → Accept."""
        plan = table_with_round.submit_plan("Use SQL database")

        # Critic asks for clarification
        q = table_with_round.request_clarification(
            ROLE_CRITIC,
            "What about NoSQL?",
            in_reply_to=plan,
        )

        # Doer clarifies
        a = table_with_round.submit_clarification_response(
            ROLE_DOER,
            "SQL is better for our relational data",
            in_reply_to=q,
        )

        # Critic counter-proposes
        counter = table_with_round.submit_counter_proposal(
            ROLE_CRITIC,
            "Hybrid: SQL for relations, Redis for cache",
            in_reply_to=a,
        )

        # Doer acknowledges
        ack = table_with_round.submit_acknowledgment(
            ROLE_DOER,
            "Great compromise, I'll implement both",
            in_reply_to=counter,
        )

        # Check the interaction graph
        graph = table_with_round.interaction
        assert graph.thread_count >= 1
        assert graph.interaction_count(ROLE_DOER, ROLE_CRITIC) >= 2
        assert graph.interaction_count(ROLE_CRITIC, ROLE_DOER) >= 2

    def test_multi_round_with_escalation(self, table_with_round):
        """Multiple rounds ending in Arbiter decision."""
        # Round 1: Plan rejected → auto-escalate
        plan = table_with_round.submit_plan("Approach A")
        table_with_round.submit_critique("Nope", approved=False)
        # Auto-escalation should have occurred (default strategy + auto_escalate=True)
        msgs = table_with_round.get_messages(msg_type=MessageType.ESCALATION.value)
        assert len(msgs) >= 1

        # Arbiter decides
        table_with_round.submit_decision("Go with modified approach", side_with=ROLE_DOER)
        table_with_round.submit_approval("Proceed")

        state = table_with_round.get_state()
        assert state["escalation_count"] >= 1

    def test_interaction_type_tracking(self, table_with_round):
        """Verify interaction types are set correctly."""
        plan = table_with_round.submit_plan("Plan")
        assert plan.interaction_type == InteractionType.REQUEST.value

        critique = table_with_round.submit_critique("Bad", approved=False)
        assert critique.interaction_type == InteractionType.CHALLENGE.value

    def test_trust_scoring_integration(self, table_with_round):
        """Trust events are recorded during interactions."""
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Bad", approved=False)
        trust = table_with_round.trust
        # Critic should have trust events recorded
        record = trust.get_trust(ROLE_CRITIC)
        assert record is not None


# =====================================================================
# 13. ConversationThread Methods
# =====================================================================


class TestConversationThreadMethods:
    """Test ConversationThread data methods."""

    def test_to_text(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan text",
        )
        thread = ConversationThread(msg.thread_id, msg)
        text = thread.to_text()
        assert "[doer→critic]" in text
        assert "(plan)" in text

    def test_reply_chain(self):
        msg1 = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        msg2 = msg1.create_reply(ROLE_CRITIC, MessageType.CRITIQUE.value, "Bad")
        msg3 = msg2.create_reply(ROLE_DOER, MessageType.RESPONSE.value, "Why?")
        thread = ConversationThread(msg1.thread_id, msg1)
        thread.add(msg2)
        thread.add(msg3)
        chain = thread.get_reply_chain(msg3.message_id)
        assert len(chain) == 3
        assert chain[0].message_id == msg1.message_id
        assert chain[2].message_id == msg3.message_id

    def test_last_sender(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        thread = ConversationThread(msg.thread_id, msg)
        assert thread.last_sender == ROLE_DOER

    def test_thread_get(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        thread = ConversationThread(msg.thread_id, msg)
        assert thread.get(msg.message_id) is msg
        assert thread.get("nonexistent") is None


# =====================================================================
# 14. NegotiationRound and Negotiation Data
# =====================================================================


class TestNegotiationData:
    """Test negotiation data structures."""

    def test_negotiation_round_turn_count(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        nr = NegotiationRound(proposal=msg)
        assert nr.turn_count == 1
        nr.response = msg.create_reply(ROLE_CRITIC, MessageType.CRITIQUE.value, "X")
        assert nr.turn_count == 2

    def test_negotiation_to_dict(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        mgr = NegotiationManager()
        neg = mgr.start_negotiation(msg, subject="test")
        d = neg.to_dict()
        assert d["initiator"] == ROLE_DOER
        assert d["respondent"] == ROLE_CRITIC
        assert d["subject"] == "test"

    def test_negotiation_is_stale(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
        )
        neg = Negotiation(
            negotiation_id="x",
            thread_id="t",
            initiator=ROLE_DOER,
            respondent=ROLE_CRITIC,
            subject="test",
            max_rounds=1,
        )
        neg.rounds.append(NegotiationRound(proposal=msg))
        assert neg.is_stale


# =====================================================================
# 15. InteractionType Enum
# =====================================================================


class TestInteractionTypeEnum:
    """Test InteractionType enum values."""

    def test_all_types(self):
        expected = {"request", "response", "challenge", "concession", "negotiation", "information", "directive"}
        actual = {t.value for t in InteractionType}
        assert expected == actual

    def test_serialization(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan",
            interaction_type=InteractionType.REQUEST.value,
        )
        d = msg.to_dict()
        assert d["interaction_type"] == "request"
        restored = AgentMessage.from_dict(d)
        assert restored.interaction_type == "request"
