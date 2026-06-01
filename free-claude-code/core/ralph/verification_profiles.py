"""Goal-scoped verification profiles for the Ralph Runtime.

Each profile defines what verification commands and KPIs are appropriate
for a given type of goal.  This prevents irrelevant verification (e.g.
``pytest tests/core/ralph``) from blocking throwaway app-building tasks.

Profiles are deterministic — no LLM calls, no provider calls.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Profile types
# ---------------------------------------------------------------------------


class VerificationProfile(enum.Enum):
    """The verification profile selected for a goal.

    Each profile controls what verification commands and KPIs are assigned
    to generated tasks.
    """

    RALPH_RUNTIME = "ralph-runtime"
    """Default profile for changes to the Ralph Runtime or VegaClaw core code.
    Includes :command:`pytest tests/core/ralph`, ruff, ty, etc."""

    THROWAWAY_APP = "throwaway-app"
    """Profile for self-contained app-building goals (calculator, landing page,
    browser app, HTML/CSS/JS).  Verification is workspace-local and does
    NOT reference the VegaClaw source tree."""

    DOCUMENTATION = "documentation"
    """Profile for documentation-only goals.  No command verification."""

    GENERIC = "generic"
    """Fallback profile for goals that don't match any specific category.
    Includes basic syntax and lint checks but no VegaClaw-specific tests."""


# ---------------------------------------------------------------------------
# Profile selection result
# ---------------------------------------------------------------------------


@dataclass
class ProfileDecision:
    """The result of selecting a verification profile for a goal."""

    profile: VerificationProfile
    reason: str
    recommended_commands: dict[str, list[str]] = field(default_factory=dict)
    """Recommended verification commands per task role (architect, doer, verifier)."""

    recommended_kpis: dict[str, list[str]] = field(default_factory=dict)
    """Recommended KPI descriptions per task role."""


# ---------------------------------------------------------------------------
# Heuristic goal classifiers
# ---------------------------------------------------------------------------

_THROWAWAY_WORDS: set[str] = {
    "calculator",
    "browser",
    "html",
    "css",
    "javascript",
    "js",
    "frontend",
    "front-end",
    "front_end",
    "throwaway",
    "standalone",
    "static",
}

_THROWAWAY_PHRASES: set[str] = {
    "browser app",
    "landing page",
    "standalone app",
    "single page",
    "static site",
    "app files",
}

_RALPH_RUNTIME_KEYWORDS: set[str] = {
    "ralph",
    "runtime",
    "core",
    "cli",
    "tests",
    "test",
    "provider",
    "routing",
    "model",
    "api",
    "proxy",
    "verification",
    "kpi",
    "arbiter",
    "planner",
    "executor",
}

_DOCUMENTATION_KEYWORDS: set[str] = {
    "documentation",
    "docs",
    "readme",
    "report",
    "changelog",
}

_APP_FILE_EXTENSIONS: set[str] = {".html", ".js", ".css", ".mjs"}


def _collect_goal_text(
    title: str, description: str, constraints: list[str], kpis: list[str]
) -> str:
    """Concatenate all goal text into a single lowercased string for keyword matching."""
    return f"{title} {description} {' '.join(constraints)} {' '.join(kpis)}".lower()


def _is_throwaway_app(text: str) -> bool:
    """Return True if the goal text describes a throwaway app."""
    # Word-level matching
    words = set(re.split(r"[^a-z0-9]", text))
    if words & _THROWAWAY_WORDS:
        return True
    # Phrase-level matching
    return any(phrase in text for phrase in _THROWAWAY_PHRASES)


def _is_ralph_runtime(text: str) -> bool:
    """Return True if the goal text describes Ralph Runtime / VegaClaw core work."""
    words = set(re.split(r"[^a-z0-9]", text))
    return bool(words & _RALPH_RUNTIME_KEYWORDS)


def _is_documentation(text: str) -> bool:
    """Return True if the goal text describes documentation work."""
    words = set(re.split(r"[^a-z0-9]", text))
    return bool(words & _DOCUMENTATION_KEYWORDS)


def _has_app_file_pattern(text: str) -> bool:
    """Return True if the goal text mentions specific app file types."""
    return any(ext in text for ext in _APP_FILE_EXTENSIONS)


# ---------------------------------------------------------------------------
# Profile selection
# ---------------------------------------------------------------------------


def select_profile_for_goal(
    title: str,
    description: str = "",
    constraints: list[str] | None = None,
    kpis: list[str] | None = None,
) -> ProfileDecision:
    """Select the appropriate verification profile for a goal.

    Priority order:
    1. Throwaway app keywords match → THROWAWAY_APP
    2. Documentation keywords match → DOCUMENTATION
    3. Ralph Runtime keywords match → RALPH_RUNTIME
    4. Default → GENERIC

    The function is fully deterministic — no LLM calls, no provider calls.
    """
    text = _collect_goal_text(title, description, constraints or [], kpis or [])

    # Throwaway app detection (highest priority)
    if _is_throwaway_app(text) or _has_app_file_pattern(text):
        return _build_throwaway_app_decision(
            reason="Goal matches throwaway app keywords: detected in goal text"
        )

    # Documentation detection
    if _is_documentation(text):
        return ProfileDecision(
            profile=VerificationProfile.DOCUMENTATION,
            reason="Goal matches documentation keywords.",
            recommended_commands={
                "architect": [],
                "doer": [],
                "verifier": [],
            },
            recommended_kpis={
                "architect": ["Documentation structure is outlined."],
                "doer": ["Documentation files are created or updated."],
                "verifier": ["Documentation is reviewed and accurate."],
            },
        )

    # Ralph Runtime detection
    if _is_ralph_runtime(text):
        return ProfileDecision(
            profile=VerificationProfile.RALPH_RUNTIME,
            reason="Goal matches Ralph Runtime/core keywords.",
            recommended_commands={
                "architect": ["uv run pytest tests/core/ralph -q"],
                "doer": [
                    "uv run ruff check core/ralph",
                    "uv run pytest tests/core/ralph -q",
                ],
                "verifier": [
                    "uv run pytest tests/core/ralph -q",
                    "uv run ruff check core/ralph tests/core/ralph",
                    "uv run ty check core/ralph",
                ],
            },
            recommended_kpis={
                "architect": ["Architecture document covers all affected modules."],
                "doer": [
                    "Implementation passes ruff linting.",
                    "All pytest tests pass.",
                ],
                "verifier": [
                    "All ruff checks pass.",
                    "All ty (strict type) checks pass.",
                    "All pytest tests pass.",
                ],
            },
        )

    # Generic fallback
    return ProfileDecision(
        profile=VerificationProfile.GENERIC,
        reason="Goal did not match any specific profile; using GENERIC fallback.",
        recommended_commands={
            "architect": [],
            "doer": [],
            "verifier": [],
        },
        recommended_kpis={
            "architect": ["Architecture document covers all affected modules."],
            "doer": ["Implementation is complete and functional."],
            "verifier": ["All acceptance criteria are met."],
        },
    )


def _build_throwaway_app_decision(reason: str) -> ProfileDecision:
    """Build a THROWAWAY_APP profile decision with workspace-local verification."""
    return ProfileDecision(
        profile=VerificationProfile.THROWAWAY_APP,
        reason=reason,
        recommended_commands={
            # Architect: no blocking verification needed
            "architect": [],
            # Doer/implementer: check files exist and JS syntax
            "doer": [
                "test -f index.html || test -f app.html || exit 1",
            ],
            # Verifier: full workspace-local checks
            "verifier": [
                'find . -maxdepth 4 -type f \\( -name "*.html" -o -name "*.js" -o -name "*.css" \\) | head -20',
            ],
        },
        recommended_kpis={
            "architect": [
                "Architecture is documented for the throwaway app.",
            ],
            "doer": [
                "Required app files exist (HTML, CSS, JS).",
                "JS files pass Node syntax check if available.",
            ],
            "verifier": [
                "All generated files stay inside the workspace.",
                "No VegaClaw source tree modifications.",
                "App files are present and valid.",
            ],
        },
    )


def make_profile_decision(
    profile: VerificationProfile, reason: str = ""
) -> ProfileDecision:
    """Create a ProfileDecision for a given profile enum value.

    This is used when the profile is explicitly specified (e.g. via CLI)
    rather than auto-detected from goal text.
    """
    if profile == VerificationProfile.THROWAWAY_APP:
        return _build_throwaway_app_decision(
            reason or "Explicitly specified throwaway-app profile."
        )
    if profile == VerificationProfile.DOCUMENTATION:
        return ProfileDecision(
            profile=VerificationProfile.DOCUMENTATION,
            reason=reason or "Explicitly specified documentation profile.",
            recommended_commands={
                "architect": [],
                "doer": [],
                "verifier": [],
            },
            recommended_kpis={
                "architect": ["Documentation structure is outlined."],
                "doer": ["Documentation files are created or updated."],
                "verifier": ["Documentation is reviewed and accurate."],
            },
        )
    if profile == VerificationProfile.RALPH_RUNTIME:
        return ProfileDecision(
            profile=VerificationProfile.RALPH_RUNTIME,
            reason=reason or "Explicitly specified ralph-runtime profile.",
            recommended_commands={
                "architect": ["uv run pytest tests/core/ralph -q"],
                "doer": [
                    "uv run ruff check core/ralph",
                    "uv run pytest tests/core/ralph -q",
                ],
                "verifier": [
                    "uv run pytest tests/core/ralph -q",
                    "uv run ruff check core/ralph tests/core/ralph",
                    "uv run ty check core/ralph",
                ],
            },
            recommended_kpis={
                "architect": ["Architecture document covers all affected modules."],
                "doer": [
                    "Implementation passes ruff linting.",
                    "All pytest tests pass.",
                ],
                "verifier": [
                    "All ruff checks pass.",
                    "All ty (strict type) checks pass.",
                    "All pytest tests pass.",
                ],
            },
        )
    # GENERIC fallback
    return ProfileDecision(
        profile=VerificationProfile.GENERIC,
        reason=reason or "Explicitly specified generic profile.",
        recommended_commands={
            "architect": [],
            "doer": [],
            "verifier": [],
        },
        recommended_kpis={
            "architect": ["Architecture document covers all affected modules."],
            "doer": ["Implementation is complete and functional."],
            "verifier": ["All acceptance criteria are met."],
        },
    )


def profile_from_string(name: str) -> VerificationProfile:
    """Convert a string to a VerificationProfile, raising ValueError on invalid input."""
    normalized = name.lower().replace("-", "_").replace(" ", "_")
    for profile in VerificationProfile:
        if profile.value == name.lower() or profile.name.lower() == normalized:
            return profile
    valid = ", ".join(p.value for p in VerificationProfile)
    raise ValueError(f"Unknown verification profile: {name!r}. Valid profiles: {valid}")
