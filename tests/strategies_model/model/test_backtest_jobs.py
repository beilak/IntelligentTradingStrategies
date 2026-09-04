from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import BackgroundTasks, HTTPException

import services.strategy_backend.app.test_runs as test_runs_module
from services.strategy_backend.app.backtest import (
    BacktestRunRequest,
    queue_backtest_run,
)


@pytest.fixture(autouse=True)
def isolated_run_status_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setattr(test_runs_module, "RUN_STATUS_DIR", tmp_path / "runs")
    TEST_RUNS.clear()
    yield
    TEST_RUNS.clear()


from services.strategy_backend.app.cpcv import CpcvRunRequest, validate_cpcv_request
from services.strategy_backend.app.test_runs import (
    TEST_RUNS,
    find_test_run,
    list_test_runs,
    public_test_run,
    queue_test_run,
)


def test_duplicate_active_backtest_reuses_existing_run(tmp_path: Path) -> None:
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
    assert first["test_type"] == "backtest"
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_background_test_run_completes_with_lightweight_status(
    tmp_path: Path,
) -> None:
    background_tasks = BackgroundTasks()

    async def flow(**_kwargs: Any) -> dict[str, Any]:
        return {"metadata": {"test_name": "daily"}}

    queued = queue_test_run(
        test_type="cpcv",
        subject_name="ExampleBuilder",
        test_name="daily",
        output_path=tmp_path / "daily.json",
        flow=flow,
        flow_kwargs={},
        background_tasks=background_tasks,
    )

    assert queued["status"] == "queued"
    await background_tasks()

    completed = find_test_run(
        queued["run_id"], test_type="cpcv", subject_name="ExampleBuilder"
    )
    assert completed is not None
    assert completed["status"] == "completed"
    assert "result" not in completed
    assert public_test_run(completed) == {
        "run_id": queued["run_id"],
        "test_type": "cpcv",
        "subject_name": "ExampleBuilder",
        "test_name": "daily",
        "status": "completed",
        "created_at": completed["created_at"],
        "updated_at": completed["updated_at"],
        "error": None,
    }
    assert list_test_runs(test_type="cpcv", subject_name="ExampleBuilder") == [
        completed
    ]


@pytest.mark.asyncio
async def test_background_test_run_preserves_http_error_detail(tmp_path: Path) -> None:
    background_tasks = BackgroundTasks()

    async def flow(**_kwargs: Any) -> dict[str, Any]:
        raise HTTPException(status_code=422, detail="Not enough price rows.")

    queued = queue_test_run(
        test_type="walk_forward",
        subject_name="ExampleBuilder",
        test_name="daily",
        output_path=tmp_path / "daily.json",
        flow=flow,
        flow_kwargs={},
        background_tasks=background_tasks,
    )
    await background_tasks()

    failed = find_test_run(
        queued["run_id"],
        test_type="walk_forward",
        subject_name="ExampleBuilder",
    )
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["error"] == "Not enough price rows."


def test_cpcv_run_request_keeps_test_size() -> None:
    request = CpcvRunRequest(
        test_name="daily",
        start_date="2024-01-01",
        end_date="2024-12-31",
        test_size=0.2,
    )

    assert request.model_dump()["test_size"] == 0.2


def test_cpcv_rejects_combinatorial_fit_count_above_safety_limit() -> None:
    request = CpcvRunRequest(
        test_name="too-large",
        start_date="2024-01-01",
        end_date="2024-12-31",
        n_folds=10,
        n_test_folds=6,
    )

    with pytest.raises(HTTPException, match="1260 model fits"):
        validate_cpcv_request(request)


def test_running_job_is_reported_as_failed_after_registry_restart(
    tmp_path: Path,
) -> None:
    background_tasks = BackgroundTasks()

    async def flow(**_kwargs: Any) -> dict[str, Any]:
        return {}

    queued = queue_test_run(
        test_type="cpcv",
        subject_name="ExampleBuilder",
        test_name="daily",
        output_path=tmp_path / "daily.json",
        flow=flow,
        flow_kwargs={},
        background_tasks=background_tasks,
    )
    TEST_RUNS.clear()

    restored = find_test_run(
        queued["run_id"], test_type="cpcv", subject_name="ExampleBuilder"
    )

    assert restored is not None
    assert restored["status"] == "failed"
    assert "restarted" in restored["error"]
