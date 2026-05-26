"""FCC smoke target adapter for Ralph Runtime.

Maps Ralph smoke target labels (strings) to FCC-compatible command
plans. Deterministic — no network, no imports from FCC smoke/.
"""

from __future__ import annotations

from dataclasses import dataclass

# Known FCC smoke targets extracted from smoke/features.py.
# Each maps to the pytest command(s) that exercise it.
_KNOWN_SMOKE_TARGETS: dict[str, str] = {
    "providers": "pytest smoke/prereq -m providers --co -q",
    "api": "pytest smoke/prereq -m api --co -q",
    "cli": "pytest smoke/prereq -m cli --co -q",
    "clients": "pytest smoke/prereq -m clients --co -q",
    "nvidia_nim_cli": "pytest smoke/prereq -m nvidia_nim_cli --co -q",
    "openrouter_free_cli": "pytest smoke/prereq -m openrouter_free_cli --co -q",
    "config": "pytest smoke/prereq -m config --co -q",
    "messaging": "pytest smoke/prereq -m messaging --co -q",
    "tools": "pytest smoke/prereq -m tools --co -q",
    "voice": "pytest smoke/prereq -m voice --co -q",
    "rate_limit": "pytest smoke/prereq -m rate_limit --co -q",
    "auth": "pytest smoke/prereq -m auth --co -q",
    "extensibility": "pytest smoke/prereq -m extensibility --co -q",
    "lmstudio": "pytest smoke/prereq -m lmstudio --co -q",
    "llamacpp": "pytest smoke/prereq -m llamacpp --co -q",
    "ollama": "pytest smoke/prereq -m ollama --co -q",
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
        # plan.commands -> ("pytest smoke/prereq -m providers --co -q", ...)
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
        """
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
