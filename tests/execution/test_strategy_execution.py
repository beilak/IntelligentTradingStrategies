from datetime import date

import pandas as pd
import pytest
from fastapi import HTTPException

import its.execution.service as service_module
from its.execution.schemas import StrategyExecutionRequest
from its.execution.service import ExecutionService
from its.execution.strategy_runner import StrategyRunSettings, build_preview_payload
from its.strategies.testing.backtest.vectorbt_backtest import _build_order_plan
from its.strategies_model.model import ModelPullbackWithEqStopLoss1TakeProfit3Builder


class ExampleStrategy:
    name = "ExampleStrategy"
    description = "Example rebalance strategy"
    exit_policy = None


class StopsStrategy(ExampleStrategy):
    exit_policy = type(
        "ExitPolicy",
        (),
        {"stop_loss_pct": 0.01, "take_profit_pct": 0.03},
    )()


class UnsupportedLiveStrategy(ExampleStrategy):
    supports_live_execution = False


def strategy_settings() -> StrategyRunSettings:
    return StrategyRunSettings(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 8, 1),
        interval="CANDLE_INTERVAL_DAY",
        class_code="TQBR",
        order_type="market",
        limit_offset_pct=0.0,
        min_order_value=0.0,
        cash_buffer_pct=0.01,
    )


def account_overview(*, open_orders: int = 0) -> dict:
    return {
        "summary": {
            "portfolio_value": 1_000.0,
            "open_orders_count": open_orders,
            "total_amount_portfolio": {"value": 1_000.0, "currency": "rub"},
            "money": [{"value": 650.0, "currency": "rub"}],
        },
        "sections": {
            "portfolio": {
                "positions": [
                    {
                        "figi": "figi-a",
                        "instrument_uid": "uid-a",
                        "instrument_type": "share",
                        "quantity": {"value": 20.0},
                        "quantity_lots": {"value": 2.0},
                        "blocked_lots": {"value": 0.0},
                    },
                    {
                        "figi": "figi-b",
                        "instrument_uid": "uid-b",
                        "instrument_type": "share",
                        "quantity": {"value": 3.0},
                        "quantity_lots": {"value": 3.0},
                        "blocked_lots": {"value": 0.0},
                    },
                    {
                        "figi": "RUB000UTSTOM",
                        "instrument_uid": "rub-uid",
                        "instrument_type": "currency",
                        "quantity": {"value": 650.0},
                        "quantity_lots": {"value": 650.0},
                    },
                ]
            }
        },
    }


def build_plan(*, open_orders: int = 0) -> dict:
    run_time = pd.Timestamp("2026-08-01")
    close = pd.DataFrame(
        [{"AAA": 10.0, "BBB": 50.0, "CCC": 20.0}],
        index=[run_time],
    )
    stocks = [
        {"ticker": "AAA", "figi": "figi-a", "uid": "uid-a", "lot": 10},
        {"ticker": "BBB", "figi": "figi-b", "uid": "uid-b", "lot": 1},
        {"ticker": "CCC", "figi": "figi-c", "uid": "uid-c", "lot": 1},
    ]
    return build_preview_payload(
        strategy=ExampleStrategy(),
        account_id="acc-1",
        account_overview=account_overview(open_orders=open_orders),
        stocks=stocks,
        close=close,
        target_weights=pd.Series({"AAA": 0.4, "CCC": 0.3}),
        run_time=run_time,
        settings=strategy_settings(),
    )


def test_preview_rebalances_only_the_difference_and_sells_removed_assets() -> None:
    plan = build_plan()
    targets = {row["ticker"]: row for row in plan["target_weights"]}
    orders = {(row["ticker"], row["side"]): row for row in plan["orders"]}

    assert targets["AAA"]["current_lots"] == 2
    assert targets["AAA"]["target_lots"] == 4
    assert targets["AAA"]["delta_lots"] == 2
    assert orders[("AAA", "buy")]["quantity_lots"] == 2
    assert orders[("BBB", "sell")]["quantity_lots"] == 3
    assert orders[("CCC", "buy")]["quantity_lots"] == 15
    assert plan["summary"]["model_target_positions"] == 2
    assert plan["summary"]["planned_target_positions"] == 2
    assert "RUB000UTSTOM" not in targets
    assert not any(
        "RUB000UTSTOM" in reason for reason in plan["execution"]["blocking_reasons"]
    )
    assert plan["execution"]["ready"] is True
    assert len(plan["plan_id"]) == 64
    assert plan["plan_id"] == build_plan()["plan_id"]


