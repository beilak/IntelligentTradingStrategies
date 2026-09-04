import numpy as np
import pandas as pd
import pytest

from its.strategies.core.signals import LongOnlyCrossSectionalMomentumSignal


def momentum_rows(
    ticker: str,
    closes: list[float],
    *,
    is_complete: bool = True,
) -> list[dict]:
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return [
        {
            "time": date,
            "ticker": ticker,
            "close": close,
            "is_complete": is_complete,
        }
        for date, close in zip(dates, closes, strict=True)
    ]


def build_signal(context: pd.DataFrame, *, top_n: int = 2, **kwargs):
    n = len(context)
    columns = list(dict.fromkeys(context["ticker"].astype(str).tolist()))
    returns = pd.DataFrame(0.0, index=range(max(n, 6)), columns=columns)
    signal = LongOnlyCrossSectionalMomentumSignal(
        asset_universe_prices=context,
        lookback_days=3,
        skip_last_days=1,
        top_n=top_n,
        **kwargs,
    ).fit(returns)
    return signal, returns


def test_momentum_signal_selects_top_n_and_preserves_column_order() -> None:
    context = pd.DataFrame(
        momentum_rows("FAST", [100, 100, 200, 200, 300, 400, 400, 400])
        + momentum_rows("MID", [100, 100, 100, 150, 150, 150, 200, 200])
        + momentum_rows("SLOW", [100, 100, 100, 100, 105, 105, 110, 112])
        + momentum_rows("FLAT", [100] * 8)
    )

    signal, returns = build_signal(context)

    assert signal.to_keep_.tolist() == [True, True, False, False]
    assert list(signal.transform(returns).columns) == ["FAST", "MID"]
    assert signal.selected_assets_.tolist() == ["FAST", "MID"]
    assert signal.ranking_.loc["FAST"] == 1
    assert signal.ranking_.loc["MID"] == 2
    assert signal.momentum_scores_.loc["FAST"] == pytest.approx(1.0)
    assert signal.momentum_scores_.loc["FLAT"] == pytest.approx(0.0)
    assert signal.ranking_.loc["FLAT"] == 4


def test_momentum_signal_keeps_negative_momentum_asset_within_top_n() -> None:
    context = pd.DataFrame(
        momentum_rows("P_MILD", [100, 100, 100, 100, 101, 102])
        + momentum_rows("NEG", [100, 100, 100, 100, 99, 99])
        + momentum_rows("VERY_NEG", [100, 100, 100, 100, 98, 98])
    )

    signal, _ = build_signal(context)

    assert signal.momentum_scores_.loc["P_MILD"] == pytest.approx(0.01)
    assert signal.momentum_scores_.loc["NEG"] == pytest.approx(-0.01)
    assert signal.momentum_scores_.loc["VERY_NEG"] == pytest.approx(-0.02)
    assert "NEG" in signal.selected_assets_.tolist()
    assert signal.ranking_.loc["P_MILD"] == 1
    assert signal.ranking_.loc["NEG"] == 2
    assert signal.ranking_.loc["VERY_NEG"] == 3
    assert signal.exclusion_reasons_.loc["VERY_NEG"] == "below_top_n"


def test_momentum_signal_excludes_insufficient_history() -> None:
    context = pd.DataFrame(
        momentum_rows("ENOUGH", [100, 100, 200, 200, 300, 400])
        + momentum_rows("SHORT", [100, 110, 120])
    )

    signal, _ = build_signal(context)

    assert signal.to_keep_.tolist() == [True, False]
    assert signal.exclusion_reasons_.loc["SHORT"] == "insufficient_history"
    assert np.isnan(signal.momentum_scores_.loc["SHORT"])
    assert signal.observations_used_.loc["SHORT"] == 3


