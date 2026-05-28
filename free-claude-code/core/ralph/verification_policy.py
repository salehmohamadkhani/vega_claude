"""Structured verification policy for Ralph Runtime task commands.

Classifies verification commands by risk level and prevents unsafe
commands from executing. Allowed commands correspond to common
Ralph/FCC development tools (pytest, ruff, ty, py_compile, git
read-only). Blocked commands are those that could modify state,
make network requests, or destroy data.
"""

from __future__ import annotations

import enum
import shlex
from dataclasses import dataclass


class VerificationCommandRisk(enum.Enum):
    """Risk level of a verification command."""

    SAFE = "safe"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass
class VerificationPolicyDecision:
    """Result of classifying a single verification command."""

    command: str = ""
    risk: VerificationCommandRisk = VerificationCommandRisk.BLOCKED
    allowed: bool = False
    reason: str = ""
    normalized_command: str = ""


# Tokens that indicate a command is destructive or unsafe.
_DESTRUCTIVE_TOKENS: frozenset[str] = frozenset({
    "rm", "rmdir", "del", "erase", "format",
    "shutdown", "reboot", "halt", "poweroff",
    "dd", "mkfs", "fdisk", "parted",
})

# Tokens that indicate a network fetch (blocked in verification).
_NETWORK_TOKENS: frozenset[str] = frozenset({
    "curl", "wget", "fetch", "Invoke-WebRequest",
    "iwr", "Invoke-RestMethod", "irm",
})

# CLI tools that modify git state (blocked in verification; normal
# git workflow outside the runner is unaffected).
_GIT_WRITE_TOKENS: frozenset[str] = frozenset({
    "commit", "push", "pull", "merge", "rebase",
    "reset", "clean", "cherry-pick", "revert",
})

# Pip/install commands (blocked — verification must not mutate env).
_INSTALL_TOKENS: frozenset[str] = frozenset({
    "install", "add", "remove", "upgrade",
})


def _classify_internal(argv: list[str]) -> VerificationPolicyDecision:
    """Classify a parsed command vector without normalizing."""
    command_str = shlex.join(argv)
    decision = VerificationPolicyDecision(
        command=command_str,
        normalized_command=command_str,
    )

    if not argv:
        decision.reason = "Empty command."
        return decision

    tool = argv[0]

    # --- Safe tools (always allowed) ---
    if tool == "python" and "-m" in argv:
        if "py_compile" in argv:
            decision.risk = VerificationCommandRisk.SAFE
            decision.allowed = True
            decision.reason = "Python compile check."
            return decision
        if "pytest" in argv:
            decision.risk = VerificationCommandRisk.SAFE
            decision.allowed = True
            decision.reason = "Python pytest runner."
            return decision

    if tool == "uv" and "run" in argv:
        if "pytest" in argv:
            decision.risk = VerificationCommandRisk.SAFE
            decision.allowed = True
            decision.reason = "uv pytest runner."
            return decision
        if "ruff" in argv:
            decision.risk = VerificationCommandRisk.SAFE
            decision.allowed = True
            decision.reason = "Ruff linter via uv."
            return decision
        if "ty" in argv:
            decision.risk = VerificationCommandRisk.SAFE
            decision.allowed = True
            decision.reason = "Ty type checker via uv."
            return decision

    if tool in ("ruff",):
        decision.risk = VerificationCommandRisk.SAFE
        decision.allowed = True
        decision.reason = "Ruff linter."
        return decision

    if tool in ("ty",):
        decision.risk = VerificationCommandRisk.SAFE
        decision.allowed = True
        decision.reason = "Ty type checker."
        return decision

    if tool == "git":
        # Only read-only git operations are allowed in verification.
        rest = [a for a in argv[1:] if not a.startswith("-")]
        if rest:
            subcommand = rest[0]
            if subcommand in ("status", "diff", "log", "show", "branch", "ls-files"):
                decision.risk = VerificationCommandRisk.SAFE
                decision.allowed = True
                decision.reason = f"Git read-only: {subcommand}."
                return decision
        decision.risk = VerificationCommandRisk.BLOCKED
        decision.allowed = False
        decision.reason = "Write git operations are blocked in verification."
        return decision

    # --- Blocked tools ---
    if tool in _DESTRUCTIVE_TOKENS:
        decision.risk = VerificationCommandRisk.BLOCKED
        decision.allowed = False
        decision.reason = f"Destructive command blocked: {tool}."
        return decision

    if tool in _NETWORK_TOKENS:
        decision.risk = VerificationCommandRisk.BLOCKED
        decision.allowed = False
        decision.reason = f"Network command blocked: {tool}."
        return decision

    # --uv run with non-whitelisted subcommand
    if tool == "uv":
        for t in argv:
            if t in ("install", "add", "remove", "sync"):
                decision.risk = VerificationCommandRisk.BLOCKED
                decision.allowed = False
                decision.reason = f"uv mutating operation blocked: {t}."
                return decision
        decision.risk = VerificationCommandRisk.REVIEW
        decision.allowed = False
        decision.reason = f"uv command not in allowed list: {' '.join(argv[:3])}."
        return decision

    # -- npm / pip / cargo / other package managers
    if tool in ("npm", "pip", "pip3", "cargo", "go"):
        decision.risk = VerificationCommandRisk.BLOCKED
        decision.allowed = False
        decision.reason = f"Package manager blocked: {tool}."
        return decision

    # -- shell invocation (blocked)
    if tool in ("sh", "bash", "zsh", "powershell", "pwsh", "cmd", "cmd.exe"):
        decision.risk = VerificationCommandRisk.BLOCKED
        decision.allowed = False
        decision.reason = f"Shell invocation blocked: {tool}."
        return decision

    # -- Anything with python -c (arbitrary code)
    if tool == "python" and len(argv) > 1 and argv[1] in ("-c", "-i"):
        decision.risk = VerificationCommandRisk.BLOCKED
        decision.allowed = False
        decision.reason = "Arbitrary python code execution blocked."
        return decision

    # Fallback: unknown tool requires review.
    decision.risk = VerificationCommandRisk.REVIEW
    decision.allowed = False
    decision.reason = f"Unrecognised command: {tool}."
    return decision


