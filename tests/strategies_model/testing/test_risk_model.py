import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from its.strategies.testing.risk_model import (
    calculate_loss_metrics,
    calculate_qae_style_metrics,
    discretize_losses,
    list_risk_models,
    risk_model_definition,
    simulate_portfolio_losses,
    simulate_portfolio_scenarios,
)


def test_risk_model_bootstrap_var_and_cvar_are_reproducible() -> None:
    returns = pd.DataFrame(
        {
            "LOW": [0.01, -0.01, 0.015, -0.005, 0.0],
            "HIGH": [0.03, -0.08, 0.04, -0.05, 0.01],
        },
        index=pd.bdate_range("2024-01-01", periods=5),
    )
    weights = np.array([0.7, 0.3])

    losses = simulate_portfolio_losses(
        returns=returns,
        weights=weights,
        portfolio_value=1_000_000,
        n_simulations=5_000,
        horizon_days=1,
        method="historical_bootstrap",
        random_state=7,
    )
    repeated_losses = simulate_portfolio_losses(
        returns=returns,
        weights=weights,
        portfolio_value=1_000_000,
        n_simulations=5_000,
        horizon_days=1,
        method="historical_bootstrap",
        random_state=7,
    )

    assert np.array_equal(losses, repeated_losses)
    metrics = calculate_loss_metrics(
        losses,
        confidence_level=0.95,
        portfolio_value=1_000_000,
    )
    assert metrics["scenario_count"] == 5_000
    assert metrics["cvar"] >= metrics["var"]
    assert 0 < metrics["tail_probability"] <= 1
    assert metrics["tail_count"] > 0


def test_risk_models_are_grouped_by_engine_with_legacy_aliases() -> None:
    models = list_risk_models()

    assert [item["id"] for item in models] == ["monte_carlo", "qae"]
    assert risk_model_definition("monte_carlo_var")["id"] == "monte_carlo"
    assert risk_model_definition("monte_carlo_cvar")["id"] == "monte_carlo"
    assert risk_model_definition("qae_var")["id"] == "qae"
    assert risk_model_definition("qae_cvar")["id"] == "qae"


def test_risk_model_scenarios_include_portfolio_paths() -> None:
    returns = pd.DataFrame(
        {
            "LOW": [0.01, -0.01, 0.015, -0.005, 0.0],
            "HIGH": [0.03, -0.08, 0.04, -0.05, 0.01],
        },
        index=pd.bdate_range("2024-01-01", periods=5),
    )

    result = simulate_portfolio_scenarios(
        returns=returns,
        weights=np.array([0.7, 0.3]),
        portfolio_value=1_000_000,
        n_simulations=200,
        horizon_days=5,
        method="historical_bootstrap",
        random_state=7,
        path_count=12,
    )

    assert len(result["losses"]) == 200
    assert len(result["simulated_paths"]["paths"]) == 12
    assert len(result["simulated_paths"]["paths"][0]["points"]) == 6
    assert result["simulated_paths"]["paths"][0]["points"][0] == {
        "x": 0,
        "y": 1_000_000.0,
    }


def test_qae_style_metrics_are_discrete_reference_over_loss_buckets() -> None:
    losses = np.array([-10, 0, 20, 30, 40, 60, 90, 120], dtype=float)
    reference = calculate_loss_metrics(
        losses,
        confidence_level=0.75,
        portfolio_value=1_000,
    )

    distribution = discretize_losses(losses, n_buckets=8)
    qae = calculate_qae_style_metrics(
        distribution,
        confidence_level=0.75,
        reference_metrics=reference,
    )

    assert distribution["bucket_count"] == 8
    assert distribution["qubits"] == 3
    assert qae["bucket_count"] == 8
    assert qae["qubits"] == 3
    assert qae["cvar"] >= qae["var"]
    assert qae["target_tail_probability"] == pytest.approx(0.25)


def test_qae_bucket_count_must_be_power_of_two() -> None:
    with pytest.raises(HTTPException):
        discretize_losses(np.array([1.0, 2.0, 3.0]), n_buckets=12)