def test_preview_rejects_strategy_that_requires_persisted_live_state() -> None:
    run_time = pd.Timestamp("2026-08-01")

    with pytest.raises(HTTPException, match="persisted position") as error:
        build_preview_payload(
            strategy=UnsupportedLiveStrategy(),
            account_id="acc-1",
            account_overview=account_overview(),
            stocks=[],
            close=pd.DataFrame({"AAA": [10.0]}, index=[run_time]),
            target_weights=pd.Series({"AAA": 0.7}),
            run_time=run_time,
            settings=strategy_settings(),
        )

    assert error.value.status_code == 422


def test_preview_blocks_execution_while_broker_has_open_orders() -> None:
    plan = build_plan(open_orders=2)

    assert plan["execution"]["ready"] is False
    assert "открытые заявки: 2" in plan["execution"]["blocking_reasons"][0]


def test_small_portfolio_explains_why_only_two_of_169_targets_are_feasible() -> None:
    run_time = pd.Timestamp("2026-08-01")
    target_tickers = ["SVET", "SVETP"] + [f"S{index:03d}" for index in range(167)]
    prices = {ticker: 100.0 for ticker in target_tickers}
    prices.update({"SVET": 11.0, "SVETP": 17.15, "TRNFP": 1_106.6})
    stocks = [
        {
            "ticker": ticker,
            "figi": f"figi-{ticker}",
            "uid": f"uid-{ticker}",
            "lot": 1,
            "name": ticker,
        }
        for ticker in prices
    ]
    overview = {
        "summary": {
            "portfolio_value": 3_466.86,
            "open_orders_count": 0,
            "total_amount_portfolio": {"value": 3_466.86, "currency": "rub"},
            "money": [{"value": 2_372.66, "currency": "rub"}],
        },
        "sections": {
            "portfolio": {
                "positions": [
                    {
                        "figi": "figi-TRNFP",
                        "instrument_uid": "uid-TRNFP",
                        "instrument_type": "share",
                        "quantity": {"value": 1.0},
                        "quantity_lots": {"value": 1.0},
                    },
                    {
                        "figi": "RUB000UTSTOM",
                        "instrument_type": "currency",
                        "quantity": {"value": 2_372.66},
                        "quantity_lots": {"value": 2_372.66},
                    },
                ]
            }
        },
    }

    plan = build_preview_payload(
        strategy=StopsStrategy(),
        account_id="acc-1",
        account_overview=overview,
        stocks=stocks,
        close=pd.DataFrame([prices], index=[run_time]),
        target_weights=pd.Series({ticker: 1 / 169 for ticker in target_tickers}),
        run_time=run_time,
        settings=strategy_settings(),
    )

    assert plan["summary"]["model_target_positions"] == 169
    assert plan["summary"]["planned_target_positions"] == 2
    assert plan["summary"]["below_one_lot_target_positions"] == 167
    assert plan["summary"]["minimum_one_lot_cost"] == pytest.approx(16_728.15)
    assert plan["summary"]["estimated_cash_after_orders"] == pytest.approx(3_451.11)
    assert {(row["ticker"], row["side"]) for row in plan["orders"]} == {
        ("TRNFP", "sell"),
        ("SVET", "buy"),
        ("SVETP", "buy"),
    }
    assert len(plan["stop_orders"]) == 4
    assert "167" in plan["execution"]["warnings"][0]
    assert "RUB000UTSTOM" not in {row["ticker"] for row in plan["target_weights"]}


