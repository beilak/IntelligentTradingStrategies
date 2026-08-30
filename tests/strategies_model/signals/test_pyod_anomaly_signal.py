import numpy as np
import pandas as pd
import pytest

from its.strategies.core.signals import PyODAnomalySignal

DEFAULT_LOOKBACK = 20
SERIES_LENGTH = 30


def build_context(
    close_series: dict[str, np.ndarray],
    *,
    volume: float = 1_000_000.0,
) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=len(next(iter(close_series.values()))))
    rows = []
    for index, date in enumerate(dates):
        for ticker, closes in close_series.items():
            close = closes[index]
            rows.append(
                {
                    "time": date,
                    "ticker": ticker,
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": volume,
                    "is_complete": True,
                }
            )
    return pd.DataFrame(rows)


def make_series(returns: np.ndarray, start: float = 100.0) -> np.ndarray:
    return start * np.concatenate(([1.0], np.cumprod(1.0 + returns)))


def returns_matrix(universe: dict[str, np.ndarray]) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=len(next(iter(universe.values()))))
    return pd.DataFrame(
        {
            ticker: np.concatenate(([np.nan], np.diff(closes) / closes[:-1]))
            for ticker, closes in universe.items()
        },
        index=dates,
    )


def build_default_universe() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, 0.003, SERIES_LENGTH)
    tiny_up = rng.normal(0.001, 0.003, SERIES_LENGTH)

    spike_returns = noise.copy()
    spike_returns[-1] = 0.10
    drop_returns = noise.copy()
    drop_returns[-1] = -0.10
    flat_returns = tiny_up.copy()
    flat_returns[-1] = 0.0

    return {
        "SPIKE": make_series(spike_returns),
        "FLAT": make_series(flat_returns),
        "DROP": make_series(drop_returns),
    }


def fit_signal(universe, context=None, matrix=None, **kwargs):
    context = context if context is not None else build_context(universe)
    matrix = matrix if matrix is not None else returns_matrix(universe)
    return PyODAnomalySignal(
        asset_universe_prices=context,
        **{"lookback_bars": DEFAULT_LOOKBACK, **kwargs},
    ).fit(matrix)


def test_pyod_anomaly_signal_selects_only_positive_anomalies() -> None:
    universe = build_default_universe()
    signal = fit_signal(universe)

    assert signal.to_keep_.tolist() == [True, False, False]
    assert list(signal.transform(returns_matrix(universe)).columns) == ["SPIKE"]
    assert signal.latest_return_.loc["SPIKE"] == pytest.approx(0.10)
    assert bool(signal.labels_.at["SPIKE"]) is True
    assert signal.scores_.loc["SPIKE"] > signal.fitted_detectors_["SPIKE"].threshold_
    assert signal.bars_used_.loc["SPIKE"] == DEFAULT_LOOKBACK


def test_pyod_anomaly_signal_direction_gates() -> None:
    universe = build_default_universe()
    context = build_context(universe)
    matrix = returns_matrix(universe)

    negative = fit_signal(universe, context=context, matrix=matrix, direction="negative")
    assert negative.to_keep_.tolist() == [False, False, True]

    either = fit_signal(universe, context=context, matrix=matrix, direction="either")
    assert either.to_keep_.tolist() == [True, False, True]


def test_pyod_anomaly_signal_returns_all_false_mask_without_anomaly() -> None:
    rng = np.random.default_rng(7)
    universe = {
        ticker: make_series(rng.normal(0.0, 0.003, SERIES_LENGTH))
        for ticker in ("AAA", "BBB")
    }
    signal = fit_signal(universe)

    assert not signal.to_keep_.any()
    assert signal.transform(returns_matrix(universe)).empty


def test_pyod_anomaly_signal_ignores_insufficient_history() -> None:
    universe = {
        "SHORT": make_series(np.zeros(10), start=100.0),
        "SPIKE": make_series(np.array([0.1] * 5 + [0.0] * 5), start=100.0),
    }
    signal = fit_signal(universe)

    assert not signal.to_keep_.any()
    assert signal.bars_used_.loc["SHORT"] < DEFAULT_LOOKBACK
    assert signal.bars_used_.loc["SPIKE"] < DEFAULT_LOOKBACK


def test_pyod_anomaly_signal_lookahead_does_not_change_decision() -> None:
    universe = build_default_universe()
    train_end = pd.bdate_range("2024-01-01", periods=SERIES_LENGTH)[SERIES_LENGTH - 1]
    matrix = returns_matrix(universe)

    def refit(prices: pd.DataFrame) -> PyODAnomalySignal:
        truncated = prices.loc[prices["time"] <= train_end]
        return PyODAnomalySignal(
            lookback_bars=DEFAULT_LOOKBACK,
            direction="positive",
            asset_universe_prices=truncated,
        ).fit(matrix.loc[:train_end])

    first = refit(build_context(universe))
    score_before = first.scores_.loc["SPIKE"]
    keep_before = first.to_keep_.tolist()

    extended = build_context(
        {
            ticker: np.concatenate((closes, np.full(5, closes[-1])))
            for ticker, closes in universe.items()
        }
    )
    second = refit(extended)

    assert second.to_keep_.tolist() == keep_before
    assert second.scores_.to_numpy() == pytest.approx(first.scores_.to_numpy(), nan_ok=True)
    assert second.scores_.loc["SPIKE"] == pytest.approx(score_before)


def test_pyod_anomaly_signal_moves_with_the_latest_bar() -> None:
    universe = build_default_universe()
    on_spike = fit_signal(universe)
    assert on_spike.to_keep_.argmax() == 0

    shifted_universe = {
        ticker: np.concatenate((closes, np.full(3, closes[-1])))
        for ticker, closes in universe.items()
    }
    shifted = build_context(shifted_universe)
    after_spike = fit_signal(
        universe,
        context=shifted,
        matrix=returns_matrix(shifted_universe),
    )

    assert not after_spike.to_keep_.any()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"lookback_bars": 3}, "lookback_bars"),
        ({"direction": "up"}, "direction"),
        ({"feature_columns": ("bogus",)}, "feature_columns"),
        ({"feature_columns": ()}, "feature_columns"),
    ],
)
def test_pyod_anomaly_signal_validates_parameters(kwargs, message) -> None:
    universe = build_default_universe()
    with pytest.raises(ValueError, match=message):
        fit_signal(universe, **kwargs)


def test_pyod_anomaly_signal_requires_context() -> None:
    with pytest.raises(ValueError, match="asset_universe_prices is required"):
        PyODAnomalySignal().fit(pd.DataFrame({"AAA": [0.0] * SERIES_LENGTH}))


def test_pyod_anomaly_signal_reports_missing_columns() -> None:
    universe = build_default_universe()
    context = build_context(universe).drop(columns=["volume"])
    with pytest.raises(ValueError, match="volume"):
        fit_signal(universe, context=context)