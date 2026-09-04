from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks

TestFlow = Callable[..., Awaitable[dict[str, Any]]]

TEST_RUNS: dict[str, dict[str, Any]] = {}
MAX_CONCURRENT_TESTS = max(
    1,
    int(
        os.getenv(
            "STRATEGY_MAX_CONCURRENT_TESTS",
            os.getenv("STRATEGY_MAX_CONCURRENT_BACKTESTS", "1"),
        )
    ),
)
TEST_RUN_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
MAX_RETAINED_TEST_RUNS = 100
RUN_STATUS_DIR = Path(
    os.getenv("STRATEGY_RUN_STATUS_DIR", "/tmp/its-strategy-test-runs")
)


def queue_test_run(
    *,
    test_type: str,
    subject_name: str,
    test_name: str,
    output_path: Path,
    flow: TestFlow,
    flow_kwargs: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    restore_test_runs()
    output_key = str(output_path)
    for existing_run in TEST_RUNS.values():
        if existing_run.get("output_path") == output_key and existing_run.get(
            "status"
        ) in {"queued", "running"}:
            return existing_run

    prune_test_runs()
    run_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    run = {
        "run_id": run_id,
        "test_type": test_type,
        "subject_name": subject_name,
        "test_name": test_name,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "error": None,
        "output_path": output_key,
    }
    TEST_RUNS[run_id] = run
    persist_test_run(run)
    background_tasks.add_task(
        execute_test_run,
        run_id=run_id,
        flow=flow,
        flow_kwargs=flow_kwargs,
    )
    return run


async def execute_test_run(
    *, run_id: str, flow: TestFlow, flow_kwargs: dict[str, Any]
) -> None:
    run = TEST_RUNS[run_id]
    async with TEST_RUN_SEMAPHORE:
        run.update(status="running", updated_at=datetime.now(UTC).isoformat())
        persist_test_run(run)
        try:
            await flow(**flow_kwargs)
            run.update(
                status="completed",
                updated_at=datetime.now(UTC).isoformat(),
            )
            persist_test_run(run)
        # This is the worker boundary: every calculation failure must become a
        # terminal job state so clients do not poll a permanently running job.
        except Exception as exc:  # noqa: BLE001
            detail = getattr(exc, "detail", None)
            run.update(
                status="failed",
                error=str(detail or exc or exc.__class__.__name__),
                updated_at=datetime.now(UTC).isoformat(),
            )
            persist_test_run(run)


def find_test_run(
    run_id: str, *, test_type: str, subject_name: str
) -> dict[str, Any] | None:
    restore_test_runs()
    run = TEST_RUNS.get(run_id)
    if (
        run is None
        or run.get("test_type") != test_type
        or run.get("subject_name") != subject_name
    ):
        return None
    return run


def list_test_runs(*, test_type: str, subject_name: str) -> list[dict[str, Any]]:
    restore_test_runs()
    return sorted(
        (
            run
            for run in TEST_RUNS.values()
            if run.get("test_type") == test_type
            and run.get("subject_name") == subject_name
        ),
        key=lambda run: str(run.get("created_at", "")),
        reverse=True,
    )


def public_test_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run.get(key)
        for key in (
            "run_id",
            "test_type",
            "subject_name",
            "test_name",
            "status",
            "created_at",
            "updated_at",
            "error",
        )
    }


def persist_test_run(run: dict[str, Any]) -> None:
    RUN_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUN_STATUS_DIR / f"{run['run_id']}.json"
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(public_test_run(run), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def restore_test_runs() -> None:
    if not RUN_STATUS_DIR.exists():
        return
    for path in RUN_STATUS_DIR.glob("*.json"):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        run_id = str(run.get("run_id", ""))
        if not run_id or run_id in TEST_RUNS:
            continue
        if run.get("status") in {"queued", "running"}:
            run.update(
                status="failed",
                error="The strategy backend restarted before the test completed.",
                updated_at=datetime.now(UTC).isoformat(),
            )
            TEST_RUNS[run_id] = run
            persist_test_run(run)
        else:
            TEST_RUNS[run_id] = run


def prune_test_runs() -> None:
    overflow = len(TEST_RUNS) - MAX_RETAINED_TEST_RUNS + 1
    if overflow <= 0:
        return
    finished = sorted(
        (
            run
            for run in TEST_RUNS.values()
            if run.get("status") in {"completed", "failed"}
        ),
        key=lambda run: str(run.get("updated_at", "")),
    )
    for run in finished[:overflow]:
        TEST_RUNS.pop(str(run["run_id"]), None)
        status_path = RUN_STATUS_DIR / f"{run['run_id']}.json"
        status_path.unlink(missing_ok=True)
