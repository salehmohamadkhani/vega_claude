"""FCC smoke target adapter for Ralph Runtime.

Maps Ralph smoke target labels (strings) to FCC-compatible command
plans. Deterministic — no network, no imports from FCC smoke/.
"""

from __future__ import annotations

from dataclasses import dataclass

# Known FCC smoke targets extracted from smoke/features.py.
# Each maps to the pytest command(s) that exercise it.
# Keep in sync with FEATURE_INVENTORY smoke_targets in smoke/features.py.
_KNOWN_SMOKE_TARGETS: dict[str, str] = {
    "providers": "uv run pytest smoke/prereq -m providers --collect-only -q",
    "api": "uv run pytest smoke/prereq -m api --collect-only -q",
    "cli": "uv run pytest smoke/prereq -m cli --collect-only -q",
    "clients": "uv run pytest smoke/prereq -m clients --collect-only -q",
    "nvidia_nim_cli": "uv run pytest smoke/prereq -m nvidia_nim_cli --collect-only -q",
    "openrouter_free_cli": "uv run pytest smoke/prereq -m openrouter_free_cli --collect-only -q",
    "config": "uv run pytest smoke/prereq -m config --collect-only -q",
    "messaging": "uv run pytest smoke/prereq -m messaging --collect-only -q",
    "tools": "uv run pytest smoke/prereq -m tools --collect-only -q",
    "voice": "uv run pytest smoke/prereq -m voice --collect-only -q",
    "rate_limit": "uv run pytest smoke/prereq -m rate_limit --collect-only -q",
    "auth": "uv run pytest smoke/prereq -m auth --collect-only -q",
    "extensibility": "uv run pytest smoke/prereq -m extensibility --collect-only -q",
    "lmstudio": "uv run pytest smoke/prereq -m lmstudio --collect-only -q",
    "llamacpp": "uv run pytest smoke/prereq -m llamacpp --collect-only -q",
    "ollama": "uv run pytest smoke/prereq -m ollama --collect-only -q",
    "telegram": "uv run pytest smoke/prereq -m telegram --collect-only -q",
    "discord": "uv run pytest smoke/prereq -m discord --collect-only -q",
}


@dataclass(frozen=True)
class SmokePlan:
    """A plan for running smoke verification on a set of targets."""

    targets: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    unknown_targets: tuple[str, ...] = ()
    requires_live_provider: bool = False


class FCCSmokeAdapter:
    """Maps smoke target labels to command plans without executing anything.

    Usage::

        adapter = FCCSmokeAdapter()
        plan = adapter.build_smoke_plan(["providers", "api"])
        # plan.commands -> ("uv run pytest smoke/prereq -m providers --collect-only -q", ...)
    """

    def __init__(self, known_targets: dict[str, str] | None = None) -> None:
        self._targets = dict(known_targets or _KNOWN_SMOKE_TARGETS)

    @property
    def known_targets(self) -> set[str]:
        """Return the set of known smoke target labels."""
        return set(self._targets)

    def is_known(self, target: str) -> bool:
        """Return True if the target label is recognised."""
        return target in self._targets

    def validate_targets(self, targets: list[str]) -> tuple[list[str], list[str]]:
        """Split a list of targets into (known, unknown)."""
        known: list[str] = []
        unknown: list[str] = []
        for t in targets:
            (known if t in self._targets else unknown).append(t)
        return known, unknown

    def build_smoke_plan(self, targets: list[str]) -> SmokePlan:
        """Convert smoke targets into a SmokePlan with commands.

        Unknown targets are collected but not mapped to commands.
        When targets is empty, a collect-only command is returned so all
        smoke tests are at least validated as parseable.
        """
        if not targets:
            return SmokePlan(
                targets=(),
                commands=("uv run pytest smoke --collect-only -q",),
                unknown_targets=(),
                requires_live_provider=False,
            )

        known, unknown = self.validate_targets(targets)
        commands: list[str] = []
        requires_live = False
        for t in known:
            cmd = self._targets[t]
            commands.append(cmd)
            # Targets that exercise provider routes require live provider
            if t in ("providers", "api", "clients"):
                requires_live = True

        return SmokePlan(
            targets=tuple(known),
            commands=tuple(commands),
            unknown_targets=tuple(unknown),
            requires_live_provider=requires_live,
        )
