import numpy as np
import pandas as pd

from its.strategies.core.optimization import CQMAllocator


def test_cqm_allocator_solves_feasible_discrete_allocation() -> None:
    returns = pd.DataFrame(
        {
            "LOW_ALPHA": [0.001, 0.002, 0.001, 0.002],
            "HIGH_ALPHA": [0.003, 0.004, 0.003, 0.004],
        },
        index=pd.bdate_range("2024-01-01", periods=4),
    )

    allocator = CQMAllocator(
        alpha_scores=pd.Series({"HIGH_ALPHA": 0.05, "LOW_ALPHA": 0.01}),
        covariance_matrix=pd.DataFrame(
            np.zeros((2, 2)),
            index=["HIGH_ALPHA", "LOW_ALPHA"],
            columns=["HIGH_ALPHA", "LOW_ALPHA"],
        ),
        max_weight=0.6,
        weight_unit=0.1,
        risk_weight=0.0,
        deviation_weight=0.0,
        concentration_weight=0.0,
    ).fit(returns)
    portfolio = allocator.predict(returns)

    assert allocator.feasible_ is True
    assert allocator.weight_units_.tolist() == [4, 6]
    assert np.allclose(allocator.weights_, [0.4, 0.6])
    assert allocator.target_weights_.tolist() == allocator.weights_.tolist()
    assert allocator.diagnostics_["feasible"] is True
    assert allocator.diagnostics_["fallback_used"] is False
    assert allocator.diagnostics_["constraints"]["budget_weight_units"] == 10
    assert allocator.cqm_.upper_bound("w_1") == 6
    assert "budget" in allocator.cqm_.constraints
    assert set(portfolio.weights_dict) == {"LOW_ALPHA", "HIGH_ALPHA"}
    assert np.isclose(portfolio.weights_dict["HIGH_ALPHA"], 0.6)


def test_cqm_allocator_uses_fallback_when_constraints_are_infeasible() -> None:
    returns = pd.DataFrame(
        {
            "A": [0.01, 0.02, 0.01],
            "B": [0.02, 0.03, 0.02],
        }
    )

    allocator = CQMAllocator(
        max_weight=0.4,
        weight_unit=0.1,
    ).fit(returns)

    assert allocator.feasible_ is False
    assert allocator.fallback_ is not None
    assert np.allclose(allocator.weights_, [0.5, 0.5])
    assert allocator.target_weights_.tolist() == allocator.weights_.tolist()
    assert allocator.diagnostics_["fallback_used"] is True
    assert "infeasible" in allocator.diagnostics_["fallback_reason"]


def test_cqm_allocator_can_penalize_deviation_from_previous_weights() -> None:
    returns = pd.DataFrame(
        {
            "CURRENT_HEAVY": [0.01, 0.01, 0.01],
            "HIGH_ALPHA": [0.02, 0.02, 0.02],
        }
    )

    allocator = CQMAllocator(
        alpha_scores={"CURRENT_HEAVY": 0.0, "HIGH_ALPHA": 1.0},
        covariance_matrix=np.zeros((2, 2)),
        previous_weights={"CURRENT_HEAVY": 0.8, "HIGH_ALPHA": 0.2},
        weight_unit=0.1,
        risk_weight=0.0,
        deviation_weight=10.0,
        concentration_weight=0.0,
    ).fit(returns)

    assert allocator.needs_previous_weights is True
    assert allocator.feasible_ is True
    assert np.allclose(allocator.weights_, [0.8, 0.2])
    assert allocator.diagnostics_["objective_components"]["deviation"] == 0.0
