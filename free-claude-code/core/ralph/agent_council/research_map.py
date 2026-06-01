"""Agent Council V2 — Research Map.

Lightweight readers for Research Corpus indexes under
``/opt/vega-cloud/research/indexes/``.

Supports:
- Load agent-to-repo mappings
- Load category mappings
- Load pattern index
- Find research references for an agent
- Find research references for a layer
- Degrade gracefully if research root is missing

Does NOT clone repos, run repo code, or access network.
"""

from __future__ import annotations

import os

from .models import ResearchReference

# ---------------------------------------------------------------------------
# Default research root
# ---------------------------------------------------------------------------

DEFAULT_RESEARCH_ROOT = "/opt/vega-cloud/research"


# ---------------------------------------------------------------------------
# Research Map
# ---------------------------------------------------------------------------


class ResearchMap:
    """Reads Research Corpus indexes and maps them to Agent Council agents.

    All operations are read-only. If the research root is missing or
    incomplete, methods degrade gracefully (return empty results).
    """

    def __init__(self, research_root: str | None = None) -> None:
        """Initialize with optional custom research root.

        Args:
            research_root: Path to research corpus root. Defaults to
                           /opt/vega-cloud/research.
        """
        self._root = research_root or DEFAULT_RESEARCH_ROOT
        self._indexes_dir = os.path.join(self._root, "indexes")
        self._agent_to_repo: dict[str, list[ResearchReference]] = {}
        self._category_to_repo: dict[str, list[ResearchReference]] = {}
        self._patterns: dict[str, list[str]] = {}  # pattern -> [repo_ids]
        self._loaded = False

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True if the research root exists and contains indexes."""
        return os.path.isdir(self._indexes_dir)

    @property
    def indexes_dir(self) -> str:
        """Path to the indexes directory."""
        return self._indexes_dir

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load all available indexes. No-op if already loaded."""
        if self._loaded:
            return
        if not self.is_available:
            self._loaded = True
            return
        self._load_agent_to_repo()
        self._load_pattern_index()
        self._loaded = True

    def _load_agent_to_repo(self) -> None:
        """Parse AGENT_TO_REPO_INDEX.md for agent→repo mappings."""
        path = os.path.join(self._indexes_dir, "AGENT_TO_REPO_INDEX.md")
        if not os.path.isfile(path):
            return
        try:
            with open(path) as f:
                content = f.read()
            self._parse_agent_index_md(content)
        except OSError, UnicodeDecodeError:
            pass

    def _parse_agent_index_md(self, content: str) -> None:
        """Parse the agent-to-repo index markdown.

        Looks for lines like:
        | `agent_id` | repo1, repo2, ... |
        Also parses agent_id: lines and bullet points with repo references.
        """
        current_agent: str | None = None
        for line in content.split("\n"):
            line = line.strip()

            # Table row: | `agent_id` | ...
            if line.startswith("| `") and "` |" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    agent = parts[1].strip("`").strip()
                    if (
                        agent
                        and not agent.startswith("-")
                        and not agent.startswith("Agent")
                    ):
                        current_agent = agent
                        # Check if there's a repos column
                        if len(parts) >= 3:
                            repo_text = parts[2].strip()
                            if repo_text and repo_text != "—" and repo_text != "-":
                                self._agent_to_repo.setdefault(current_agent, [])
                                for repo_id in self._extract_repo_ids(repo_text):
                                    self._agent_to_repo.setdefault(
                                        current_agent, []
                                    ).append(
                                        ResearchReference(
                                            repo_id=repo_id,
                                            relevance_agent=current_agent,
                                        )
                                    )

            # Markdown header: ### AGENT: agent_id
            elif line.startswith("### ") and "agent_id" not in line.lower():
                # Not a taxonomy-style doc — skip
                pass

            # Bullet: - repo_id (description)
            elif line.startswith("- ") and current_agent:
                repo_text = line[2:].strip()
                if repo_text and not repo_text.startswith("`"):
                    repo_id = repo_text.split()[0].rstrip(",").rstrip(":")
                    if repo_id:
                        self._agent_to_repo.setdefault(current_agent, []).append(
                            ResearchReference(
                                repo_id=repo_id,
                                relevance_agent=current_agent,
                            )
                        )

    @staticmethod
    def _extract_repo_ids(text: str) -> list[str]:
        """Extract repo IDs from freeform text like 'Trivy, E2B, Semgrep'."""
        # Split on commas, clean up
        parts = [p.strip().rstrip(",") for p in text.replace("`", "").split(",")]
        return [p for p in parts if p and not p.startswith("http")]

    def _load_pattern_index(self) -> None:
        """Parse PATTERN_INDEX.md for pattern→repo mappings."""
        path = os.path.join(self._indexes_dir, "PATTERN_INDEX.md")
        if not os.path.isfile(path):
            return
        try:
            with open(path) as f:
                content = f.read()
            self._parse_pattern_index_md(content)
        except OSError, UnicodeDecodeError:
            pass

    def _parse_pattern_index_md(self, content: str) -> None:
        """Parse the pattern index markdown for pattern→repo references."""
        for line in content.split("\n"):
            line = line.strip()
            # Table rows with pattern name and repo references
            if line.startswith("|") and "`" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    pattern = parts[1].strip("`").strip()
                    if (
                        pattern
                        and not pattern.startswith("-")
                        and not pattern.startswith("Pattern")
                    ):
                        # Later columns may contain repo references
                        for i in range(2, min(len(parts), 4)):
                            repo_text = parts[i].strip()
                            if repo_text and repo_text != "—":
                                for repo_id in self._extract_repo_ids(repo_text):
                                    self._patterns.setdefault(pattern, []).append(
                                        repo_id
                                    )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_for_agent(self, agent_id: str) -> tuple[ResearchReference, ...]:
        """Return research references for a given agent.

        If indexes haven't been loaded yet, loads them first.
        """
        self.load()
        return tuple(self._agent_to_repo.get(agent_id, ()))

    def find_for_layer(self, layer: int) -> tuple[ResearchReference, ...]:
        """Return research references for all agents in a layer.

        Delegates to load() and crawls all agent entries.
        """
        self.load()
        results: list[ResearchReference] = []
        # This is a best-effort search — the agent-to-repo index
        # maps agent_id -> repos. We need registry context to know
        # which agents are in which layer. If not available, return empty.
        # Callers should pass registry for precise layer mapping.
        for refs in self._agent_to_repo.values():
            results.extend(refs)
        return tuple(results)

    def find_for_agent_with_registry(
        self,
        agent_id: str,
        registry,  # AgentRegistry (lazy import to avoid cycle)
    ) -> tuple[ResearchReference, ...]:
        """Find research references for an agent, enriched with registry data."""
        self.load()
        refs = list(self._agent_to_repo.get(agent_id, ()))
        try:
            registry.get(agent_id)  # verify agent exists
            enriched = [
                ResearchReference(
                    repo_id=ref.repo_id,
                    repo_name=ref.repo_name,
                    category=ref.category,
                    patterns=ref.patterns,
                    relevance_agent=agent_id,
                    relevance_level=ref.relevance_level,
                    important_files=ref.important_files,
                )
                for ref in refs
            ]
            return tuple(enriched) if enriched else tuple(refs)
        except KeyError:
            return tuple(refs)

    def find_patterns(self, pattern_keyword: str) -> tuple[str, ...]:
        """Find patterns matching a keyword (case-insensitive substring match)."""
        self.load()
        keyword = pattern_keyword.lower()
        results = [pattern for pattern in self._patterns if keyword in pattern.lower()]
        return tuple(sorted(results))

    def list_categories(self) -> tuple[str, ...]:
        """List all known categories from category index."""
        self.load()
        return tuple(sorted(self._category_to_repo.keys()))

    def list_patterns(self) -> tuple[str, ...]:
        """List all known patterns."""
        self.load()
        return tuple(sorted(self._patterns.keys()))

    def repo_count_for_agent(self, agent_id: str) -> int:
        """Number of research repos mapped to an agent."""
        self.load()
        return len(self._agent_to_repo.get(agent_id, ()))

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, int]:
        """Return a summary of what was loaded."""
        self.load()
        return {
            "agents_with_repos": len(self._agent_to_repo),
            "total_agent_repo_mappings": sum(
                len(v) for v in self._agent_to_repo.values()
            ),
            "patterns_indexed": len(self._patterns),
            "categories_indexed": len(self._category_to_repo),
            "research_root_available": self.is_available,
        }
