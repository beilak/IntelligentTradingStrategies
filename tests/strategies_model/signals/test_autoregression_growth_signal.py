import numpy as np
import pandas as pd
import pytest

from its.strategies.core.signals import AutoRegressionGrowthSignal


def test_autoregression_growth_signal_selects_required_forecast_growth() -> None:
    rng = np.random.default_rng(42)
    observations = 80
    returns = pd.DataFrame(
        {
            "GROWTH": 0.02 + rng.normal(0, 0.0005, observations),
            "DECLINE": -0.01 + rng.normal(0, 0.0005, observations),
            "SHORT": [np.nan] * 30
            + list(0.03 + rng.normal(0, 0.0005, observations - 30)),
        }
    )

    signal = AutoRegressionGrowthSignal(
        lookback_bars=60,
        lags=3,
        forecast_bars=1,
        min_growth_pct=0.01,
        n_jobs=2,
    ).fit(returns)

    assert signal.to_keep_.tolist() == [True, False, False]
    assert list(signal.transform(returns).columns) == ["GROWTH"]
    assert signal.predicted_growth_.loc["GROWTH"] >= 0.01
    assert signal.observations_used_.loc["GROWTH"] == 60


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"lookback_bars": 2}, "lookback_bars"),
        ({"lookback_bars": 10, "lags": 9}, "lags"),
        ({"forecast_bars": 0}, "forecast_bars"),
        ({"min_growth_pct": float("nan")}, "min_growth_pct"),
        ({"n_jobs": 0}, "n_jobs"),
    ],
)
def test_autoregression_growth_signal_validates_parameters(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        AutoRegressionGrowthSignal(**kwargs).fit(pd.DataFrame({"AAA": [0.0] * 80}))
