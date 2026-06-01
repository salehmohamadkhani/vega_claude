"""Auto Agent Proposal Engine — maps task text to agent blueprints and proposes new agents.

This is a PURE PROPOSAL engine. It does NOT execute anything, make network
calls, read environment variables, or invoke LLMs. All analysis is done via
keyword/token matching and rule-based gap detection.

Output:
  TaskAgentProposal — a structured recommendation containing:
    - matched existing blueprints (with relevance scores)
    - gap analysis (what the task covers that no blueprint does)
    - proposed new agent blueprints (to fill gaps)
    - overall recommendation string
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from .blueprints import (
    AgentBlueprint,
    get_agent_blueprint_catalog,
    search_blueprints,
)


# ── Proposal dataclasses ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProposedAgentBlueprint:
    """A proposed new agent blueprint generated from gap analysis.

    Unlike AgentBlueprint (which is a pre-defined catalog entry), this is a
    synthetic proposal — it does NOT exist in the catalog and must be reviewed
    and potentially registered before execution.
    """

    name: str
    category: str
    purpose: str
    activation_keywords: tuple[str, ...] = ()
    risk_level: str = "low"
    tools_allowed: tuple[str, ...] = ("read",)
    estimated_cost_level: str = "low"
    generation_reason: str = ""

    def to_blueprint(self) -> AgentBlueprint:
        """Convert this proposal into a full AgentBlueprint for review.

        Returns a blueprint with a synthetic ``proposed.``-prefixed id so
        callers can distinguish proposed agents from registered ones.
        """
        safe_id = re.sub(r"[^a-z0-9_]", "_", self.name.lower().replace(" ", "_"))
        return AgentBlueprint(
            id=f"proposed.{safe_id}",
            name=self.name,
            category=self.category,
            purpose=self.purpose,
            activation_keywords=self.activation_keywords,
            risk_level=self.risk_level,
            default_enabled=False,
            requires_approval=True,
            estimated_cost_level=self.estimated_cost_level,
            tools_allowed=self.tools_allowed,
        )


@dataclass(frozen=True)
class GapResult:
    """Result of gap analysis between task text and the existing blueprint catalog.

    A gap exists when the task mentions concepts (after stop-word removal)
    that are not covered by any existing blueprint's keywords or purpose.
    """

    has_gap: bool
    gap_reason: str = ""
    uncovered_tokens: tuple[str, ...] = ()
    coverage_ratio: float = 1.0  # 1.0 = fully covered, 0.0 = nothing covered
    suggested_new_blueprint: ProposedAgentBlueprint | None = None


@dataclass(frozen=True)
class TaskAgentProposal:
    """Complete proposal from the Auto Agent Proposal Engine.

    Contains the matched existing blueprints, gap analysis, proposed new
    agents, and an overall recommendation. This is a PURE DATA object —
    no execution, no side effects, no LLM calls.
    """

    task_text: str
    matched_blueprints: tuple[tuple[AgentBlueprint, float], ...] = ()
    gap_analysis: GapResult | None = None
    proposed_new_agents: tuple[ProposedAgentBlueprint, ...] = ()
    overall_recommendation: str = ""

    @property
    def requires_approval(self) -> bool:
        """Return True if any matched blueprint or proposed agent needs approval."""
        for bp, _ in self.matched_blueprints:
            if bp.requires_approval:
                return True
        for agent in self.proposed_new_agents:
            if agent.to_blueprint().requires_approval:
                return True
        return False

    @property
    def has_proposals(self) -> bool:
        """Return True if there are any matched blueprints or proposed agents."""
        return bool(self.matched_blueprints) or bool(self.proposed_new_agents)

    def summary(self) -> str:
        """Return a concise human-readable summary of this proposal."""
        lines: list[str] = ["=== Auto Agent Proposal ===", f"Task: {self.task_text}"]

        if self.matched_blueprints:
            lines.append(f"\nMatched blueprints ({len(self.matched_blueprints)}):")
            for bp, score in self.matched_blueprints:
                lines.append(f"  - {bp.id} (score={score:.2f}, risk={bp.risk_level})")

        if self.gap_analysis and self.gap_analysis.has_gap:
            lines.append(f"\nGap detected: {self.gap_analysis.gap_reason}")
            if self.gap_analysis.uncovered_tokens:
                tokens = ", ".join(self.gap_analysis.uncovered_tokens)
                lines.append(f"  Uncovered tokens: [{tokens}]")
            lines.append(f"  Coverage ratio: {self.gap_analysis.coverage_ratio:.2f}")
            if self.gap_analysis.suggested_new_blueprint:
                nb = self.gap_analysis.suggested_new_blueprint
                lines.append(f"  Suggested new agent: {nb.name} ({nb.category})")
                lines.append(f"    Purpose: {nb.purpose}")

        if self.proposed_new_agents:
            lines.append(f"\nProposed new agents ({len(self.proposed_new_agents)}):")
            for pa in self.proposed_new_agents:
                lines.append(f"  - {pa.name}")
                lines.append(f"    Reason: {pa.generation_reason}")

        if self.overall_recommendation:
            lines.append(f"\nRecommendation: {self.overall_recommendation}")

        return "\n".join(lines)


# ── Stop words and category heuristics ──────────────────────────────────────────────────

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "although",
    "this", "that", "these", "those", "it", "its", "i", "me", "my",
    "we", "us", "our", "you", "your", "he", "she", "they", "them",
    "their", "what", "which", "who", "whom", "please", "add", "new",
    "make", "implement", "change", "update", "fix", "remove", "set",
    "get", "put", "run", "use", "need", "want", "like", "work",
})

# Domain signal words: map uncovered tokens → likely category
_CATEGORY_SIGNALS: dict[str, set[str]] = {
    "code": {
        "refactor", "rename", "extract", "inline", "simplify", "module",
        "class", "function", "method", "variable", "constant", "enum",
        "generic", "overload", "decorator", "context", "manager",
    },
    "test": {
        "mock", "stub", "fixture", "parametrize", "assert", "coverage",
        "hypothesis", "regression", "smoke", "snapshot", "golden",
    },
    "security": {
        "encrypt", "decrypt", "hash", "cipher", "certificate", "tls",
        "ssl", "xss", "csrf", "sqli", "injection", "sanitize", "cors",
        "oidc", "saml", "mfa", "2fa", "rate", "limit", "throttle",
    },
    "data": {
        "migration", "etl", "pipeline", "schema", "query", "index",
        "normalize", "denormalize", "aggregate", "partition", "shard",
        "backfill", "deduplicate", "warehouse", "lake", "parquet",
    },
    "ml": {
        "model", "train", "inference", "feature", "embedding", "vector",
        "tensor", "pytorch", "tensorflow", "onnx", "quantize", "prune",
        "accuracy", "precision", "recall", "f1", "auc", "loss",
        "dataset", "label", "annotation", "augment", "batch",
    },
    "devops": {
        "deploy", "release", "rollback", "canary", "blue", "green",
        "terraform", "ansible", "puppet", "chef", "helm", "kustomize",
        "istio", "envoy", "sidecar", "service", "mesh",
    },
    "docs": {
        "readme", "api", "reference", "adr", "decision", "record",
        "tutorial", "walkthrough", "guide", "faq", "glossary",
    },
    "qa": {
        "manual", "exploratory", "uat", "acceptance", "compatibility",
        "penetration", "load", "stress", "soak",
    },
    "business": {
        "roi", "tco", "pricing", "tier", "subscription", "monetize",
        "forecast", "projection", "budget", "cost", "revenue",
    },
    "ux": {
        "responsive", "accessibility", "a11y", "i18n", "l10n",
        "wireframe", "prototype", "mockup", "onboarding",
    },
}

# Category-level default tool allowances
_CATEGORY_TOOLS: dict[str, tuple[str, ...]] = {
    "code": ("read", "edit", "glob", "grep"),
    "test": ("read", "edit", "bash"),
    "security": ("read", "grep"),
    "data": ("read", "edit"),
    "ml": ("read", "edit", "bash"),
    "devops": ("read", "bash"),
    "docs": ("read", "edit"),
    "qa": ("read", "edit"),
    "business": ("read", "edit"),
    "research": ("web_search", "web_fetch"),
    "ux": ("read", "edit"),
}

# When category can't be inferred from signals, fall back to a general-purpose profile
_FALLBACK_TOOLS: tuple[str, ...] = ("read", "edit", "bash", "glob", "grep")


# ── Public API ──────────────────────────────────────────────────────────────────────────


def create_proposal(
    task_text: str,
    max_blueprints: int = 5,
) -> TaskAgentProposal:
    """Create a full agent proposal for the given task text.

    Steps:
    1. Search the blueprint catalog for matching blueprints.
    2. Perform gap analysis — identify tokens/domains the catalog doesn't cover.
    3. If gaps exist, generate proposed new agent blueprints.
    4. Produce an overall recommendation string.
    """
    # Step 1: search existing blueprints
    matched = search_blueprints(task_text, max_results=max_blueprints)

    # Also score them so we can report scores
    scored: list[tuple[AgentBlueprint, float]] = []
    for bp in matched:
        score = _compute_blueprint_score(bp, task_text)
        scored.append((bp, score))

    # Step 2: gap analysis
    gap = _analyze_gap(task_text, matched)
    proposed: list[ProposedAgentBlueprint] = []

    if gap and gap.has_gap and gap.uncovered_tokens:
        proposed_bp = _generate_proposed_blueprint(task_text, gap.uncovered_tokens)
        if proposed_bp:
            gap = GapResult(
                has_gap=True,
                gap_reason=gap.gap_reason,
                uncovered_tokens=gap.uncovered_tokens,
                coverage_ratio=gap.coverage_ratio,
                suggested_new_blueprint=proposed_bp,
            )
            proposed.append(proposed_bp)

    # Step 3: overall recommendation
    recommendation = _build_recommendation(scored, gap, proposed)

    return TaskAgentProposal(
        task_text=task_text,
        matched_blueprints=tuple(scored),
        gap_analysis=gap if (gap and gap.has_gap) else None,
        proposed_new_agents=tuple(proposed),
        overall_recommendation=recommendation,
    )


# ── Internal analysis ───────────────────────────────────────────────────────────────────


def _tokenize(text: str) -> set[str]:
    """Extract meaningful tokens from text, removing stop words."""
    raw = set(re.findall(r"[a-z][a-z0-9_]{1,}", text.lower()))
    return raw - _STOP_WORDS


def _compute_blueprint_score(bp: AgentBlueprint, task_text: str) -> float:
    """Compute a normalized relevance score for one blueprint against task text.

    Returns a score in [0.0, 1.0] where 1.0 = perfect match.
    Combines keyword, purpose, and category matching.
    """
    lower = task_text.lower()
    tokens = _tokenize(task_text)
    score = 0.0
    max_score = 0.0

    # Keyword matching (weight 3)
    if bp.activation_keywords:
        kw_matched = sum(1 for kw in bp.activation_keywords if kw in lower)
        kw_score = kw_matched / len(bp.activation_keywords)
        max_score += 3.0
        score += kw_score * 3.0

    # Purpose matching (weight 1)
    purpose_tokens = re.findall(r"[a-z0-9_]+", bp.purpose.lower())
    if purpose_tokens:
        purp_set = set(purpose_tokens) - _STOP_WORDS
        if purp_set:
            purp_matched = len(purp_set & tokens)
            purp_score = purp_matched / len(purp_set)
            max_score += 1.0
            score += purp_score * 1.0

    # Category token overlap (weight 0.5)
    cat_tokens = re.findall(r"[a-z0-9_]+", bp.category.lower())
    cat_set = set(cat_tokens) - _STOP_WORDS
    if cat_set:
        cat_matched = len(cat_set & tokens)
        cat_score = cat_matched / len(cat_set)
        max_score += 0.5
        score += cat_score * 0.5

    if max_score == 0:
        return 0.0
    return round(score / max_score, 4)


def _analyze_gap(
    task_text: str,
    matched: list[AgentBlueprint],
) -> GapResult | None:
    """Analyze whether the task text has gaps vs the full catalog.

    A gap exists when a significant portion (>25%) of meaningful task tokens
    are not covered by any existing blueprint's keywords or purpose text.
    """
    tokens = _tokenize(task_text)
    if not tokens:
        return GapResult(has_gap=False, coverage_ratio=1.0)

    catalog = get_agent_blueprint_catalog()

    # Collect all coverage texts from the catalog
    coverage_text = ""
    token_coverage: dict[str, bool] = {t: False for t in tokens}

    for bp in catalog:
        # Include keywords, purpose, category, and name as coverage signals
        parts = [
            bp.purpose,
            bp.category,
            bp.name,
            *bp.activation_keywords,
        ]
        coverage_text += " " + " ".join(parts).lower()

    # Check each token against the combined coverage
    for token in tokens:
        if token in coverage_text:
            token_coverage[token] = True

    uncovered = {t for t, covered in token_coverage.items() if not covered}

    coverage_ratio = 1.0 - (len(uncovered) / len(tokens))

    if uncovered and coverage_ratio < 0.75:
        uncovered_list = sorted(uncovered)[:10]  # Limit to 10 tokens
        reason = (
            f"Task references concepts not covered by existing blueprints: "
            f"{', '.join(uncovered_list)}. "
            f"Coverage ratio: {coverage_ratio:.0%} of meaningful tokens matched."
        )
        return GapResult(
            has_gap=True,
            gap_reason=reason,
            uncovered_tokens=tuple(sorted(uncovered)),
            coverage_ratio=round(coverage_ratio, 4),
        )

    return GapResult(has_gap=False, coverage_ratio=round(coverage_ratio, 4))


def _infer_category(uncovered_tokens: tuple[str, ...]) -> str:
    """Infer the most likely agent category from uncovered tokens."""
    if not uncovered_tokens:
        return "general"

    best_cat = "general"
    best_score = 0

    for cat, signals in _CATEGORY_SIGNALS.items():
        score = 0
        for token in uncovered_tokens:
            if token in signals:
                score += 1
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat


def _generate_proposed_blueprint(
    task_text: str,
    uncovered_tokens: tuple[str, ...],
) -> ProposedAgentBlueprint | None:
    """Generate a proposed new agent blueprint from uncovered tokens.

    Uses rule-based heuristics — no LLM calls, no network access.
    Returns None if the uncovered tokens are too generic to propose anything.
    """
    if not uncovered_tokens:
        return None

    category = _infer_category(uncovered_tokens)
    tools = _CATEGORY_TOOLS.get(category, _FALLBACK_TOOLS)

    # Generate a descriptive name from uncovered tokens
    # Take the most specific-looking tokens (longer ones, domain-specific terms)
    meaningful = sorted(
        [t for t in uncovered_tokens if len(t) > 3],
        key=lambda t: -len(t),
    )[:4]

    if not meaningful:
        meaningful = list(uncovered_tokens[:3])

    name_parts = meaningful[:3]
    name_suffixes = {
        "code": "Agent",
        "test": "Tester",
        "security": "Scanner",
        "data": "Manager",
        "ml": "Pipeline",
        "devops": "Operator",
        "docs": "Writer",
        "qa": "Checker",
        "business": "Analyzer",
        "research": "Explorer",
        "ux": "Designer",
        "general": "Agent",
    }
    suffix = name_suffixes.get(category, "Agent")
    name = " ".join(p.capitalize() for p in name_parts) + f" {suffix}"

    # Build purpose from the domain
    purpose_text = _generate_purpose(task_text, category, meaningful)

    # Build activation keywords from uncovered tokens
    keywords = tuple(sorted(set(
        t.replace("_", " ") for t in meaningful if len(t) > 2
    )))

    # Risk level based on category
    risk_level = "medium" if category in ("security", "devops", "data", "ml") else "low"

    cost_level = "medium" if category in ("ml", "security", "devops") else "low"

    reason = (
        f"Existing blueprints lack coverage for {category}-related concepts: "
        f"{', '.join(meaningful)}. "
        f"A new '{category}' agent would fill this gap."
    )

    return ProposedAgentBlueprint(
        name=name,
        category=category,
        purpose=purpose_text,
        activation_keywords=keywords,
        risk_level=risk_level,
        tools_allowed=tools,
        estimated_cost_level=cost_level,
        generation_reason=reason,
    )


def _generate_purpose(
    task_text: str,
    category: str,
    meaningful_tokens: list[str],
) -> str:
    """Generate a purpose description for the proposed blueprint."""
    domain_purposes = {
        "code": (
            "Apply code-related changes based on task requirements. "
            "Handles implementation, refactoring, and structural improvements."
        ),
        "test": (
            "Design and write tests for task-specific functionality. "
            "Covers unit, integration, and other test types as needed."
        ),
        "security": (
            "Audit and address security concerns in the codebase. "
            "Reviews authentication, authorization, data protection, and compliance."
        ),
        "data": (
            "Manage data-related operations including schema design, "
            "transformations, migrations, and quality validation."
        ),
        "ml": (
            "Handle machine learning workflows — model development, "
            "training pipelines, inference optimization, and evaluation."
        ),
        "devops": (
            "Manage infrastructure, deployments, and operational workflows. "
            "Handles CI/CD, monitoring, scaling, and configuration."
        ),
        "docs": (
            "Generate and maintain documentation for the project. "
            "Covers READMEs, API references, guides, and decision records."
        ),
        "qa": (
            "Ensure quality through manual and automated testing processes. "
            "Designs test plans, triages issues, and validates compatibility."
        ),
        "business": (
            "Analyze business requirements and produce structured reports. "
            "Handles cost analysis, market research, and strategic planning."
        ),
        "research": (
            "Investigate external sources for patterns, references, "
            "and best practices relevant to the task."
        ),
        "ux": (
            "Improve user experience through accessibility, responsiveness, "
            "and interaction design recommendations."
        ),
        "general": (
            "Execute general-purpose development tasks. "
            "Adapts to the specific requirements of each task."
        ),
    }

    purpose = domain_purposes.get(category, domain_purposes["general"])

    # If we have specific tokens, append a task-specific note
    if meaningful_tokens:
        token_note = ", ".join(meaningful_tokens[:3])
        purpose = purpose.rstrip(".") + f", with focus on: {token_note}."

    return purpose


def _build_recommendation(
    scored: list[tuple[AgentBlueprint, float]],
    gap: GapResult | None,
    proposed: list[ProposedAgentBlueprint],
) -> str:
    """Build the overall recommendation string."""
    parts: list[str] = []

    if not scored and not proposed:
        return (
            "No matching blueprints found and no new agents to propose. "
            "The task may be too vague or require a custom agent definition."
        )

    if scored:
        best = scored[0]
        top_ids = [bp.id for bp, _ in scored[:3]]
        parts.append(
            f"Recommend starting with: {scored[0][0].id} "
            f"(score={best[1]:.2f}). "
            f"Top candidates: {', '.join(top_ids)}."
        )

    if gap and gap.has_gap:
        parts.append(
            f"Gap detected ({gap.coverage_ratio:.0%} coverage). "
            f"Consider reviewing the proposed new agent before proceeding."
        )

    if not proposed and (not gap or not gap.has_gap):
        parts.append("No new agents needed — existing blueprints cover the task.")

    if proposed:
        p_names = ", ".join(p.name for p in proposed)
        parts.append(f"Proposed new agent{'s' if len(proposed) > 1 else ''}: {p_names}.")

    return " ".join(parts)


# ── Convenience aliases ─────────────────────────────────────────────────────────────────


def propose_agents(task_text: str, max_blueprints: int = 5) -> TaskAgentProposal:
    """Convenience alias for ``create_proposal``."""
    return create_proposal(task_text, max_blueprints=max_blueprints)


def has_gap(task_text: str) -> bool:
    """Quick-check whether a task has any blueprint covereage gap.

    Returns True if >25% of meaningful tokens are uncovered.
    No proposal generation — just gap detection.
    """
    matched = search_blueprints(task_text, max_results=3)
    gap = _analyze_gap(task_text, matched)
    return gap is not None and gap.has_gap
