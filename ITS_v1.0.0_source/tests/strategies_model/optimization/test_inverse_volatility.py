import warnings

import pandas as pd

from its.strategies.core.optimization import InverseVolatility


def test_inverse_volatility_uses_equal_weight_fallback_for_zero_variance_assets() -> None:
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
