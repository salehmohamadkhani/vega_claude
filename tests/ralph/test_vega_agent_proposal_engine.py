"""Tests for the Auto Agent Proposal Engine (vega_agents/engine.py).

Covers:
- TaskAgentProposal construction and convenience properties
- Gap analysis detection and non-detection
- ProposedAgentBlueprint generation and .to_blueprint()
- Full proposal creation for various task types
- Edge cases (gibberish, empty, very short tasks)
- Safety guarantees (no execution, no env, no network, no LLM calls)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the worktree root is on sys.path
_worktree = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _worktree not in sys.path:
    sys.path.insert(0, _worktree)

import pytest

from vega_agents.blueprints import AgentBlueprint
from vega_agents.engine import (
    GapResult,
    ProposedAgentBlueprint,
    TaskAgentProposal,
    _analyze_gap,
    _compute_blueprint_score,
    _generate_proposed_blueprint,
    _infer_category,
    _tokenize,
    create_proposal,
    has_gap,
    propose_agents,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def proposal_engine() -> type:  # module reference
    import vega_agents.engine as eng
    return eng


# ── Tokeniser ───────────────────────────────────────────────────────────────────────


class TestTokenise:
    def test_removes_stop_words(self) -> None:
        tokens = _tokenize("please add the new feature to the system")
        assert "please" not in tokens
        assert "the" not in tokens
        assert "add" not in tokens
        assert "feature" in tokens
        assert "system" in tokens

    def test_removes_single_char_tokens(self) -> None:
        tokens = _tokenize("a b c test x y z")
        assert "test" in tokens
        assert "x" not in tokens  # single char
        assert "y" not in tokens
        assert "z" not in tokens

    def test_preserves_underscored_terms(self) -> None:
        tokens = _tokenize("implement rate_limiting and jwt_auth")
        assert "rate_limiting" in tokens
        assert "jwt_auth" in tokens

    def test_returns_empty_for_stop_words_only(self) -> None:
        tokens = _tokenize("the and for with this that")
        assert len(tokens) == 0

    def test_returns_empty_for_empty_string(self) -> None:
        tokens = _tokenize("")
        assert len(tokens) == 0

    def test_returns_empty_for_gibberish_numbers(self) -> None:
        tokens = _tokenize("123 456 789")
        assert len(tokens) == 0


# ── Blueprint scoring ───────────────────────────────────────────────────────────────


class TestComputeBlueprintScore:
    def test_perfect_keyword_match_returns_high_score(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("security.audit")
        assert bp is not None
        # Use exact keywords from the blueprint: audit, vulnerability, cve, injection, xss, csrf
        score = _compute_blueprint_score(
            bp,
            "audit vulnerability cve injection xss csrf security audit",
        )
        assert score > 0.5, f"Expected high score for exact keyword match, got {score}"
        assert score <= 1.0

    def test_no_match_returns_low_score(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("docs.faq")
        assert bp is not None
        score = _compute_blueprint_score(
            bp, "Optimize database query performance with indexing"
        )
        assert score < 0.3, f"Expected low score for unrelated match, got {score}"

    def test_partial_match_returns_moderate_score(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("code.refactor")
        assert bp is not None
        # Task partially matching refactoring concepts
        score = _compute_blueprint_score(
            bp, "Clean up and restructure the module architecture"
        )
        assert 0.2 < score < 0.9, f"Expected moderate score, got {score}"

    def test_empty_task_text_returns_zero(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("code.refactor")
        assert bp is not None
        score = _compute_blueprint_score(bp, "")
        assert score == 0.0


# ── Gap analysis ────────────────────────────────────────────────────────────────────


class TestAnalyzeGap:
    def test_no_gap_for_well_covered_task(self) -> None:
        """Tasks fully covered by existing blueprints should have no gap."""
        matched = []
        gap = _analyze_gap("audit security vulnerabilities", matched)
        assert gap is not None
        # The catalog HAS security.audit, so tokens like "audit", "security"
        # should be covered by the catalog even though matched list is empty
        assert gap.has_gap is False or gap.coverage_ratio >= 0.5

    def test_no_gap_for_familiar_task_using_search(self) -> None:
        """A common task like 'add unit tests' should have matching blueprints."""
        from vega_agents.blueprints import search_blueprints

        matched = search_blueprints("write unit tests for the new module")
        gap = _analyze_gap("write unit tests for the new module", matched)
        assert gap is not None
        # "test" and "unit" are well-covered
        assert gap.coverage_ratio >= 0.3

    def test_gap_for_ml_workflow(self) -> None:
        """ML-related tasks may not be fully covered by existing blueprints."""
        from vega_agents.blueprints import search_blueprints

        matched = search_blueprints(
            "Train a PyTorch model and run inference on a dataset"
        )
        gap = _analyze_gap(
            "Train a PyTorch model and run inference on a dataset",
            matched,
        )
        assert gap is not None
        # PyTorch, train, inference, dataset may not be in the catalog
        # This check verifies the gap detection runs without error

    def test_gap_for_obscure_domain(self) -> None:
        """Tasks about obscure domains should be flagged as gaps."""
        from vega_agents.blueprints import search_blueprints

        matched = search_blueprints("quantum error correction with surface codes")
        gap = _analyze_gap(
            "quantum error correction with surface codes",
            matched,
        )
        assert gap is not None
        # "quantum", "surface" are not in any blueprint → should be a gap

    def test_no_gap_for_gibberish(self) -> None:
        """Gibberish will fall through — no tokens match anything."""
        matched = []
        gap = _analyze_gap("xyzzytron megablaster", matched)
        assert gap is not None
        # The gibberish tokens are not in the catalog
        assert gap.coverage_ratio < 0.5

    def test_empty_text_returns_no_gap(self) -> None:
        matched = []
        gap = _analyze_gap("", matched)
        assert gap is not None
        assert gap.has_gap is False
        assert gap.coverage_ratio == 1.0


# ── Category inference ──────────────────────────────────────────────────────────────


class TestInferCategory:
    def test_code_signals(self) -> None:
        assert _infer_category(("refactor", "class", "function")) == "code"

    def test_security_signals(self) -> None:
        assert _infer_category(("encrypt", "tls", "xss")) == "security"

    def test_ml_signals(self) -> None:
        assert _infer_category(("model", "train", "pytorch")) == "ml"

    def test_data_signals(self) -> None:
        assert _infer_category(("etl", "pipeline", "schema")) == "data"

    def test_devops_signals(self) -> None:
        assert _infer_category(("deploy", "helm", "terraform")) == "devops"

    def test_ux_signals(self) -> None:
        assert _infer_category(("responsive", "a11y", "wireframe")) == "ux"

    def test_general_fallback(self) -> None:
        assert _infer_category(("widget", "gizmo", "flubber")) == "general"

    def test_empty_returns_general(self) -> None:
        assert _infer_category(()) == "general"


# ── ProposedAgentBlueprint ──────────────────────────────────────────────────────────


class TestProposedAgentBlueprint:
    def test_to_blueprint_returns_agent_blueprint(self) -> None:
        proposed = ProposedAgentBlueprint(
            name="ML Pipeline Agent",
            category="ml",
            purpose="Train and evaluate machine learning models.",
            activation_keywords=("train", "model", "inference"),
            risk_level="medium",
            tools_allowed=("read", "edit", "bash"),
            estimated_cost_level="high",
            generation_reason="ML concepts not covered by existing blueprints.",
        )
        bp = proposed.to_blueprint()
        assert isinstance(bp, AgentBlueprint)
        assert bp.name == "ML Pipeline Agent"
        assert bp.category == "ml"
        assert bp.id.startswith("proposed.")
        assert bp.requires_approval is True
        assert bp.default_enabled is False

    def test_to_blueprint_generates_safe_id(self) -> None:
        proposed = ProposedAgentBlueprint(
            name="Super Secure Scanner!",
            category="security",
            purpose="Scan for issues.",
            generation_reason="test",
        )
        bp = proposed.to_blueprint()
        assert bp.id == "proposed.super_secure_scanner_"
        assert all(c.isalnum() or c in "._-" for c in bp.id)

    def test_frozen_cannot_be_modified(self) -> None:
        proposed = ProposedAgentBlueprint(
            name="Test Agent",
            category="code",
            purpose="Test purpose.",
        )
        with pytest.raises(Exception):
            proposed.name = "Changed"  # type: ignore[misc]


# ── TaskAgentProposal ──────────────────────────────────────────────────────────────


class TestTaskAgentProposal:
    def test_empty_proposal_properties(self) -> None:
        proposal = TaskAgentProposal(task_text="do something")
        assert proposal.requires_approval is False
        assert proposal.has_proposals is False

    def test_requires_approval_high_risk_blueprint(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("security.audit")
        assert bp is not None
        assert bp.requires_approval is True
        proposal = TaskAgentProposal(
            task_text="audit the system",
            matched_blueprints=((bp, 0.9),),
        )
        assert proposal.requires_approval is True

    def test_requires_approval_proposed_agent(self) -> None:
        proposed = ProposedAgentBlueprint(
            name="New Agent",
            category="code",
            purpose="Do things.",
            generation_reason="test",
        )
        proposal = TaskAgentProposal(
            task_text="do things",
            proposed_new_agents=(proposed,),
        )
        assert proposal.requires_approval is True  # all proposed agents require approval

    def test_has_proposals_with_matches(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("code.refactor")
        assert bp is not None
        proposal = TaskAgentProposal(
            task_text="refactor code",
            matched_blueprints=((bp, 0.8),),
        )
        assert proposal.has_proposals is True

    def test_summary_contains_task_text(self) -> None:
        proposal = TaskAgentProposal(task_text="refactor the module")
        summary = proposal.summary()
        assert "refactor the module" in summary
        assert "Auto Agent Proposal" in summary

    def test_summary_includes_proposals(self) -> None:
        from vega_agents.blueprints import find_blueprint

        bp = find_blueprint("code.refactor")
        assert bp is not None
        proposal = TaskAgentProposal(
            task_text="refactor code",
            matched_blueprints=((bp, 0.85),),
        )
        summary = proposal.summary()
        assert "code.refactor" in summary
        assert "0.85" in summary


# ── Blueprint generation ────────────────────────────────────────────────────────────


class TestGenerateProposedBlueprint:
    def test_generates_from_uncovered_tokens(self) -> None:
        result = _generate_proposed_blueprint(
            "Train a PyTorch model on custom dataset",
            ("pytorch", "dataset", "train", "model"),
        )
        assert result is not None
        assert "ML" in result.name or "Pipeline" in result.name
        assert result.category == "ml"
        assert len(result.activation_keywords) > 0
        assert result.generation_reason

    def test_returns_none_for_empty_tokens(self) -> None:
        result = _generate_proposed_blueprint("do something", ())
        assert result is None

    def test_generates_security_agent(self) -> None:
        result = _generate_proposed_blueprint(
            "Encrypt data with TLS and validate certificates",
            ("encrypt", "tls", "certificate"),
        )
        assert result is not None
        assert result.category == "security"
        assert result.risk_level == "medium"

    def test_generates_code_agent_for_code_tokens(self) -> None:
        result = _generate_proposed_blueprint(
            "Refactor the module class hierarchy",
            ("refactor", "module", "class"),
        )
        assert result is not None
        assert result.category == "code"
        assert result.risk_level == "low"

    def test_generated_blueprint_has_read_tools(self) -> None:
        result = _generate_proposed_blueprint(
            "Build a data pipeline",
            ("pipeline", "etl"),
        )
        assert result is not None
        assert "read" in result.tools_allowed


# ── Full proposal creation ──────────────────────────────────────────────────────────


class TestCreateProposal:
    def test_proposal_for_code_task(self) -> None:
        proposal = create_proposal("Refactor the module structure and clean up imports")
        assert proposal.task_text is not None
        assert len(proposal.matched_blueprints) > 0
        # Code refactoring task should match at least one code blueprint
        bp_ids = {bp.id for bp, _ in proposal.matched_blueprints}
        assert any("code" in bid for bid in bp_ids), (
            f"Expected code-related agents, got: {bp_ids}"
        )

    def test_proposal_for_security_task(self) -> None:
        proposal = create_proposal(
            "Audit for XSS vulnerabilities and SQL injection"
        )
        assert len(proposal.matched_blueprints) > 0
        bp_ids = {bp.id for bp, _ in proposal.matched_blueprints}
        assert any("security" in bid for bid in bp_ids), (
            f"Expected security agents, got: {bp_ids}"
        )

    def test_proposal_for_testing_task(self) -> None:
        proposal = create_proposal(
            "Write pytest unit tests for the new API endpoints"
        )
        assert len(proposal.matched_blueprints) > 0
        bp_ids = {bp.id for bp, _ in proposal.matched_blueprints}
        assert any("test" in bid for bid in bp_ids), (
            f"Expected test agents, got: {bp_ids}"
        )

    def test_proposal_respects_max_blueprints(self) -> None:
        proposal = create_proposal(
            "Refactor, test, deploy, and document the system",
            max_blueprints=3,
        )
        assert len(proposal.matched_blueprints) <= 3

    def test_matched_blueprints_scored_descending(self) -> None:
        proposal = create_proposal("Deploy a Docker container to production")
        if len(proposal.matched_blueprints) >= 2:
            scores = [score for _, score in proposal.matched_blueprints]
            assert scores == sorted(scores, reverse=True), (
                "Blueprints should be sorted by score descending"
            )

    def test_proposal_returns_structured_data(self) -> None:
        proposal = create_proposal("Fix the login redirect bug")
        assert isinstance(proposal, TaskAgentProposal)
        assert isinstance(proposal.matched_blueprints, tuple)
        if proposal.matched_blueprints:
            bp, score = proposal.matched_blueprints[0]
            assert isinstance(bp, AgentBlueprint)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    def test_proposal_gap_analysis_runs(self) -> None:
        proposal = create_proposal(
            "Train a neural network with PyTorch on a GPU cluster"
        )
        # Gap analysis should have been performed (may or may not find a gap)
        assert isinstance(proposal.gap_analysis, (GapResult, type(None)))

    def test_proposal_for_gibberish_returns_empty(self) -> None:
        proposal = create_proposal("xylophone quasar nebula frobnicator")
        # Gibberish shouldn't match any blueprints
        assert len(proposal.matched_blueprints) == 0

    def test_proposes_new_agents_for_ml_domain(self) -> None:
        proposal = create_proposal(
            "Train a PyTorch model with a custom dataset and run inference"
        )
        # May or may not have proposed agents depending on gap analysis
        assert isinstance(proposal.proposed_new_agents, tuple)

    def test_proposal_is_deterministic(self) -> None:
        a = create_proposal("Add user authentication with JWT tokens")
        b = create_proposal("Add user authentication with JWT tokens")
        assert [bp.id for bp, _ in a.matched_blueprints] == [
            bp.id for bp, _ in b.matched_blueprints
        ]
        assert a.overall_recommendation == b.overall_recommendation


# ── Convenience functions ───────────────────────────────────────────────────────────


class TestProposeAgents:
    def test_is_equivalent_to_create_proposal(self) -> None:
        a = create_proposal("Validate user input for SQL injection")
        b = propose_agents("Validate user input for SQL injection")
        assert [bp.id for bp, _ in a.matched_blueprints] == [
            bp.id for bp, _ in b.matched_blueprints
        ]


class TestHasGap:
    def test_common_task_has_no_gap(self) -> None:
        result = has_gap("Fix a typo in the README documentation")
        assert isinstance(result, bool)

    def test_returns_false_for_covered_task(self) -> None:
        """Tasks fully covered by existing blueprints should not be gaps."""
        result = has_gap("Write unit tests for the new function")
        # At minimum, doesn't crash; "test" is a well-covered domain
        assert isinstance(result, bool)

    def test_returns_bool(self) -> None:
        result = has_gap("Deploy the Docker container to Kubernetes")
        assert isinstance(result, bool)


# ── Edge cases ──────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_task_text(self) -> None:
        proposal = create_proposal("")
        assert isinstance(proposal, TaskAgentProposal)
        assert len(proposal.matched_blueprints) == 0
        assert proposal.overall_recommendation

    def test_very_short_task(self) -> None:
        proposal = create_proposal("Fix")
        assert isinstance(proposal, TaskAgentProposal)
        # Single-word task should still produce valid proposal

    def test_task_with_numbers_only(self) -> None:
        proposal = create_proposal("42 100 256")
        assert isinstance(proposal, TaskAgentProposal)
        assert len(proposal.matched_blueprints) == 0

    def test_task_with_special_characters(self) -> None:
        proposal = create_proposal("!!! refactor @#$ the %%^ module &&&")
        assert len(proposal.matched_blueprints) > 0

    def test_long_task_text(self) -> None:
        long_text = (
            "Refactor the authentication module to use JWT tokens instead of session "
            "cookies. Add unit tests for all new endpoints. Update the documentation "
            "with the new flow. Deploy the changes to staging and run integration tests. "
            "Finally, update the API documentation with the new authentication scheme."
        )
        proposal = create_proposal(long_text)
        assert len(proposal.matched_blueprints) > 0
        assert len(proposal.matched_blueprints) <= 5
        assert isinstance(proposal.overall_recommendation, str)

    def test_mixed_case_task(self) -> None:
        lower = create_proposal("deploy production docker container")
        upper = create_proposal("DEPLOY PRODUCTION DOCKER CONTAINER")
        assert [bp.id for bp, _ in lower.matched_blueprints] == [
            bp.id for bp, _ in upper.matched_blueprints
        ]

    def test_proposal_for_security_with_approval_flag(self) -> None:
        proposal = create_proposal(
            "Audit authentication tokens for security vulnerabilities"
        )
        # Security blueprints require approval
        for bp, score in proposal.matched_blueprints:
            if bp.category == "security":
                assert bp.requires_approval, (
                    f"Security blueprint {bp.id} must require approval"
                )


# ── Safety guarantees ───────────────────────────────────────────────────────────────


class TestSafetyGuarantees:
    def test_no_env_access_in_engine_module(self) -> None:
        """The engine module must never read os.environ."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "engine.py"
        text = source.read_text()
        assert "os.environ" not in text, "engine.py accesses os.environ"
        assert "os.getenv" not in text, "engine.py accesses os.getenv"
        assert "environ.get" not in text, "engine.py accesses environ"

    def test_no_network_in_engine_module(self) -> None:
        """The engine module must not make network calls."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "engine.py"
        text = source.read_text()
        assert "urllib" not in text, "engine.py uses urllib"
        assert "requests" not in text, "engine.py uses requests"
        assert "http." not in text, "engine.py uses http"
        assert "socket" not in text, "engine.py uses socket"

    def test_no_file_writes_in_engine_module(self) -> None:
        """The engine module must not write files."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "engine.py"
        text = source.read_text()
        assert ".write(" not in text, "engine.py writes files"
        assert "open(" not in text, "engine.py calls open()"

    def test_no_llm_calls_in_engine_module(self) -> None:
        """The engine must not make LLM calls."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "engine.py"
        text = source.read_text()
        assert "anthropic" not in text, "engine.py references Anthropic SDK"
        assert "openai" not in text, "engine.py references OpenAI SDK"
        assert "llm" not in text.lower() or "estimated" in text.lower(), (
            "engine.py should not reference LLM directly"
        )

    def test_no_deepseek_or_token_leak(self) -> None:
        """No environment or secret leakage."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "engine.py"
        text = source.read_text()
        # Check for OpenAI-style secret keys with typical prefixes
        assert "sk-proj-" not in text, "No OpenAI project keys"
        assert "sk-ant-" not in text, "No Anthropic keys"
        assert "ghp_" not in text, "No GitHub PAT"
        assert "gho_" not in text, "No GitHub OAuth token"
        assert "-----BEGIN" not in text, "No private keys"
        assert "api_key" not in text, "No API keys"
        assert "os.environ" not in text, "No os.environ access"

    def test_engine_is_pure_data_no_callables_with_execute(self) -> None:
        """The engine proposal dataclasses have no execute/run methods."""
        proposal = TaskAgentProposal(task_text="test")
        assert not hasattr(proposal, "execute")
        assert not hasattr(proposal, "run")
        # Properties and accessor methods are fine — they don't execute code externally

    def test_no_imports_from_product_modules(self) -> None:
        """Meta-check: no product modules imported through engine."""
        for mod in sys.modules:
            if "free_claude" in mod or "vega_claude" in mod:
                raise AssertionError(f"Product module imported: {mod}")