def test_momentum_signal_tie_break_is_deterministic() -> None:
    context = pd.DataFrame(
        momentum_rows("B", [100, 100, 100, 200, 200, 200])
        + momentum_rows("A", [100, 100, 100, 200, 200, 200])
        + momentum_rows("C", [100, 100, 100, 100, 100, 100])
    )

    signal, _ = build_signal(context, top_n=1)

    assert signal.selected_assets_.tolist() == ["A"]
    assert signal.ranking_.loc["A"] == 1
    assert signal.ranking_.loc["B"] == 2


def test_momentum_signal_keeps_exactly_top_n_and_excludes_rest() -> None:
    context = pd.DataFrame(
        momentum_rows("P1", [100, 110, 120, 130, 140, 150, 160])
        + momentum_rows("P2", [100, 105, 110, 115, 120, 125, 130])
        + momentum_rows("P3", [100, 103, 106, 109, 112, 115, 118])
    )

    signal, _ = build_signal(context, top_n=1)

    assert signal.to_keep_.tolist() == [True, False, False]
    assert signal.ranking_.loc["P2"] == 2
    assert signal.exclusion_reasons_.loc["P2"] == "below_top_n"
    assert signal.exclusion_reasons_.loc["P1"] == ""


def test_momentum_signal_allows_empty_selection() -> None:
    context = pd.DataFrame(momentum_rows("AAA", [100, 110, 120]))

    returns = pd.DataFrame({"AAA": [0.0] * 6})
    signal = LongOnlyCrossSectionalMomentumSignal(
        asset_universe_prices=context,
        lookback_days=3,
        skip_last_days=1,
        top_n=2,
    ).fit(returns)

    assert signal.to_keep_.tolist() == [False]
    assert not signal.to_keep_.any()


def test_momentum_signal_ignores_incomplete_and_incorrect_candles() -> None:
    rows = momentum_rows("GOOD", [100, 100, 200, 200, 300, 400])
    rows += momentum_rows("BAD", [100, 100, 200, 200, 300, 400], is_complete=False)
    rows += [
        {
            "time": pd.Timestamp("2024-01-03"),
            "ticker": "GOOD",
            "close": -5.0,
            "is_complete": True,
        }
    ]
    context = pd.DataFrame(rows)

    signal, _ = build_signal(context)

    assert signal.exclusion_reasons_.loc["BAD"] == "insufficient_history"


def test_momentum_signal_validates_parameters_and_columns() -> None:
    returns = pd.DataFrame({"AAA": [0.0]})
    with pytest.raises(ValueError, match="lookback_days"):
        LongOnlyCrossSectionalMomentumSignal(lookback_days=0).fit(returns)
    with pytest.raises(ValueError, match="skip_last_days"):
        LongOnlyCrossSectionalMomentumSignal(skip_last_days=-1).fit(returns)
    with pytest.raises(ValueError, match="top_n"):
        LongOnlyCrossSectionalMomentumSignal(top_n=0).fit(returns)
    with pytest.raises(ValueError, match="asset_universe_prices is required"):
        LongOnlyCrossSectionalMomentumSignal().fit(returns)
    with pytest.raises(ValueError, match="close"):
        LongOnlyCrossSectionalMomentumSignal(
            asset_universe_prices=pd.DataFrame({"time": [], "ticker": []})
        ).fit(returns)


def test_momentum_signal_is_unchanged_when_future_is_truncated() -> None:
    base = pd.DataFrame(momentum_rows("FAST", [100, 100, 200, 200, 300, 400]))
    decision_time = pd.Timestamp("2024-01-06")
    future = pd.concat(
        [
            base,
            pd.DataFrame(momentum_rows("FAST", [1_000, 5_000])).assign(
                time=pd.date_range("2024-01-07", periods=2, freq="D")
            ),
        ],
        ignore_index=True,
    )
    baseline, _ = build_signal(base)
    repeated, _ = build_signal(future.loc[future["time"] <= decision_time])

    assert repeated.to_keep_.tolist() == baseline.to_keep_.tolist()
    assert repeated.momentum_scores_.equals(baseline.momentum_scores_)
    assert repeated.formation_intervals_.equals(baseline.formation_intervals_)