def test_pullback_execution_plan_never_expands_beyond_its_fixed_universe() -> None:
    dates = pd.bdate_range("2026-07-01", periods=15)
    tickers = ["SBER", "TRNFP", "GAZP"]
    price_context = pd.DataFrame(
        [
            {
                "time": timestamp,
                "ticker": ticker,
                "high": 100.0,
                "low": 97.0,
                "close": 98.0,
                "is_complete": True,
            }
            for timestamp in dates
            for ticker in tickers
        ]
    )
    close = pd.DataFrame(
        {ticker: [98.0] * len(dates) for ticker in tickers},
        index=dates,
    )
    strategy = ModelPullbackWithEqStopLoss1TakeProfit3Builder(
        price_context,
        pd.DataFrame(),
    ).build()
    run_time = dates[-1]
    weights, _, _ = _build_order_plan(
        strategy,
        close,
        pd.Index([run_time]),
        trading_start_date=run_time,
    )
    overview = {
        "summary": {
            "portfolio_value": 10_000.0,
            "open_orders_count": 0,
            "total_amount_portfolio": {"value": 10_000.0, "currency": "rub"},
            "money": [{"value": 10_000.0, "currency": "rub"}],
        },
        "sections": {"portfolio": {"positions": []}},
    }
    stocks = [
        {
            "ticker": ticker,
            "figi": f"figi-{ticker}",
            "uid": f"uid-{ticker}",
            "lot": 1,
        }
        for ticker in tickers
    ]

    plan = build_preview_payload(
        strategy=strategy,
        account_id="acc-1",
        account_overview=overview,
        stocks=stocks,
        close=close,
        target_weights=weights.loc[run_time],
        run_time=run_time,
        settings=strategy_settings(),
    )

    assert weights.loc[run_time].to_dict() == {
        "SBER": 0.5,
        "TRNFP": 0.5,
        "GAZP": 0.0,
    }
    assert plan["summary"]["model_target_positions"] == 2
    assert {row["ticker"] for row in plan["target_weights"]} == {
        "SBER",
        "TRNFP",
    }
    assert {row["ticker"] for row in plan["orders"]} == {"SBER", "TRNFP"}
    assert {row["ticker"] for row in plan["stop_orders"]} == {
        "SBER",
        "TRNFP",
    }


def test_cash_buffer_reduces_a_buy_that_cannot_be_safely_funded() -> None:
    run_time = pd.Timestamp("2026-08-01")
    overview = {
        "summary": {
            "portfolio_value": 100.0,
            "open_orders_count": 0,
            "total_amount_portfolio": {"value": 100.0, "currency": "rub"},
            "money": [{"value": 100.0, "currency": "rub"}],
        },
        "sections": {"portfolio": {"positions": []}},
    }

    plan = build_preview_payload(
        strategy=ExampleStrategy(),
        account_id="acc-1",
        account_overview=overview,
        stocks=[{"ticker": "AAA", "figi": "figi-a", "uid": "uid-a", "lot": 1}],
        close=pd.DataFrame([{"AAA": 100.0}], index=[run_time]),
        target_weights=pd.Series({"AAA": 1.0}),
        run_time=run_time,
        settings=strategy_settings(),
    )

    target = plan["target_weights"][0]
    assert target["model_target_lots"] == 1
    assert target["target_lots"] == 0
    assert target["constraint"] == "cash_limited"
    assert plan["summary"]["cash_limited_target_positions"] == 1
    assert plan["summary"]["conservative_cash_after_orders"] == pytest.approx(100.0)
    assert plan["orders"] == []


async def test_strategy_orders_are_idempotent_and_submit_sells_first(
    monkeypatch,
) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    monkeypatch.setenv("EXECUTION_ORDER_SUBMISSION_MODE", "real")
    service = ExecutionService()
    submitted = []

    async def fake_submit(account_id, ticket):
        submitted.append((account_id, ticket))
        return {
            "submitted": True,
            "broker_order_id": ticket.client_order_id,
        }

    monkeypatch.setattr(service, "submit_order", fake_submit)
    plan = build_plan()

    first = await service.execute_strategy_orders(
        account_id="acc-1",
        strategy_name="ExampleStrategy",
        plan=plan,
        requested_by_user_id="user-1",
    )
    second = await service.execute_strategy_orders(
        account_id="acc-1",
        strategy_name="ExampleStrategy",
        plan=plan,
        requested_by_user_id="user-1",
    )

    first_tickets = [ticket for _, ticket in submitted[:3]]
    second_tickets = [ticket for _, ticket in submitted[3:]]
    assert [ticket.side for ticket in first_tickets] == ["sell", "buy", "buy"]
    assert all(ticket.order_type == "market" for ticket in first_tickets)
    assert [ticket.client_order_id for ticket in first_tickets] == [
        ticket.client_order_id for ticket in second_tickets
    ]
    assert first["status"] == "submitted"
    assert second["summary"]["submitted"] == 3