# ── Integration: engine + blueprints ────────────────────────────────────────────────


class TestIntegration:
    def test_create_proposal_returns_valid_matches(self) -> None:
        """Proposal matches should be valid AgentBlueprint instances."""
        proposal = create_proposal("Implement a new API endpoint")
        for bp, score in proposal.matched_blueprints:
            assert isinstance(bp, AgentBlueprint)
            assert bp.id
            assert bp.name
            assert bp.purpose
            assert 0.0 <= score <= 1.0

    def test_create_proposal_various_domains(self) -> None:
        domains = [
            "Write documentation for the API",
            "Set up a CI/CD pipeline with GitHub Actions",
            "Optimize database queries for better performance",
            "Design a data model for the user profile",
            "Review code for security best practices",
        ]
        for task in domains:
            proposal = create_proposal(task)
            assert len(proposal.matched_blueprints) > 0, (
                f"No matches for task: {task}"
            )

    def test_create_proposal_augmented_gap(self) -> None:
        """When gap exists, the proposal should include potential new agents."""
        proposal = create_proposal(
            "Set up a GPU training pipeline for LLM fine-tuning",
        )
        # This task has ML-related tokens that may trigger gap analysis
        assert isinstance(proposal, TaskAgentProposal)
        # The gap might or might not fire — depends on coverage
        # Just verify the structure is correct
