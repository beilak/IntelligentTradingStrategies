import pandas as pd
import pytest
from skfolio.optimization import EqualWeighted
from sklearn.base import clone

from its.strategies.core.optimization import EqualWeightedWithCash


def test_equal_weighted_with_cash_scales_weights_and_preserves_names() -> None:
    returns = pd.DataFrame(
        {
            "AAA": [0.0, 0.01, -0.01],
            "BBB": [0.0, -0.01, 0.01],
        }
    )

    allocator = EqualWeightedWithCash(allocation_pct=0.70).fit(returns)
    portfolio = allocator.predict(returns)

    assert isinstance(allocator, EqualWeighted)
    assert allocator.weights_.tolist() == pytest.approx([0.35, 0.35])
    assert allocator.weights_.sum() == pytest.approx(0.70)
    assert allocator.cash_weight_ == pytest.approx(0.30)
    assert portfolio.weights_dict == pytest.approx({"AAA": 0.35, "BBB": 0.35})


@pytest.mark.parametrize(
    ("allocation_pct", "expected_weight"),
    [(0.0, 0.0), (0.70, 0.70), (1.0, 1.0)],
)
def test_equal_weighted_with_cash_handles_one_asset_and_boundaries(
    allocation_pct: float,
    expected_weight: float,
) -> None:
    returns = pd.DataFrame({"AAA": [0.0, 0.01]})

    allocator = EqualWeightedWithCash(allocation_pct=allocation_pct).fit(returns)
    portfolio = allocator.predict(returns)

    assert allocator.weights_.tolist() == pytest.approx([expected_weight])
    assert allocator.cash_weight_ == pytest.approx(1 - allocation_pct)
    assert portfolio.weights_dict == pytest.approx({"AAA": expected_weight})


def test_equal_weighted_with_cash_is_clone_compatible() -> None:
    allocator = EqualWeightedWithCash(
        allocation_pct=0.65,
        portfolio_params={"name": "cash-aware"},
        raise_on_failure=False,
    )

    cloned = clone(allocator)

    assert cloned.allocation_pct == pytest.approx(0.65)
    assert cloned.portfolio_params == {"name": "cash-aware"}
    assert cloned.raise_on_failure is False


@pytest.mark.parametrize("allocation_pct", [-0.01, 1.01, float("nan")])
def test_equal_weighted_with_cash_rejects_invalid_allocation(
    allocation_pct: float,
) -> None:
    with pytest.raises(ValueError, match="allocation_pct"):
        EqualWeightedWithCash(allocation_pct=allocation_pct).fit(
            pd.DataFrame({"AAA": [0.0, 0.01]})
        )
