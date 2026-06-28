from pathlib import Path

from fastapi import BackgroundTasks

from services.strategy_backend.app.backtest import (
    BACKTEST_RUNS,
    BacktestRunRequest,
    queue_backtest_run,
)


def test_duplicate_active_backtest_reuses_existing_run(tmp_path: Path) -> None:
    BACKTEST_RUNS.clear()
    request = BacktestRunRequest(
        test_name="daily",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    background_tasks = BackgroundTasks()
    output_path = tmp_path / "daily.json"

    first = queue_backtest_run(
        subject_name="ExampleBuilder",
        request=request,
        output_path=output_path,
        report_factory=lambda *args, **kwargs: {},
        authorization=None,
        background_tasks=background_tasks,
    )
    second = queue_backtest_run(
        subject_name="ExampleBuilder",
        request=request,
        output_path=output_path,
        report_factory=lambda *args, **kwargs: {},
        authorization=None,
        background_tasks=background_tasks,
    )

    assert second["run_id"] == first["run_id"]
    assert len(background_tasks.tasks) == 1
    BACKTEST_RUNS.clear()
