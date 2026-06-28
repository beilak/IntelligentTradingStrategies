import pandas as pd
import pytest

from its.strategies.core.signals import CamarillaSupportCrossSignal


def candle_rows(ticker: str, closes: tuple[float, ...]) -> list[dict]:
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return [
        {
            "time": date,
            "ticker": ticker,
            "high": 110.0 if index == 0 else close + 1,
            "low": 90.0 if index == 0 else close - 1,
            "close": close,
            "is_complete": True,
        }
        for index, (date, close) in enumerate(zip(dates, closes, strict=True))
    ]


def test_camarilla_signal_selects_s1_cross_from_below() -> None:
    returns = pd.DataFrame({"CROSSED": [0.0, 0.0, 0.0], "ABOVE": [0.0, 0.0, 0.0]})
    candles = pd.DataFrame(
        candle_rows("CROSSED", (100.0, 98.0, 99.0))
        + candle_rows("ABOVE", (100.0, 99.0, 100.0))
    )

    signal = CamarillaSupportCrossSignal(
        support_line="S1", asset_universe_prices=candles
    ).fit(returns)

    assert signal.to_keep_.tolist() == [True, False]
    assert list(signal.transform(returns).columns) == ["CROSSED"]
    assert signal.support_levels_.loc["CROSSED", "S1"] == pytest.approx(
        100 - 1.1 * 20 / 12
    )
    assert signal.previous_closes_.loc["CROSSED"] == 98.0
    assert signal.current_closes_.loc["CROSSED"] == 99.0


def test_camarilla_signal_support_line_is_configurable() -> None:
    returns = pd.DataFrame({"AAA": [0.0, 0.0, 0.0]})
    candles = pd.DataFrame(candle_rows("AAA", (100.0, 96.0, 97.0)))

    s1 = CamarillaSupportCrossSignal(
        support_line="S1", asset_universe_prices=candles
    ).fit(returns)
    s2 = CamarillaSupportCrossSignal(
        support_line="s2", asset_universe_prices=candles
    ).fit(returns)

    assert s1.to_keep_.tolist() == [False]
    assert s2.to_keep_.tolist() == [True]
    assert s2.selected_support_line_ == "S2"


def test_camarilla_signal_accepts_touching_level_from_below() -> None:
    level = 100 - 1.1 * 20 / 12
    returns = pd.DataFrame({"AAA": [0.0, 0.0, 0.0]})
    candles = pd.DataFrame(candle_rows("AAA", (100.0, 98.0, level)))

    signal = CamarillaSupportCrossSignal(
        support_line="S1", asset_universe_prices=candles
    ).fit(returns)

    assert signal.to_keep_.tolist() == [True]


def test_camarilla_signal_ignores_short_history_and_incomplete_future() -> None:
    returns = pd.DataFrame({"COMPLETE": [0.0, 0.0, 0.0], "SHORT": [0.0, 0.0, 0.0]})
    rows = candle_rows("COMPLETE", (100.0, 98.0, 99.0))
    rows.append(
        {
            "time": "2024-01-04",
            "ticker": "COMPLETE",
            "high": 1000.0,
            "low": 1.0,
            "close": 1.0,
            "is_complete": False,
        }
    )
    rows.extend(candle_rows("SHORT", (100.0, 99.0)))

    signal = CamarillaSupportCrossSignal(
        support_line="S1", asset_universe_prices=pd.DataFrame(rows)
    ).fit(returns)

    assert signal.to_keep_.tolist() == [True, False]
    assert signal.bars_used_.to_dict() == {"COMPLETE": 3, "SHORT": 2}


def test_camarilla_signal_validates_configuration_and_columns() -> None:
    returns = pd.DataFrame({"AAA": [0.0, 0.0, 0.0]})
    with pytest.raises(ValueError, match="support_line"):
        CamarillaSupportCrossSignal(support_line="S5").fit(returns)
    with pytest.raises(ValueError, match="camarilla_multiplier"):
        CamarillaSupportCrossSignal(camarilla_multiplier=0).fit(returns)
    with pytest.raises(ValueError, match="asset_universe_prices"):
        CamarillaSupportCrossSignal().fit(returns)
    with pytest.raises(ValueError, match="low"):
        CamarillaSupportCrossSignal(
            asset_universe_prices=pd.DataFrame(
                {"time": [], "ticker": [], "high": [], "close": []}
            )
        ).fit(returns)
