import json
from types import SimpleNamespace

import pandas as pd
import pytest
import vectorbt as vbt

from its.strategies.testing.backtest.core import build_backtest_pnl_source


def test_backtest_pnl_source_reconciles_to_portfolio_value() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 105.0],
            "BBB": [50.0, 55.0, 60.0],
        },
        index=index,
    )
    weights = pd.DataFrame(
        [[0.5, 0.5], [None, None], [0.0, 1.0]],
        index=index,
        columns=prices.columns,
    )
    portfolio = vbt.Portfolio.from_orders(
        prices,
        size=weights,
        size_type="targetpercent",
        init_cash=1_000.0,
        fees=0.001,
        cash_sharing=True,
        group_by=True,
        freq="1D",
    )

    source = build_backtest_pnl_source(
        backtest_result=SimpleNamespace(
            portfolio=portfolio,
            order_prices=prices,
        ),
        settings={"init_cash": 1_000.0},
    )

    total_contribution = sum(
        value
        for day in source["daily_asset_pnl"]
        for value in day["contributions"].values()
    )
    assert 1_000.0 + total_contribution == pytest.approx(
        float(portfolio.value().iloc[-1])
    )
    assert len(source["orders"]) == 4
    assert sum(item["fees"] for item in source["orders"]) == pytest.approx(
        float(portfolio.orders.fees.sum())
    )
    assert set(source["daily_asset_pnl"][0]["contributions"]) == {
        "AAA",
        "BBB",
    }
    assert source["external_flows"] is False
    assert source["taxes_applied"] is False
    json.dumps(source, allow_nan=False)


def test_backtest_pnl_source_marks_closed_and_open_trades() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 105.0]}, index=index)
    weights = pd.DataFrame([[1.0], [None], [0.0]], index=index, columns=["AAA"])
    portfolio = vbt.Portfolio.from_orders(
        prices,
        size=weights,
        size_type="targetpercent",
        init_cash=1_000.0,
        cash_sharing=True,
        group_by=True,
        freq="1D",
    )

    source = build_backtest_pnl_source(
        backtest_result=SimpleNamespace(
            portfolio=portfolio,
            order_prices=prices,
        ),
        settings={"init_cash": 1_000.0},
    )

    assert [trade["status"] for trade in source["trades"]] == ["closed"]
    assert source["trades"][0]["pnl"] == pytest.approx(50.0)
