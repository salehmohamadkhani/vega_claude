"""Tests for the Vega Agent Blueprint Catalog.

Verifies:
- catalog size (>=120)
- unique IDs
- required categories
- search behavior (security, research, devops)
- approval gating for high-risk agents
- no execution, no env access, no secrets
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from vega_agents.blueprints import (
    AgentBlueprint,
    find_blueprint,
    get_agent_blueprint_catalog,
    get_blueprint_count,
    get_categories,
    list_blueprints,
    propose_blueprints_for_task,
    search_blueprints,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def catalog() -> list[AgentBlueprint]:
    return get_agent_blueprint_catalog()


# ─── Catalog structure ──────────────────────────────────────────────────────────────


class TestCatalogSize:
    def test_catalog_has_at_least_120_blueprints(self, catalog: list[AgentBlueprint]) -> None:
        assert len(catalog) >= 120, f"Expected >=120 blueprints, got {len(catalog)}"

    def test_all_ids_are_unique(self, catalog: list[AgentBlueprint]) -> None:
        ids = [bp.id for bp in catalog]
        duplicates = {bid for bid in ids if ids.count(bid) > 1}
        assert not duplicates, f"Duplicate blueprint IDs: {duplicates}"

    def test_all_ids_match_pattern(self, catalog: list[AgentBlueprint]) -> None:
        pattern = re.compile(r"^[a-z][a-z0-9_.]*$")
        for bp in catalog:
            assert pattern.match(bp.id), (
                f"Blueprint ID '{bp.id}' does not match expected pattern"
            )

    def test_all_names_are_non_empty(self, catalog: list[AgentBlueprint]) -> None:
        for bp in catalog:
            assert bp.name.strip(), f"Blueprint {bp.id} has empty name"

    def test_all_purposes_are_non_empty(self, catalog: list[AgentBlueprint]) -> None:
        for bp in catalog:
            assert bp.purpose.strip(), f"Blueprint {bp.id} has empty purpose"


class TestCategories:
    REQUIRED_CATEGORIES = {
        "code", "test", "security", "devops", "research",
        "product", "docs", "data", "ux", "business",
        "seo", "qa", "architecture",
    }

    def test_required_categories_exist(self) -> None:
        found = set(get_categories())
        missing = self.REQUIRED_CATEGORIES - found
        assert not missing, f"Required categories missing: {missing}"

    def test_get_categories_returns_sorted(self) -> None:
        cats = get_categories()
        assert cats == sorted(cats), "Categories should be sorted alphabetically"

    def test_list_blueprints_filters_by_category(self, catalog: list[AgentBlueprint]) -> None:
        for cat in self.REQUIRED_CATEGORIES:
            filtered = list_blueprints(category=cat)
            assert len(filtered) >= 5, (
                f"Category '{cat}' has only {len(filtered)} blueprints (need >=5)"
            )
            for bp in filtered:
                assert bp.category == cat, (
                    f"Blueprint {bp.id} has category '{bp.category}', expected '{cat}'"
                )

    def test_list_blueprints_no_filter_returns_all(self, catalog: list[AgentBlueprint]) -> None:
        all_bps = list_blueprints(category=None)
        assert len(all_bps) == len(catalog)

    def test_get_blueprint_count_matches_catalog_length(self, catalog: list[AgentBlueprint]) -> None:
        assert get_blueprint_count() == len(catalog)


# ─── Search behavior ────────────────────────────────────────────────────────────────


class TestSearchBlueprints:
    def test_search_finds_security_agents_for_auth_task(self) -> None:
        results = search_blueprints("Review authentication and authorization tokens")
        ids = {bp.id for bp in results}
        assert "security.auth" in ids, "Should find auth reviewer for auth task"
        assert "security.secrets_scan" in ids, "Should find secrets scanner for token task"

    def test_search_finds_security_agents_for_secret_task(self) -> None:
        results = search_blueprints("Scan for hardcoded API keys and secrets")
        ids = {bp.id for bp in results}
        assert "security.secrets_scan" in ids, "Should find secrets scanner"

    def test_search_finds_research_agents_for_research_task(self) -> None:
        results = search_blueprints("Research github repos for reference implementations")
        ids = {bp.id for bp in results}
        # research.github and research.pattern are the most relevant
        assert any("research" in bp.id for bp in results), (
            "Should find research agents for research task"
        )

    def test_search_finds_devops_agents_for_deploy_task(self) -> None:
        results = search_blueprints("Deploy the server to production using systemd on port 8080")
        ids = {bp.id for bp in results}
        assert any("devops" in bp.id for bp in results), (
            "Should find devops agents for deploy/server/port task"
        )

    def test_search_finds_devops_for_server_setup(self) -> None:
        results = search_blueprints("Configure systemd service and server setup")
        ids = {bp.id for bp in results}
        assert "devops.server" in ids, "Should find server config agent"

    def test_search_respects_max_results(self) -> None:
        results = search_blueprints("code refactoring", max_results=3)
        assert len(results) <= 3

    def test_search_returns_empty_for_gibberish(self) -> None:
        results = search_blueprints("xyzzytron megablaster flurbo")
        assert len(results) == 0

    def test_search_case_insensitive(self) -> None:
        lower = search_blueprints("deploy production server")
        upper = search_blueprints("DEPLOY PRODUCTION SERVER")
        # Same results regardless of case
        lower_ids = {bp.id for bp in lower}
        upper_ids = {bp.id for bp in upper}
        assert lower_ids == upper_ids, "Search should be case-insensitive"

    def test_search_is_deterministic(self) -> None:
        a = search_blueprints("database migration and schema changes")
        b = search_blueprints("database migration and schema changes")
        assert [bp.id for bp in a] == [bp.id for bp in b], "Search should be deterministic"


# ─── Proposal behavior ──────────────────────────────────────────────────────────────


class TestProposeBlueprints:
    def test_propose_returns_only_proposals_no_execution(self) -> None:
        results = propose_blueprints_for_task("Add login with OAuth", max_results=5)
        assert isinstance(results, list)
        assert all(isinstance(r, AgentBlueprint) for r in results)

    def test_propose_respects_max_results(self) -> None:
        results = propose_blueprints_for_task("code formatting and linting", max_results=3)
        assert len(results) <= 3

    def test_propose_high_risk_requires_approval(self) -> None:
        """High-risk agents returned from propose must have requires_approval=True."""
        results = propose_blueprints_for_task(
            "Deploy to production with secrets management",
            max_results=10,
        )
        for bp in results:
            if bp.risk_level in ("high", "critical"):
                assert bp.requires_approval, (
                    f"High-risk blueprint {bp.id} must require approval"
                )

    def test_propose_returns_empty_for_gibberish(self) -> None:
        results = propose_blueprints_for_task("xylophone tsunami fractal")
        assert len(results) == 0


# ─── Find blueprint ─────────────────────────────────────────────────────────────────


class TestFindBlueprint:
    def test_find_by_exact_id(self, catalog: list[AgentBlueprint]) -> None:
        bp = find_blueprint("security.auth")
        assert bp is not None
        assert bp.id == "security.auth"
        assert bp.category == "security"

    def test_find_returns_none_for_missing_id(self) -> None:
        assert find_blueprint("nonexistent.agent") is None

    def test_find_returns_none_for_empty_string(self) -> None:
        assert find_blueprint("") is None


# ─── Risk and approval gating ───────────────────────────────────────────────────────


class TestRiskAndApproval:
    def test_high_risk_agents_require_approval(self, catalog: list[AgentBlueprint]) -> None:
        """Every high or critical risk blueprint must have requires_approval=True."""
        high_risk = [bp for bp in catalog if bp.risk_level in ("high", "critical")]
        assert high_risk, "Expected at least some high/critical risk agents"
        for bp in high_risk:
            assert bp.requires_approval, (
                f"Blueprint {bp.id} is {bp.risk_level} risk but not approval-gated"
            )

    def test_low_risk_agents_do_not_require_approval(self, catalog: list[AgentBlueprint]) -> None:
        """Low risk blueprints should not require approval by default."""
        for bp in catalog:
            if bp.risk_level == "low":
                assert not bp.requires_approval, (
                    f"Blueprint {bp.id} is low risk but requires approval"
                )

    def test_security_category_agents_require_approval(self, catalog: list[AgentBlueprint]) -> None:
        """All agents in the security category should require approval."""
        security_agents = [bp for bp in catalog if bp.category == "security"]
        for bp in security_agents:
            assert bp.requires_approval, (
                f"Security blueprint {bp.id} should require approval"
            )

    def test_devops_high_risk_agents_require_approval(self, catalog: list[AgentBlueprint]) -> None:
        """High-risk devops agents require approval."""
        for bp in catalog:
            if bp.category == "devops" and bp.risk_level in ("high", "critical"):
                assert bp.requires_approval, (
                    f"Devops high-risk blueprint {bp.id} should require approval"
                )


# ─── Safety guarantees: no execution, no env, no secrets ────────────────────────────


class TestSafetyGuarantees:
    def test_no_blueprint_executes_anything(self) -> None:
        """Blueprints are pure data — no callables, no run methods, no execute."""
        catalog = get_agent_blueprint_catalog()
        for bp in catalog:
            assert not hasattr(bp, "execute"), f"{bp.id} has execute method"
            assert not hasattr(bp, "run"), f"{bp.id} has run method"
            assert not hasattr(bp, "__call__"), f"{bp.id} is callable"
            # The blueprint is a frozen dataclass with only expected fields
            assert isinstance(bp, AgentBlueprint)

    def test_no_env_access_in_blueprint_module(self) -> None:
        """The blueprints module must never read os.environ."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "blueprints.py"
        text = source.read_text()
        assert "os.environ" not in text, "blueprints.py accesses os.environ"
        assert "os.getenv" not in text, "blueprints.py accesses os.getenv"
        assert "environ.get" not in text, "blueprints.py accesses environ"

    def test_no_network_in_blueprint_module(self) -> None:
        """The blueprints module must not make network calls.

        web_search and web_fetch are legitimate tool ALLOW-lists in the
        blueprint data (they describe what tools a blueprint COULD use),
        not actual invocations — so they are excluded from this check.
        """
        source = Path(__file__).parent.parent.parent / "vega_agents" / "blueprints.py"
        text = source.read_text()
        assert "urllib" not in text, "blueprints.py uses urllib"
        assert "requests" not in text, "blueprints.py uses requests"
        assert "http." not in text, "blueprints.py uses http"
        assert "socket" not in text, "blueprints.py uses socket"
        assert "curl" not in text, "blueprints.py uses curl"

    def test_no_file_writes_in_blueprint_module(self) -> None:
        """The blueprints module must not write files."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "blueprints.py"
        text = source.read_text()
        assert ".write(" not in text, "blueprints.py writes files via .write()"
        assert "open(" not in text, "blueprints.py calls open()"

    def test_no_secrets_in_blueprint_module(self) -> None:
        """The blueprints module must not contain secrets or credentials."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "blueprints.py"
        text = source.read_text()
        assert "sk-" not in text, "blueprints.py contains OpenAI-style secret key"
        assert "ghp_" not in text, "blueprints.py contains GitHub PAT"
        assert "gho_" not in text, "blueprints.py contains GitHub OAuth token"
        assert "-----BEGIN" not in text, "blueprints.py contains private key"

    def test_no_llm_calls_in_blueprint_module(self) -> None:
        """The blueprints module must not make LLM calls."""
        source = Path(__file__).parent.parent.parent / "vega_agents" / "blueprints.py"
        text = source.read_text()
        assert "anthropic" not in text, "blueprints.py references Anthropic SDK"
        assert "openai" not in text, "blueprints.py references OpenAI SDK"


# ─── Tools allowed ──────────────────────────────────────────────────────────────────


class TestToolsAllowed:
    def test_all_tools_allowed_are_readonly_or_safe(self, catalog: list[AgentBlueprint]) -> None:
        """Verify tools_allowed fields contain only known safe tools."""
        known_tools = {
            "read", "edit", "glob", "grep", "bash", "web_search", "web_fetch",
        }
        for bp in catalog:
            for tool in bp.tools_allowed:
                assert tool in known_tools, (
                    f"Blueprint {bp.id} has unknown tool '{tool}'"
                )


# ─── Module-level invariants ────────────────────────────────────────────────────────


class TestModuleInvariants:
    def test_get_agent_blueprint_catalog_returns_defensive_copy(self) -> None:
        a = get_agent_blueprint_catalog()
        b = get_agent_blueprint_catalog()
        # Same content, different list objects
        assert a is not b, "Should return a new list each call"
        assert [bp.id for bp in a] == [bp.id for bp in b]

    def test_catalog_is_not_empty(self, catalog: list[AgentBlueprint]) -> None:
        assert len(catalog) > 0
