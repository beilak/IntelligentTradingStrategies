from __future__ import annotations

from typing import Any

from skfolio import RiskMeasure
from skfolio.optimization import (
    HierarchicalEqualRiskContribution as SkfolioHierarchicalEqualRiskContribution,
)
from skfolio.optimization import MaximumDiversification as SkfolioMaximumDiversification
from skfolio.optimization import MeanRisk, ObjectiveFunction, RiskBudgeting
from skfolio.optimization import (
    NestedClustersOptimization as SkfolioNestedClustersOptimization,
)


class MinimumVarianceAllocator(MeanRisk):
    """Portfolio whose variance is minimized over the chosen assets.

    This is a classic mean-variance optimizer with no expected-return target:
    it minimizes the portfolio variance subject to a full-investment budget and
    long-only bounds. It does not require a return forecast but does rely on the
    estimated covariance matrix.
    """

    def __init__(
        self,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        budget: float | None = 1.0,
        min_budget: float | None = None,
        max_budget: float | None = None,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.budget = budget
        self.min_budget = min_budget
        self.max_budget = max_budget
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            objective_function=ObjectiveFunction.MINIMIZE_RISK,
            risk_measure=RiskMeasure.VARIANCE,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            budget=budget,
            min_budget=min_budget,
            max_budget=max_budget,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class MaximumSharpeAllocator(MeanRisk):
    """Weights that maximize the portfolio Sharpe-like ratio.

    The objective is to maximize the ratio of expected portfolio return to its
    volatility, trading off expected returns against covariance risk. Requires
    an estimate of expected returns and the covariance matrix.
    """

    def __init__(
        self,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        budget: float | None = 1.0,
        min_budget: float | None = None,
        max_budget: float | None = None,
        risk_free_rate: float = 0.0,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.budget = budget
        self.min_budget = min_budget
        self.max_budget = max_budget
        self.risk_free_rate = risk_free_rate
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            objective_function=ObjectiveFunction.MAXIMIZE_RATIO,
            risk_measure=RiskMeasure.VARIANCE,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            budget=budget,
            min_budget=min_budget,
            max_budget=max_budget,
            risk_free_rate=risk_free_rate,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class MaximumReturnAllocator(MeanRisk):
    """Weights that maximize expected portfolio return under the given bounds.

    Risk is only accounted for through explicit constraints when they are
    provided; by itself this optimizer concentrates weight in the assets with
    the highest expected return.
    """

    def __init__(
        self,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        budget: float | None = 1.0,
        min_budget: float | None = None,
        max_budget: float | None = None,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.budget = budget
        self.min_budget = min_budget
        self.max_budget = max_budget
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            objective_function=ObjectiveFunction.MAXIMIZE_RETURN,
            risk_measure=RiskMeasure.VARIANCE,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            budget=budget,
            min_budget=min_budget,
            max_budget=max_budget,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class EqualRiskContributionAllocator(RiskBudgeting):
    """Weights such that every asset contributes roughly equally to portfolio risk.

    Achieved through variance-based risk budgeting with an equal risk budget per
    asset, accounting for both individual volatilities and their covariances.
    This is distinct from a naive inverse-volatility weighting.
    """

    def __init__(
        self,
        risk_budget: Any | None = None,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.risk_budget = risk_budget
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            risk_measure=RiskMeasure.VARIANCE,
            risk_budget=risk_budget,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class MinimumCVaRAllocator(MeanRisk):
    """Weights that minimize the portfolio Conditional Value-at-Risk.

    A classic CVaR-optimization formulation: the objective is to minimize CVaR
    at the chosen confidence level under full-investment and long-only bounds.
    This is a standard mean-risk optimizer, not the inverse-CVaR heuristic of
    the existing :class:`its.strategies.core.optimization.CVaR`.
    """

    def __init__(
        self,
        cvar_beta: float = 0.95,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        budget: float | None = 1.0,
        min_budget: float | None = None,
        max_budget: float | None = None,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.cvar_beta = cvar_beta
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.budget = budget
        self.min_budget = min_budget
        self.max_budget = max_budget
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            objective_function=ObjectiveFunction.MINIMIZE_RISK,
            risk_measure=RiskMeasure.CVAR,
            cvar_beta=cvar_beta,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            budget=budget,
            min_budget=min_budget,
            max_budget=max_budget,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class MeanCVaRAllocator(MeanRisk):
    """Weights balancing expected return against Conditional Value-at-Risk.

    Uses a mean-risk ratio objective (maximize expected return over CVaR) so that
    both return and tail risk are considered. Requires a return/risk trade-off
    parameter, in contrast to pure CVaR minimization.
    """

    def __init__(
        self,
        cvar_beta: float = 0.95,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        budget: float | None = 1.0,
        min_budget: float | None = None,
        max_budget: float | None = None,
        risk_free_rate: float = 0.0,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.cvar_beta = cvar_beta
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.budget = budget
        self.min_budget = min_budget
        self.max_budget = max_budget
        self.risk_free_rate = risk_free_rate
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            objective_function=ObjectiveFunction.MAXIMIZE_RATIO,
            risk_measure=RiskMeasure.CVAR,
            cvar_beta=cvar_beta,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            budget=budget,
            min_budget=min_budget,
            max_budget=max_budget,
            risk_free_rate=risk_free_rate,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class CVaRRiskParityAllocator(RiskBudgeting):
    """Risk-parity allocation where each asset's risk is measured via CVaR.

    Weights are chosen so that every asset contributes roughly equally to the
    portfolio tail risk, as opposed to the variance-based equal risk
    contribution. This spreads tail risk evenly across the components.
    """

    def __init__(
        self,
        risk_budget: Any | None = None,
        cvar_beta: float = 0.95,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        solver: str = "CLARABEL",
        solver_params: dict | None = None,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.risk_budget = risk_budget
        self.cvar_beta = cvar_beta
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.solver = solver
        self.solver_params = solver_params
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            risk_measure=RiskMeasure.CVAR,
            risk_budget=risk_budget,
            cvar_beta=cvar_beta,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            solver=solver,
            solver_params=solver_params,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class MaximumDiversificationAllocator(SkfolioMaximumDiversification):
    """Weights that maximize the portfolio diversification ratio.

    Compares the weighted average of individual asset volatilities against the
    total portfolio volatility, seeking the most efficiently diversified
    portfolio without inverting the covariance matrix directly.
    """

    def __init__(
        self,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        budget: float | None = 1.0,
        min_budget: float | None = None,
        max_budget: float | None = None,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.budget = budget
        self.min_budget = min_budget
        self.max_budget = max_budget
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            budget=budget,
            min_budget=min_budget,
            max_budget=max_budget,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class HierarchicalEqualRiskContributionAllocator(
    SkfolioHierarchicalEqualRiskContribution
):
    """Hierarchical equal risk contribution allocation.

    Assets are grouped by their correlation structure, then risk is distributed
    between clusters and within them so that each asset contributes equally to
    risk. This is distinct from the flat :class:`HierarchicalRiskParity`.
    """

    def __init__(
        self,
        distance_estimator: Any | None = None,
        hierarchical_clustering_estimator: Any | None = None,
        prior_estimator: Any | None = None,
        min_weights: Any | None = 0.0,
        max_weights: Any | None = 1.0,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.distance_estimator = distance_estimator
        self.hierarchical_clustering_estimator = hierarchical_clustering_estimator
        self.prior_estimator = prior_estimator
        self.min_weights = min_weights
        self.max_weights = max_weights
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.raise_on_failure = raise_on_failure
        super().__init__(
            risk_measure=RiskMeasure.VARIANCE,
            distance_estimator=distance_estimator,
            hierarchical_clustering_estimator=hierarchical_clustering_estimator,
            prior_estimator=prior_estimator,
            min_weights=min_weights,
            max_weights=max_weights,
            portfolio_params=portfolio_params,
            fallback=fallback,
            raise_on_failure=raise_on_failure,
        )


class NestedClustersOptimizationAllocator(SkfolioNestedClustersOptimization):
    """Nested clustered optimization allocation.

    Assets are first clustered; optimization is then performed within each
    cluster and finally between clusters. This reduces the sensitivity of
    classical portfolio optimization to estimation errors in the covariance
    matrix.
    """

    def __init__(
        self,
        inner_estimator: Any | None = None,
        outer_estimator: Any | None = None,
        distance_estimator: Any | None = None,
        clustering_estimator: Any | None = None,
        quantile: float = 0.5,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        previous_weights: Any | None = None,
        raise_on_failure: bool = True,
    ) -> None:
        self.inner_estimator = inner_estimator
        self.outer_estimator = outer_estimator
        self.distance_estimator = distance_estimator
        self.clustering_estimator = clustering_estimator
        self.quantile = quantile
        self.portfolio_params = portfolio_params
        self.fallback = fallback
        self.previous_weights = previous_weights
        self.raise_on_failure = raise_on_failure
        super().__init__(
            inner_estimator=inner_estimator,
            outer_estimator=outer_estimator,
            distance_estimator=distance_estimator,
            clustering_estimator=clustering_estimator,
            quantile=quantile,
            portfolio_params=portfolio_params,
            fallback=fallback,
            previous_weights=previous_weights,
            raise_on_failure=raise_on_failure,
        )
