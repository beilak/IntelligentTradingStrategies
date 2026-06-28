import warnings

import pandas as pd
import pytest

from its.strategies.core.optimization import InverseVolatility


def test_inverse_volatility_uses_equal_weight_fallback_for_zero_variance_assets() -> (
    None
):
    returns = pd.DataFrame(
        {
            "BTBR": [0.0, 0.0, 0.0, 0.0],
            "HHRU": [0.0, 0.0, 0.0, 0.0],
        }
    )

    allocator = InverseVolatility(raise_on_failure=False)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        allocator.fit(returns)

    assert caught_warnings == []
    assert allocator.weights_.tolist() == [0.5, 0.5]


def test_inverse_volatility_does_not_repair_singular_covariance() -> None:
    returns = pd.DataFrame(
        {
            "AAA": [0.01, 0.02, -0.01, 0.00, 0.01],
            "BBB": [0.02, 0.04, -0.02, 0.00, 0.02],
        }
    )

    allocator = InverseVolatility()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        allocator.fit(returns)

    assert caught_warnings == []
    assert allocator.weights_[0] == pytest.approx(2 / 3)
    assert allocator.weights_[1] == pytest.approx(1 / 3)
