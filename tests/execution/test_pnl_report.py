from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from its.execution.pnl_report import build_pnl_report, xirr
from its.execution.service import ExecutionService


def money(value: float, currency: str = "rub") -> dict[str, object]:
    return {"value": value, "currency": currency}


def operation(
    operation_id: str,
    operation_date: str,
    operation_type: str,
    payment: float,
    *,
    quantity: int = 0,
    price: float = 0,
    figi: str | None = "FIGI1",
    ticker: str | None = "AAA",
    yield_value: float = 0,
) -> dict[str, object]:
    return {
        "id": operation_id,
        "date": operation_date,
        "type": operation_type,
        "payment": money(payment),
        "price": money(price),
        "quantity_done": quantity,
        "figi": figi,
        "ticker": ticker,
        "name": ticker,
        "yield_": money(yield_value),
    }


def test_report_replays_trades_and_excludes_external_cash_flows_from_pnl() -> None:
    operations = [
        operation(
            "deposit-before",
            "2026-01-01T10:00:00+00:00",
            "OPERATION_TYPE_INPUT",
            1_000,
            figi=None,
            ticker=None,
        ),
        operation(
            "buy",
            "2026-01-02T10:00:00+00:00",
            "OPERATION_TYPE_BUY",
            -500,
            quantity=10,
            price=50,
        ),
        operation(
            "buy-fee",
            "2026-01-02T10:00:01+00:00",
            "OPERATION_TYPE_BROKER_FEE",
            -5,
        ),
        operation(
            "deposit-during",
            "2026-01-03T09:00:00+00:00",
            "OPERATION_TYPE_INPUT",
            100,
            figi=None,
            ticker=None,
        ),
        operation(
            "dividend",
            "2026-01-03T10:00:00+00:00",
            "OPERATION_TYPE_DIVIDEND",
            10,
        ),
        operation(
            "sell",
            "2026-01-04T10:00:00+00:00",
            "OPERATION_TYPE_SELL",
            270,
            quantity=5,
            price=54,
            yield_value=20,
        ),
        operation(
            "sell-fee",
            "2026-01-04T10:00:01+00:00",
            "OPERATION_TYPE_BROKER_FEE",
            -3,
        ),
    ]
    prices = [
        {"figi": "FIGI1", "ticker": "AAA", "time": "2026-01-01", "close": 50},
        {"figi": "FIGI1", "ticker": "AAA", "time": "2026-01-02", "close": 52},
        {"figi": "FIGI1", "ticker": "AAA", "time": "2026-01-03", "close": 55},
        {"figi": "FIGI1", "ticker": "AAA", "time": "2026-01-04", "close": 54},
    ]

    report = build_pnl_report(
        account_id="acc-1",
        account_name="Main",
        from_date=date(2026, 1, 2),
        to_date=date(2026, 1, 4),
        operations=operations,
        prices=prices,
        strategy_name="StrategyA",
        assigned_strategies=["StrategyA"],
    )

    assert report["summary"]["opening_nav"] == pytest.approx(1_000)
    assert report["summary"]["ending_nav"] == pytest.approx(1_142)
    assert report["summary"]["net_external_flow"] == pytest.approx(100)
    assert report["summary"]["total_pnl"] == pytest.approx(42)
    assert report["summary"]["fees"] == pytest.approx(-8)
    assert report["summary"]["dividends"] == pytest.approx(10)
    assert report["summary"]["realized_pnl_broker"] == pytest.approx(20)
    assert report["summary"]["unrealized_pnl_estimate"] == pytest.approx(20)
    assert report["summary"]["trades"] == 2
    assert report["strategy"]["attribution_mode"] == "dedicated_account_proxy"
    assert report["strategy"]["is_exact"] is False
    assert report["equity_curve"][0]["nav"] == pytest.approx(1_015)
    assert report["equity_curve"][-1]["cumulative_pnl"] == pytest.approx(42)
    assert report["attribution"][0]["ticker"] == "AAA"


def test_report_builds_drawdown_and_monthly_returns() -> None:
    report = build_pnl_report(
        account_id="acc-1",
        account_name="Main",
        from_date=date(2026, 1, 2),
        to_date=date(2026, 2, 2),
        operations=[
            operation(
                "deposit",
                "2026-01-01T10:00:00+00:00",
                "OPERATION_TYPE_INPUT",
                100,
                figi=None,
                ticker=None,
            ),
            operation(
                "buy",
                "2026-01-01T11:00:00+00:00",
                "OPERATION_TYPE_BUY",
                -100,
                quantity=1,
                price=100,
            ),
        ],
        prices=[
            {"figi": "FIGI1", "time": "2026-01-01", "close": 100},
            {"figi": "FIGI1", "time": "2026-01-02", "close": 110},
            {"figi": "FIGI1", "time": "2026-01-20", "close": 88},
            {"figi": "FIGI1", "time": "2026-02-02", "close": 99},
        ],
    )

    assert report["summary"]["total_pnl"] == pytest.approx(-1)
    assert report["risk"]["max_drawdown"] == pytest.approx(-0.2)
    assert [row["month"] for row in report["monthly_returns"]] == [
        "2026-01",
        "2026-02",
    ]


def test_xirr_returns_annual_money_weighted_return() -> None:
    rate = xirr(
        [
            (date(2025, 1, 1), -1_000),
            (date(2026, 1, 1), 1_100),
        ]
    )
    assert rate == pytest.approx(0.1, rel=1e-3)


@pytest.mark.asyncio
async def test_operations_history_uses_cursor_until_last_page(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    seen_cursors: list[str | None] = []

    class Operations:
        async def get_operations_by_cursor(self, request):
            seen_cursors.append(request.cursor)
            if len(seen_cursors) == 1:
                return {
                    "items": [{"id": "one"}],
                    "has_next": True,
                    "next_cursor": "next",
                }
            return {"items": [{"id": "two"}], "has_next": False, "next_cursor": ""}

    result = await ExecutionService()._get_all_operations(
        SimpleNamespace(operations=Operations()),
        account_id="acc-1",
        to=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert seen_cursors == [None, "next"]
    assert [row["id"] for row in result] == ["one", "two"]