async def test_strategy_execution_skips_buys_after_a_sell_failure(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    service = ExecutionService()
    submitted_sides = []

    async def fake_submit(_account_id, ticket):
        submitted_sides.append(ticket.side)
        if ticket.side == "sell":
            raise HTTPException(status_code=502, detail="broker rejected sell")
        return {"submitted": True}

    monkeypatch.setattr(service, "submit_order", fake_submit)

    result = await service.execute_strategy_orders(
        account_id="acc-1",
        strategy_name="ExampleStrategy",
        plan=build_plan(),
        requested_by_user_id="user-1",
    )

    assert submitted_sides == ["sell"]
    assert result["status"] == "partial"
    assert result["summary"] == {
        "orders": 3,
        "submitted": 0,
        "simulated": 0,
        "failed": 1,
        "skipped": 2,
    }
    assert result["results"][0]["error"] == "broker rejected sell"
    assert all(
        row["error"] == "Buy phase was skipped because at least one sell order failed."
        for row in result["results"][1:]
    )


async def test_strategy_execution_exposes_each_broker_rejection(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    service = ExecutionService()

    async def fake_submit(_account_id, ticket):
        if ticket.side == "buy":
            return {
                "submitted": False,
                "message": f"T-Invest rejected {ticket.instrument_id}: insufficient funds",
            }
        return {"submitted": True, "broker_order_id": "sell-order-1"}

    monkeypatch.setattr(service, "submit_order", fake_submit)

    result = await service.execute_strategy_orders(
        account_id="acc-1",
        strategy_name="ExampleStrategy",
        plan=build_plan(),
        requested_by_user_id="user-1",
    )

    assert result["status"] == "partial"
    assert result["summary"]["failed"] == 2
    errors_by_instrument = {
        row["instrument_id"]: row["error"] for row in result["results"]
    }
    assert errors_by_instrument == {
        "uid-a": "T-Invest rejected uid-a: insufficient funds",
        "uid-b": None,
        "uid-c": "T-Invest rejected uid-c: insufficient funds",
    }


async def test_market_order_availability_is_checked_as_one_batch(monkeypatch) -> None:
    calls: list[list[str]] = []

    class FakeMarketData:
        async def get_trading_statuses(self, *, instrument_ids):
            calls.append(instrument_ids)
            return {
                "trading_statuses": [
                    {
                        "instrument_uid": "uid-a",
                        "api_trade_available_flag": True,
                        "market_order_available_flag": True,
                        "limit_order_available_flag": True,
                    },
                    {
                        "instrument_uid": "uid-b",
                        "api_trade_available_flag": True,
                        "market_order_available_flag": False,
                        "limit_order_available_flag": True,
                    },
                ]
            }

    class FakeAsyncClient:
        def __init__(self, _token):
            self.market_data = FakeMarketData()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setenv("EXECUTION_TINVEST_TOKEN", "token")
    monkeypatch.setattr(service_module, "AsyncClient", FakeAsyncClient)
    service = ExecutionService()

    result = await service.get_market_order_availability(
        [
            {"ticker": "AAA", "instrument_id": "uid-a"},
            {"ticker": "BBB", "instrument_id": "uid-b"},
        ]
    )

    assert calls == [["uid-a", "uid-b"]]
    assert [(row["ticker"], row["available"]) for row in result] == [
        ("AAA", True),
        ("BBB", False),
    ]
    assert result[1]["limit_order_available_flag"] is True


async def test_strategy_execution_rejects_a_stale_preview(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    service = ExecutionService()

    async def fake_preview(*_args, **_kwargs):
        return {"plan_id": "b" * 64, "execution": {"ready": True}}

    monkeypatch.setattr(service, "run_assigned_strategy", fake_preview)
    request = StrategyExecutionRequest(
        plan_id="a" * 64,
        confirmation="execute_market_orders",
        order_type="market",
    )

    with pytest.raises(HTTPException) as error:
        await service.execute_assigned_strategy(
            "acc-1",
            "ExampleStrategy",
            request,
            session=object(),
            authorization="Bearer token",
            requested_by_user_id="user-1",
        )

    assert error.value.status_code == 409
    assert error.value.detail["current_plan_id"] == "b" * 64