class VerificationPolicy:
    """Policy for classifying and allowing/blocking verification commands.

    The policy is deterministic — no AI, no network. It classifies
    commands as SAFE (allowed), REVIEW (requires human review), or
    BLOCKED (destructive / network / shell). Only SAFE commands are
    allowed to execute by default.

    Parameters
    ----------
    allow_pytest:
        Allow ``python -m pytest`` / ``uv run pytest``.
    allow_python_compile:
        Allow ``python -m py_compile``.
    allow_ruff:
        Allow ``ruff`` / ``uv run ruff``.
    allow_ty:
        Allow ``ty`` / ``uv run ty``.
    allow_smoke_collect:
        Allow smoke collection targets.
    allow_git_readonly:
        Allow read-only git commands (status, diff, log, etc.).
    block_shell:
        Block shell invocation (sh, bash, powershell, etc.).
    block_network:
        Block network commands (curl, wget, etc.).
    block_destructive_commands:
        Block destructive commands (rm, del, format, etc.).
    max_timeout_seconds:
        Maximum allowed timeout for any verification command.
    """

    def __init__(
        self,
        allow_pytest: bool = True,
        allow_python_compile: bool = True,
        allow_ruff: bool = True,
        allow_ty: bool = True,
        allow_smoke_collect: bool = True,
        allow_git_readonly: bool = True,
        block_shell: bool = True,
        block_network: bool = True,
        block_destructive_commands: bool = True,
        max_timeout_seconds: int = 120,
    ) -> None:
        self.allow_pytest = allow_pytest
        self.allow_python_compile = allow_python_compile
        self.allow_ruff = allow_ruff
        self.allow_ty = allow_ty
        self.allow_smoke_collect = allow_smoke_collect
        self.allow_git_readonly = allow_git_readonly
        self.block_shell = block_shell
        self.block_network = block_network
        self.block_destructive_commands = block_destructive_commands
        self.max_timeout_seconds = max_timeout_seconds

    def classify_command(self, command: str) -> VerificationPolicyDecision:
        """Classify a single command string and return a policy decision.

        The command is parsed via ``shlex.split`` and then checked against
        the policy rules. If parsing fails, the command is blocked.
        """
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return VerificationPolicyDecision(
                command=command,
                risk=VerificationCommandRisk.BLOCKED,
                allowed=False,
                reason=f"Failed to parse command: {exc}",
                normalized_command=command,
            )

        decision = _classify_internal(argv)

        # Apply toggle flags: if a safe category is disabled, block it.
        if decision.allowed:
            if not self.allow_pytest and (
                "pytest" in decision.command or "pytest" in command
            ):
                decision.allowed = False
                decision.risk = VerificationCommandRisk.REVIEW
                decision.reason = "Pytest verification disabled by policy."
            if not self.allow_ruff and (
                "ruff" in decision.command or "ruff" in command
            ):
                decision.allowed = False
                decision.risk = VerificationCommandRisk.REVIEW
                decision.reason = "Ruff verification disabled by policy."
            if not self.allow_ty and ("ty" in decision.command or "ty" in command):
                decision.allowed = False
                decision.risk = VerificationCommandRisk.REVIEW
                decision.reason = "Ty verification disabled by policy."
            if not self.allow_python_compile and "py_compile" in decision.command:
                decision.allowed = False
                decision.risk = VerificationCommandRisk.REVIEW
                decision.reason = "Python compile verification disabled by policy."
            if not self.allow_smoke_collect and "smoke" in decision.command:
                decision.allowed = False
                decision.risk = VerificationCommandRisk.REVIEW
                decision.reason = "Smoke collection disabled by policy."
            if "git" in decision.command and not self.allow_git_readonly:
                decision.allowed = False
                decision.risk = VerificationCommandRisk.REVIEW
                decision.reason = "Git read-only verification disabled by policy."

        return decision

    def validate_commands(
        self,
        commands: list[str],
    ) -> list[VerificationPolicyDecision]:
        """Classify every command in a list.

        Returns a list of policy decisions in the same order as the input.
        """
        return [self.classify_command(cmd) for cmd in commands]
