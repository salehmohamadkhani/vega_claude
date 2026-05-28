"""Tests for verification policy layer."""

from __future__ import annotations

from core.ralph.verification_policy import (
    VerificationCommandRisk,
    VerificationPolicy,
    VerificationPolicyDecision,
)


class TestVerificationPolicyAllow:
    """Policy allows safe commands."""

    def test_safe_pytest_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("uv run pytest tests/core/ralph -q")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_safe_py_compile_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("python -m py_compile core/ralph/*.py")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_safe_ruff_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("uv run ruff check core/ralph tests/core/ralph")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_safe_ty_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("uv run ty check core/ralph")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_smoke_collect_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("uv run pytest smoke --collect-only -q")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_git_status_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("git status --short")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_git_diff_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("git diff --check")
        assert d.allowed is True
        assert d.risk == VerificationCommandRisk.SAFE

    def test_git_log_allowed(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("git log --oneline -3")
        assert d.allowed is True


class TestVerificationPolicyBlock:
    """Policy blocks dangerous commands."""

    def test_rm_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("rm -rf /tmp/foo")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_del_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("del /s /q C:\\temp")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_format_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("format C: /y")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_curl_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("curl http://example.com")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_wget_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("wget http://example.com")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_git_push_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("git push origin master")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_git_reset_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("git reset --hard HEAD")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_git_clean_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("git clean -fdx")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_shell_invocation_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("sh -c 'rm -rf /'")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_powershell_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("powershell Invoke-WebRequest -Uri http://x.com")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_python_c_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command('python -c "import requests"')
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_npm_install_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("npm install")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED

    def test_pip_install_blocked(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("pip install requests")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.BLOCKED


class TestVerificationPolicyNormalization:
    """Command normalization is stable."""

    def test_empty_command(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("")
        assert d.allowed is False

    def test_garbage_input(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("'unclosed quote")
        assert d.allowed is False
        assert "parse" in d.reason.lower()

    def test_unrecognised_tool_falls_to_review(self) -> None:
        policy = VerificationPolicy()
        d = policy.classify_command("some_random_tool --flag")
        assert d.allowed is False
        assert d.risk == VerificationCommandRisk.REVIEW


class TestVerificationPolicyValidateCommands:
    """Batch validation works correctly."""

    def test_validate_commands_mixed(self) -> None:
        policy = VerificationPolicy()
        commands = [
            "uv run pytest tests -q",
            "rm -rf /",
            "curl http://example.com",
            "git status",
        ]
        results = policy.validate_commands(commands)
        assert len(results) == 4
        assert results[0].allowed is True
        assert results[1].allowed is False
        assert results[2].allowed is False
        assert results[3].allowed is True
