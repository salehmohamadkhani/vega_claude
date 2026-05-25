"""Agent Table — Multi-agent deliberation protocol for Ralph Mode.

Implements a pluggable multi-agent collaboration pattern:
  Agent 1 (Doer)    – Executes tasks, writes code
  Agent 2 (Critic)  – Reviews plans and code, provides critique
  Agent 3 (Arbiter) – Makes final decisions, resolves disagreements

Modular architecture:
  models        – Data models (AgentMessage, Phase, MessageType, enums)
  roles         – Agent role definitions and registry
  state         – Table state persistence and round management
  transcript    – JSONL-based message log with queries
  protocol      – Phase transition logic and deadlock detection
  strategies    – Pluggable deliberation strategies
  consensus     – Voting, quorum, weighted scoring
  scoring       – Per-agent trust tracking
  context       – Per-agent markdown context builders
  hooks         – Event-driven callbacks
  validators    – Message and state validation
  interaction   – Conversation threads and relationship graph
  negotiation   – Multi-turn dialogue and counter-proposal management
  router        – Conditional message routing
  fsm           – Finite state machine for protocol transitions
  table         – Main orchestrator (AgentTable)
"""

# Consensus
from .consensus import ConsensusEngine, Vote

# Context
from .context import ContextBuilder

# FSM
from .fsm import FiniteStateMachine, FSMError, Transition, TransitionRecord, build_protocol_fsm

# Hooks
from .hooks import (
    EVENT_APPROVAL,
    EVENT_CONSENSUS_REACHED,
    EVENT_CRITIQUE_SUBMITTED,
    EVENT_DEADLOCK_DETECTED,
    EVENT_DECISION,
    EVENT_ESCALATION,
    EVENT_IMPLEMENTATION_SUBMITTED,
    EVENT_MESSAGE_SENT,
    EVENT_PHASE_CHANGE,
    EVENT_PLAN_SUBMITTED,
    EVENT_REJECTION,
    EVENT_REVIEW_SUBMITTED,
    EVENT_ROUND_END,
    EVENT_ROUND_START,
    EVENT_TABLE_FINALIZED,
    EVENT_TABLE_INITIALIZED,
    EVENT_TABLE_RESET,
    EVENT_VOTE_CAST,
    HookManager,
)

# Interaction
from .interaction import ConversationThread, InteractionGraph

# Core models
from .models import AgentMessage, Confidence, InteractionType, MessageType, Phase, Severity

# Negotiation
from .negotiation import Negotiation, NegotiationManager, NegotiationRound, NegotiationStatus

# Protocol
from .protocol import ProtocolEngine

# Roles
from .roles import ALL_ROLES, ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER, AgentRole, RoleRegistry

# Router
from .router import MessageRouter, RoutingRule

# Trust scoring
from .scoring import AgentTrustRecord, TrustScoring

# Strategies
from .strategies import (
    AutocraticStrategy,
    DefaultStrategy,
    DeliberationStrategy,
    DemocraticStrategy,
    LenientStrategy,
    StrictStrategy,
    get_strategy,
    list_strategies,
    register_strategy,
)

# Orchestrator
from .table import AgentTable

# Transcript
from .transcript import TranscriptStore

# Validators
from .validators import MessageValidator, StateValidator, ValidationResult

__all__ = [
    # Core
    "AgentTable",
    "AgentMessage",
    "Phase",
    "MessageType",
    "Severity",
    "Confidence",
    "InteractionType",
    # Roles
    "ROLE_DOER",
    "ROLE_CRITIC",
    "ROLE_ARBITER",
    "ALL_ROLES",
    "AgentRole",
    "RoleRegistry",
    # Strategies
    "DeliberationStrategy",
    "DefaultStrategy",
    "StrictStrategy",
    "LenientStrategy",
    "DemocraticStrategy",
    "AutocraticStrategy",
    "get_strategy",
    "list_strategies",
    "register_strategy",
    # Consensus
    "ConsensusEngine",
    "Vote",
    # Trust
    "TrustScoring",
    "AgentTrustRecord",
    # Protocol
    "ProtocolEngine",
    # Context
    "ContextBuilder",
    # Hooks
    "HookManager",
    "EVENT_PHASE_CHANGE",
    "EVENT_ROUND_START",
    "EVENT_ROUND_END",
    "EVENT_MESSAGE_SENT",
    "EVENT_PLAN_SUBMITTED",
    "EVENT_CRITIQUE_SUBMITTED",
    "EVENT_IMPLEMENTATION_SUBMITTED",
    "EVENT_REVIEW_SUBMITTED",
    "EVENT_ESCALATION",
    "EVENT_DECISION",
    "EVENT_APPROVAL",
    "EVENT_REJECTION",
    "EVENT_TABLE_INITIALIZED",
    "EVENT_TABLE_FINALIZED",
    "EVENT_TABLE_RESET",
    "EVENT_VOTE_CAST",
    "EVENT_CONSENSUS_REACHED",
    "EVENT_DEADLOCK_DETECTED",
    # Validators
    "MessageValidator",
    "StateValidator",
    "ValidationResult",
    # Transcript
    "TranscriptStore",
    # Interaction (NEW)
    "InteractionGraph",
    "ConversationThread",
    # Negotiation (NEW)
    "NegotiationManager",
    "Negotiation",
    "NegotiationStatus",
    "NegotiationRound",
    # Router (NEW)
    "MessageRouter",
    "RoutingRule",
    # FSM (NEW)
    "FiniteStateMachine",
    "build_protocol_fsm",
    "FSMError",
    "Transition",
    "TransitionRecord",
]
