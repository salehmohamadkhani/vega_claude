"""Tests for KPI model layer."""

from __future__ import annotations

from pathlib import Path

from core.ralph.kpi import KPI, KPIEvaluator, KPIResult, KPIStatus, KPIType
from core.ralph.verification_policy import VerificationPolicy


class TestKPIEvaluatorFileExists:
    """File-exists KPI evaluation."""

    def test_file_exists_passes(self, tmp_path: Path) -> None:
        (tmp_path / "test.txt").write_text("hello")
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(id="kpi-1", type=KPIType.FILE_EXISTS, file_path="test.txt")
        result = evaluator.evaluate(kpi)
        assert result.passed is True
        assert result.status == KPIStatus.PASSED

    def test_file_not_found_fails(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(id="kpi-1", type=KPIType.FILE_EXISTS, file_path="nonexistent.txt")
        result = evaluator.evaluate(kpi)
        assert result.passed is False
        assert result.status == KPIStatus.FAILED

    def test_no_file_path_skipped(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(id="kpi-1", type=KPIType.FILE_EXISTS, file_path="")
        result = evaluator.evaluate(kpi)
        assert result.passed is False
        assert result.status == KPIStatus.SKIPPED

    def test_path_escape_workspace_fails(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(id="kpi-1", type=KPIType.FILE_EXISTS, file_path="../outside.txt")
        result = evaluator.evaluate(kpi)
        assert result.passed is False
        assert result.status == KPIStatus.FAILED


class TestKPIEvaluatorTextMatch:
    """Text-match KPI evaluation."""

    def test_text_found_passes(self, tmp_path: Path) -> None:
        (tmp_path / "output.txt").write_text("Hello, world!")
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(
            id="kpi-1",
            type=KPIType.TEXT_MATCH,
            file_path="output.txt",
            text="Hello",
        )
        result = evaluator.evaluate(kpi)
        assert result.passed is True
        assert result.status == KPIStatus.PASSED

    def test_text_not_found_fails(self, tmp_path: Path) -> None:
        (tmp_path / "output.txt").write_text("Goodbye, world!")
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(
            id="kpi-1",
            type=KPIType.TEXT_MATCH,
            file_path="output.txt",
            text="Hello",
        )
        result = evaluator.evaluate(kpi)
        assert result.passed is False
        assert result.status == KPIStatus.FAILED

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(
            id="kpi-1",
            type=KPIType.TEXT_MATCH,
            file_path="missing.txt",
            text="Hello",
        )
        result = evaluator.evaluate(kpi)
        assert result.passed is False

    def test_no_file_path_skipped(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpi = KPI(id="kpi-1", type=KPIType.TEXT_MATCH, text="Hello")
        result = evaluator.evaluate(kpi)
        assert result.status == KPIStatus.SKIPPED


class TestKPIEvaluatorBoolean:
    """Boolean KPI evaluation."""

    def test_true_target_passes(self) -> None:
        evaluator = KPIEvaluator()
        kpi = KPI(id="kpi-1", type=KPIType.BOOLEAN, target=True)
        result = evaluator.evaluate(kpi)
        assert result.passed is True
        assert result.status == KPIStatus.PASSED

    def test_false_target_fails(self) -> None:
        evaluator = KPIEvaluator()
        kpi = KPI(id="kpi-1", type=KPIType.BOOLEAN, target=False)
        result = evaluator.evaluate(kpi)
        assert result.passed is False
        assert result.status == KPIStatus.FAILED


class TestKPIEvaluatorThreshold:
    """Threshold KPI evaluation."""

    def test_above_threshold_passes(self) -> None:
        evaluator = KPIEvaluator()
        kpi = KPI(id="kpi-1", type=KPIType.THRESHOLD, target=95, threshold=80)
        result = evaluator.evaluate(kpi)
        assert result.passed is True

    def test_below_threshold_fails(self) -> None:
        evaluator = KPIEvaluator()
        kpi = KPI(id="kpi-1", type=KPIType.THRESHOLD, target=50, threshold=80)
        result = evaluator.evaluate(kpi)
        assert result.passed is False


class TestKPIEvaluatorCommandExitZero:
    """Command-exit-zero KPI evaluation."""

    def test_successful_command_passes(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(
            workspace_root=tmp_path,
            policy=VerificationPolicy(),
        )
        kpi = KPI(
            id="kpi-1",
            type=KPIType.COMMAND_EXIT_ZERO,
            command="python -m py_compile --help",
        )
        result = evaluator.evaluate(kpi)
        assert result.passed is True, f"Expected pass, got {result.reason}"

    def test_blocked_command_skipped(self, tmp_path: Path) -> None:
        evaluator = KPIEvaluator(
            workspace_root=tmp_path,
            policy=VerificationPolicy(),
        )
        kpi = KPI(
            id="kpi-1",
            type=KPIType.COMMAND_EXIT_ZERO,
            command="rm -rf /tmp",
        )
        result = evaluator.evaluate(kpi)
        assert result.passed is False
        assert result.status == KPIStatus.SKIPPED
        assert "blocked" in result.reason.lower()


class TestKPIEvaluatorBatch:
    """Batch evaluation."""

    def test_evaluate_all_returns_results_in_order(self, tmp_path: Path) -> None:
        (tmp_path / "exists.txt").write_text("data")
        evaluator = KPIEvaluator(workspace_root=tmp_path)
        kpis = [
            KPI(id="k1", type=KPIType.BOOLEAN, target=True),
            KPI(id="k2", type=KPIType.FILE_EXISTS, file_path="exists.txt"),
            KPI(id="k3", type=KPIType.FILE_EXISTS, file_path="missing.txt"),
        ]
        results = evaluator.evaluate_all(kpis)
        assert len(results) == 3
        assert results[0].passed is True
        assert results[1].passed is True
        assert results[2].passed is False

    def test_kpis_all_passed_helper(self) -> None:
        evaluator = KPIEvaluator()
        results = [
            KPIResult(kpi_id="k1", passed=True, status=KPIStatus.PASSED),
            KPIResult(kpi_id="k2", passed=True, status=KPIStatus.PASSED),
        ]
        assert evaluator.kpis_all_passed(results) is True

    def test_kpis_all_passed_fails_on_failure(self) -> None:
        evaluator = KPIEvaluator()
        results = [
            KPIResult(kpi_id="k1", passed=True, status=KPIStatus.PASSED),
            KPIResult(kpi_id="k2", passed=False, status=KPIStatus.FAILED),
        ]
        assert evaluator.kpis_all_passed(results) is False
