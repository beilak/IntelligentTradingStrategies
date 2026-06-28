import pandas as pd

from its.strategies.core.types.strategy_types import Strategy
from its.strategies.testing.backtest import core


class FakeModelBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def build(self) -> Strategy:
        return Strategy(
            name="fake_strategy",
            description="Fake strategy.",
            pipeline=object(),
        )


def test_generate_backtest_report_normalizes_naive_start_date_to_price_timezone(
    monkeypatch,
) -> None:
    captured: dict[str, pd.Timestamp] = {}

    def fake_backtest_strategies_vectorbt(*args, **kwargs):
        captured["trading_start_date"] = kwargs["trading_start_date"]
        return {"fake_strategy": object()}

    def fake_build_backtest_payload(**kwargs):
        return {
            "trading_start_date": captured["trading_start_date"],
            "settings": kwargs["settings"],
        }

    monkeypatch.setattr(
        core, "load_registered_model", lambda model_name: FakeModelBuilder
    )
    monkeypatch.setattr(
        core,
        "backtest_strategies_vectorbt",
        fake_backtest_strategies_vectorbt,
    )
    monkeypatch.setattr(core, "build_backtest_payload", fake_build_backtest_payload)

    prices = pd.DataFrame(
        {
            "time": ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
            "ticker": ["AAA", "AAA"],
            "close": [100, 101],
        }
    )

    report = core.generate_backtest_report(
        model_name="FakeModelBuilder",
        stocks=[{"ticker": "AAA", "figi": "figi-aaa"}],
        prices=prices,
        settings={
            "start_date": "2024-01-01",
            "trading_start_date": "2024-01-01",
            "rebalance_freq": "3ME",
            "rebalance_on": "last",
            "fees": 0.0008,
            "slippage": 0.0,
            "freq": "1D",
            "init_cash": 1_000_000.0,
        },
    )

    assert report["trading_start_date"] == pd.Timestamp("2024-01-01", tz="UTC")


def test_normalize_timestamp_for_index_strips_timezone_for_naive_price_index() -> None:
    index = pd.date_range("2024-01-01", periods=2)

    timestamp = core.normalize_timestamp_for_index("2024-01-01T00:00:00Z", index)

    assert timestamp == pd.Timestamp("2024-01-01")
    assert timestamp.tzinfo is None
