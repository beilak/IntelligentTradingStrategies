import numpy as np
import numpy.typing as npt
from skfolio.measures import cvar
from skfolio.optimization._base import BaseOptimization
from skfolio.prior import BasePrior, EmpiricalPrior
from skfolio.utils.tools import check_estimator
from sklearn.utils.validation import validate_data


class CVaR(BaseOptimization):
    """Inverse Conditional Value at Risk allocator.

    Each asset weight is computed as inverse historical CVaR and rescaled to
    have a sum of weights equal to one.

    Parameters
    ----------
    prior_estimator : BasePrior, optional
        :ref:`Prior estimator <prior>`.
        If provided, the prior estimator is used to estimate the returns passed
        to CVaR. The default (`None`) computes historical CVaR directly from `X`.

    beta : float, default=0.95
        CVaR confidence level.

    min_cvar : float, default=1e-12
        Minimum positive CVaR used to avoid division by zero. Assets with
        non-positive CVaR are treated as having this minimum risk.

    portfolio_params :  dict, optional
        Portfolio parameters passed to the portfolio evaluated by the `predict` and
        `score` methods. If not provided, the `name`, `transaction_costs`,
        `management_fees` and `previous_weights` are copied from the optimization
        model and systematically passed to the portfolio.

    Attributes
    ----------
    weights_ : ndarray of shape (n_assets,) or (n_optimizations, n_assets)
        Weights of the assets.

    prior_estimator_ : BasePrior
        Checked `prior_estimator`. Fitted only when `prior_estimator` is provided.
    """

    prior_estimator_: BasePrior

    def __init__(
        self,
        prior_estimator: BasePrior | None = None,
        beta: float = 0.95,
        min_cvar: float = 1e-12,
        portfolio_params: dict | None = None,
    ):
        super().__init__(portfolio_params=portfolio_params)
        self.prior_estimator = prior_estimator
        self.beta = beta
        self.min_cvar = min_cvar

    def fit(self, X: npt.ArrayLike, y: npt.ArrayLike | None = None) -> "CVaR":
        """Fit the CVaR estimator.

        Parameters
        ----------
        X : array-like of shape (n_observations, n_assets)
           Price returns of the assets.

        y : array-like of shape (n_observations, n_targets), optional
            Price returns of factors or a target benchmark.
            The default is `None`.

        Returns
        -------
        self : CVaR
            Fitted estimator.
        """
        if not 0 < self.beta < 1:
            raise ValueError("beta must be in the interval (0, 1)")
        if self.min_cvar <= 0:
            raise ValueError("min_cvar must be positive")

        X_validated = validate_data(self, X, ensure_all_finite="allow-nan")

        self.prior_estimator_ = check_estimator(
            self.prior_estimator,
            default=EmpiricalPrior(),
            check_type=BasePrior,
        )

        if self.prior_estimator is None:
            returns = X_validated
            sample_weight = None
        else:
            self.prior_estimator_.fit(X, y)
            returns = self.prior_estimator_.return_distribution_.returns
            sample_weight = self.prior_estimator_.return_distribution_.sample_weight

        cvar_values = np.asarray(
            cvar(returns, beta=self.beta, sample_weight=sample_weight),
            dtype=float,
        )
        cvar_values = np.where(np.isfinite(cvar_values), cvar_values, np.nan)

        valid = ~np.isnan(cvar_values)
        if not valid.any():
            self.weights_ = np.zeros_like(cvar_values, dtype=float)
            self.cvar_ = cvar_values
            return self

        positive_risk = np.maximum(cvar_values[valid], self.min_cvar)
        inverse_risk = 1.0 / positive_risk
        total = inverse_risk.sum()

        weights = np.zeros_like(cvar_values, dtype=float)
        if total == 0 or not np.isfinite(total):
            weights[valid] = 1.0 / valid.sum()
        else:
            weights[valid] = inverse_risk / total

        self.weights_ = weights
        self.cvar_ = cvar_values
        return self


class CVaRHighRisk(BaseOptimization):
    """CVaR allocator that gives larger weights to higher tail-risk assets.

    This allocator is intentionally risk-seeking: each asset weight is
    proportional to its historical CVaR and rescaled to have a sum of weights
    equal to one. Assets with missing or non-finite CVaR receive zero weight.

    Use :class:`CVaR` when the desired behavior is the opposite, i.e. lower
    tail-risk assets should receive larger weights.

    Parameters
    ----------
    prior_estimator : BasePrior, optional
        If provided, the prior estimator is used to estimate the returns passed
        to CVaR. The default (`None`) computes historical CVaR directly from `X`.

    beta : float, default=0.95
        CVaR confidence level.

    min_cvar : float, default=1e-12
        Minimum positive CVaR used to avoid zero total risk. Assets with
        non-positive CVaR are treated as having this minimum risk.

    portfolio_params : dict, optional
        Portfolio parameters passed to the portfolio evaluated by the `predict`
        and `score` methods.

    Attributes
    ----------
    weights_ : ndarray of shape (n_assets,)
        Weights of the assets. Higher CVaR means higher weight.

    cvar_ : ndarray of shape (n_assets,)
        Historical CVaR value per asset.

    prior_estimator_ : BasePrior
        Checked `prior_estimator`. Fitted only when `prior_estimator` is provided.
    """

    prior_estimator_: BasePrior

    def __init__(
        self,
        prior_estimator: BasePrior | None = None,
        beta: float = 0.95,
        min_cvar: float = 1e-12,
        portfolio_params: dict | None = None,
    ):
        super().__init__(portfolio_params=portfolio_params)
        self.prior_estimator = prior_estimator
        self.beta = beta
        self.min_cvar = min_cvar

    def fit(self, X: npt.ArrayLike, y: npt.ArrayLike | None = None) -> "CVaRHighRisk":
        """Fit the high-risk CVaR allocator.

        Parameters
        ----------
        X : array-like of shape (n_observations, n_assets)
           Price returns of the assets.

        y : array-like of shape (n_observations, n_targets), optional
            Price returns of factors or a target benchmark.
            The default is `None`.

        Returns
        -------
        self : CVaRHighRisk
            Fitted estimator.
        """
        if not 0 < self.beta < 1:
            raise ValueError("beta must be in the interval (0, 1)")
        if self.min_cvar <= 0:
            raise ValueError("min_cvar must be positive")

        X_validated = validate_data(self, X, ensure_all_finite="allow-nan")

        self.prior_estimator_ = check_estimator(
            self.prior_estimator,
            default=EmpiricalPrior(),
            check_type=BasePrior,
        )

        if self.prior_estimator is None:
            returns = X_validated
            sample_weight = None
        else:
            self.prior_estimator_.fit(X, y)
            returns = self.prior_estimator_.return_distribution_.returns
            sample_weight = self.prior_estimator_.return_distribution_.sample_weight

        cvar_values = np.asarray(
            cvar(returns, beta=self.beta, sample_weight=sample_weight),
            dtype=float,
        )
        cvar_values = np.where(np.isfinite(cvar_values), cvar_values, np.nan)

        valid = ~np.isnan(cvar_values)
        if not valid.any():
            self.weights_ = np.zeros_like(cvar_values, dtype=float)
            self.cvar_ = cvar_values
            return self

        positive_risk = np.maximum(cvar_values[valid], self.min_cvar)
        total = positive_risk.sum()

        weights = np.zeros_like(cvar_values, dtype=float)
        if total == 0 or not np.isfinite(total):
            weights[valid] = 1.0 / valid.sum()
        else:
            weights[valid] = positive_risk / total

        self.weights_ = weights
        self.cvar_ = cvar_values
        return self
