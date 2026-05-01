import numpy as np
import pandas as pd

from its.strategies.core.optimization import CVaR, CVaRHighRisk


def test_cvar_allocator_preserves_dataframe_columns_in_prediction() -> None:
    returns = pd.DataFrame(
        {
            "LOW_RISK": [0.01, 0.01, -0.01, 0.01, 0.0],
            "HIGH_RISK": [0.03, -0.2, 0.04, -0.15, 0.02],
        },
        index=pd.bdate_range("2024-01-01", periods=5),
    )

    allocator = CVaR(beta=0.8).fit(returns)
    portfolio = allocator.predict(returns)

    assert np.isclose(allocator.weights_.sum(), 1.0)
    assert set(portfolio.weights_dict) == {"LOW_RISK", "HIGH_RISK"}
    assert portfolio.weights_dict["LOW_RISK"] > portfolio.weights_dict["HIGH_RISK"]


def test_cvar_allocator_ignores_all_nan_asset() -> None:
    returns = pd.DataFrame(
        {
            "VALID": [0.01, -0.02, 0.01, -0.01],
            "EMPTY": [np.nan, np.nan, np.nan, np.nan],
        },
        index=pd.bdate_range("2024-01-01", periods=4),
    )

    allocator = CVaR(beta=0.75).fit(returns)

    assert np.isclose(allocator.weights_.sum(), 1.0)
    assert allocator.weights_[0] == 1.0
    assert allocator.weights_[1] == 0.0


def test_cvar_high_risk_allocator_gives_more_weight_to_higher_cvar() -> None:
    returns = pd.DataFrame(
        {
            "LOW_RISK": [0.01, 0.01, -0.01, 0.01, 0.0],
            "HIGH_RISK": [0.03, -0.2, 0.04, -0.15, 0.02],
        },
        index=pd.bdate_range("2024-01-01", periods=5),
    )

    inverse_allocator = CVaR(beta=0.8).fit(returns)
    high_risk_allocator = CVaRHighRisk(beta=0.8).fit(returns)
    portfolio = high_risk_allocator.predict(returns)

    assert np.isclose(high_risk_allocator.weights_.sum(), 1.0)
    assert set(portfolio.weights_dict) == {"LOW_RISK", "HIGH_RISK"}
    assert portfolio.weights_dict["HIGH_RISK"] > portfolio.weights_dict["LOW_RISK"]
    assert inverse_allocator.weights_[0] > inverse_allocator.weights_[1]
    assert high_risk_allocator.weights_[1] > high_risk_allocator.weights_[0]
