from __future__ import annotations

from importlib import import_module
from typing import Any

import numpy as np
import numpy.typing as npt
from skfolio.optimization import EqualWeighted
from skfolio.optimization._base import BaseOptimization
from sklearn.utils.validation import validate_data


class CQMAllocator(BaseOptimization):
    """Constrained Quadratic Model allocator for discrete portfolio weights.

    Asset weights are represented by integer variables that count discrete
    ``weight_unit`` chunks. The CQM objective minimizes a weighted combination of
    negative alpha score, covariance risk, deviation from previous weights, and
    concentration. Hard constraints enforce full investment and per-asset
    maximum weight bounds.

    Parameters
    ----------
    alpha_scores : array-like or dict, optional
        Per-asset alpha scores. If omitted, the column mean of ``X`` is used.

    covariance_matrix : array-like, optional
        Asset covariance matrix. If omitted, a pairwise covariance matrix is
        estimated from ``X``.

    max_weight : float, default=1.0
        Maximum target weight per asset.

    weight_unit : float, default=0.01
        Discrete unit size. ``1 / weight_unit`` must be an integer within a small
        numerical tolerance.

    alpha_weight, risk_weight, deviation_weight, concentration_weight : float
        Non-negative objective weights.

    sampler : object, optional
        CQM sampler exposing ``sample_cqm(cqm, **sampler_params)``. When omitted,
        ``dimod.ExactCQMSolver`` is used only when the cartesian search space is
        smaller than ``max_exact_cartesian_size``.

    sampler_params : dict, optional
        Keyword arguments forwarded to ``sample_cqm``.

    use_exact_solver : bool, default=True
        Whether to use ``dimod.ExactCQMSolver`` when no sampler is provided.

    max_exact_cartesian_size : int, default=250_000
        Maximum variable-domain cartesian size allowed for the default exact
        solver.

    portfolio_params : dict, optional
        Portfolio parameters passed to ``predict``.

    fallback : BaseOptimization or "previous_weights", optional
        Fallback allocator used when CQM solving fails or no feasible solution is
        found. Defaults to ``EqualWeighted()``.

    previous_weights : float, dict or array-like, optional
        Current portfolio weights used by the deviation term and by fallback
        propagation.

    raise_on_failure : bool, default=True
        skfolio failure behavior after all fallbacks fail.
    """

    def __init__(
        self,
        alpha_scores: npt.ArrayLike | dict[str, float] | None = None,
        covariance_matrix: npt.ArrayLike | None = None,
        max_weight: float = 1.0,
        weight_unit: float = 0.01,
        alpha_weight: float = 1.0,
        risk_weight: float = 1.0,
        deviation_weight: float = 1.0,
        concentration_weight: float = 1.0,
        sampler: Any | None = None,
        sampler_params: dict[str, Any] | None = None,
        use_exact_solver: bool = True,
        max_exact_cartesian_size: int = 250_000,
        portfolio_params: dict | None = None,
        fallback: Any | None = None,
        previous_weights: npt.ArrayLike | dict[str, float] | float | None = None,
        raise_on_failure: bool = True,
    ):
        super().__init__(
            portfolio_params=portfolio_params,
            fallback=EqualWeighted() if fallback is None else fallback,
            previous_weights=previous_weights,
            raise_on_failure=raise_on_failure,
        )
        self.alpha_scores = alpha_scores
        self.covariance_matrix = covariance_matrix
        self.max_weight = max_weight
        self.weight_unit = weight_unit
        self.alpha_weight = alpha_weight
        self.risk_weight = risk_weight
        self.deviation_weight = deviation_weight
        self.concentration_weight = concentration_weight
        self.sampler = sampler
        self.sampler_params = sampler_params
        self.use_exact_solver = use_exact_solver
        self.max_exact_cartesian_size = max_exact_cartesian_size

    def fit(self, X: npt.ArrayLike, y: npt.ArrayLike | None = None) -> "CQMAllocator":
        """Fit the CQM allocator and produce target weights."""
        self._validate_parameters()

        X_validated = validate_data(self, X, ensure_all_finite="allow-nan")
        n_assets = X_validated.shape[1]
        if n_assets == 0:
            self._raise_with_diagnostics("CQM allocation requires at least one asset")

        total_units = self._total_weight_units()
        max_units = self._max_weight_units(total_units=total_units)
        if max_units * n_assets < total_units:
            self._raise_with_diagnostics(
                (
                    "CQM allocation is infeasible: max_weight does not allow "
                    "the selected assets to sum to 1"
                ),
                n_assets=n_assets,
                total_weight_units=total_units,
                max_weight_units=max_units,
            )

        alpha_estimate, covariance_estimate = self._estimate_alpha_and_covariance(
            X_validated
        )
        alpha_scores = self._clean_alpha_scores(
            alpha_estimate,
            n_assets=n_assets,
        )
        covariance = self._clean_covariance_matrix(
            covariance_estimate,
            n_assets=n_assets,
        )
        previous_weights = self._clean_previous_weights(n_assets=n_assets)
        previous_weights = np.where(
            np.isfinite(previous_weights), previous_weights, 0.0
        )
        deviation_weight = self._effective_deviation_weight()

        dimod = self._import_dimod()
        variable_labels = [f"w_{i}" for i in range(n_assets)]
        cqm = self._build_cqm(
            dimod=dimod,
            variable_labels=variable_labels,
            alpha_scores=alpha_scores,
            covariance=covariance,
            previous_weights=previous_weights,
            deviation_weight=deviation_weight,
            total_units=total_units,
            max_units=max_units,
        )
        self.cqm_ = cqm

        diagnostics_base = self._diagnostics_base(
            n_assets=n_assets,
            total_weight_units=total_units,
            max_weight_units=max_units,
            deviation_weight=deviation_weight,
            alpha_scores=alpha_scores,
            covariance=covariance,
        )
        self.diagnostics_ = diagnostics_base | {
            "feasible": False,
            "fallback_used": False,
        }

        sampler = self._resolve_sampler(
            dimod=dimod,
            n_assets=n_assets,
            max_units=max_units,
        )
        sampleset = sampler.sample_cqm(cqm, **(self.sampler_params or {}))
        feasible_sampleset = sampleset.filter(
            lambda sample_data: self._is_sample_feasible(cqm, sample_data)
        )
        if len(feasible_sampleset) == 0:
            self._raise_with_diagnostics(
                "CQM sampler did not return a feasible solution",
                **diagnostics_base,
            )

        best = feasible_sampleset.first
        sample = dict(best.sample)
        if not cqm.check_feasible(sample):
            self._raise_with_diagnostics(
                "Best CQM sample failed feasibility validation",
                **diagnostics_base,
            )

        units = np.asarray([sample[label] for label in variable_labels], dtype=float)
        weights = units * self.weight_unit
        if not np.isclose(weights.sum(), 1.0):
            self._raise_with_diagnostics(
                "Best CQM sample does not sum to 1 after unit conversion",
                **diagnostics_base,
            )

        self.weights_ = weights
        self.target_weights_ = weights
        self.weight_units_ = units.astype(int)
        self.sample_ = sample
        self.objective_energy_ = float(best.energy)
        self.feasible_ = True
        self.diagnostics_ = diagnostics_base | {
            "feasible": True,
            "fallback_used": False,
            "solver": type(sampler).__name__,
            "objective_energy": self.objective_energy_,
            "weight_units": self.weight_units_.tolist(),
            "target_weights": self.weights_.tolist(),
            "objective_components": self._objective_components(
                weights=weights,
                alpha_scores=alpha_scores,
                covariance=covariance,
                previous_weights=previous_weights,
                deviation_weight=deviation_weight,
            ),
            "constraints": {
                "budget_weight_units": int(self.weight_units_.sum()),
                "budget_weight": float(weights.sum()),
                "max_weight": float(weights.max(initial=0.0)),
            },
        }
        return self

    def _run_fallback_chain(
        self,
        X: npt.ArrayLike,
        y: npt.ArrayLike | None,
        primary_error: Exception,
        **fit_params: Any,
    ) -> None:
        super()._run_fallback_chain(
            X=X,
            y=y,
            primary_error=primary_error,
            **fit_params,
        )
        self.target_weights_ = self.weights_
        self.feasible_ = False
        diagnostics = dict(getattr(self, "diagnostics_", {}) or {})
        diagnostics.update(
            {
                "feasible": False,
                "fallback_used": True,
                "fallback": str(self.fallback_),
                "fallback_reason": str(primary_error),
                "target_weights": (
                    None
                    if self.weights_ is None
                    else np.asarray(self.weights_).tolist()
                ),
            }
        )
        self.diagnostics_ = diagnostics

    @property
    def needs_previous_weights(self) -> bool:
        return self.deviation_weight > 0 or super().needs_previous_weights

    def _validate_parameters(self) -> None:
        if not np.isfinite(self.max_weight) or self.max_weight <= 0:
            raise ValueError("max_weight must be positive")
        if (
            not np.isfinite(self.weight_unit)
            or self.weight_unit <= 0
            or self.weight_unit > 1
        ):
            raise ValueError("weight_unit must be in the interval (0, 1]")
        if self.max_exact_cartesian_size < 1:
            raise ValueError("max_exact_cartesian_size must be positive")
        for name in (
            "alpha_weight",
            "risk_weight",
            "deviation_weight",
            "concentration_weight",
        ):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be non-negative")
        self._total_weight_units()

    def _effective_deviation_weight(self) -> float:
        if self.previous_weights is None:
            return 0.0
        return self.deviation_weight

    def _total_weight_units(self) -> int:
        total_units = int(round(1.0 / self.weight_unit))
        if total_units < 1 or not np.isclose(
            total_units * self.weight_unit,
            1.0,
            rtol=0.0,
            atol=1e-9,
        ):
            raise ValueError("1 / weight_unit must be an integer")
        return total_units

    def _max_weight_units(self, total_units: int) -> int:
        max_units = int(np.floor(self.max_weight / self.weight_unit + 1e-9))
        return min(total_units, max_units)

    def _import_dimod(self) -> Any:
        try:
            return import_module("dimod")
        except ImportError as exc:
            raise RuntimeError(
                "CQMAllocator requires the D-Wave Ocean 'dimod' package"
            ) from exc

    def _build_cqm(
        self,
        dimod: Any,
        variable_labels: list[str],
        alpha_scores: np.ndarray,
        covariance: np.ndarray,
        previous_weights: np.ndarray,
        deviation_weight: float,
        total_units: int,
        max_units: int,
    ) -> Any:
        cqm = dimod.ConstrainedQuadraticModel()
        for label in variable_labels:
            cqm.add_variable(
                "INTEGER",
                label,
                lower_bound=0,
                upper_bound=max_units,
            )

        objective_terms: list[tuple[Any, ...]] = []
        unit = self.weight_unit
        for i, label in enumerate(variable_labels):
            linear_bias = (
                -self.alpha_weight * alpha_scores[i] * unit
                - 2.0 * deviation_weight * previous_weights[i] * unit
            )
            if linear_bias:
                objective_terms.append((label, float(linear_bias)))

            quadratic_bias = (
                self.risk_weight * covariance[i, i]
                + deviation_weight
                + self.concentration_weight
            ) * unit**2
            if quadratic_bias:
                objective_terms.append((label, label, float(quadratic_bias)))

        for i in range(len(variable_labels)):
            for j in range(i + 1, len(variable_labels)):
                quadratic_bias = 2.0 * self.risk_weight * covariance[i, j] * unit**2
                if quadratic_bias:
                    objective_terms.append(
                        (
                            variable_labels[i],
                            variable_labels[j],
                            float(quadratic_bias),
                        )
                    )

        cqm.set_objective(objective_terms)
        cqm.add_constraint_from_iterable(
            [(label, 1.0) for label in variable_labels],
            "==",
            rhs=total_units,
            label="budget",
        )
        return cqm

    def _resolve_sampler(
        self,
        dimod: Any,
        n_assets: int,
        max_units: int,
    ) -> Any:
        if self.sampler is not None:
            return self.sampler
        if not self.use_exact_solver:
            raise RuntimeError("No CQM sampler configured")

        cartesian_size = self._bounded_cartesian_size(
            domain_size=max_units + 1,
            n_assets=n_assets,
        )
        if cartesian_size > self.max_exact_cartesian_size:
            raise RuntimeError(
                (
                    "No CQM sampler configured and ExactCQMSolver search space "
                    f"({cartesian_size}) exceeds max_exact_cartesian_size "
                    f"({self.max_exact_cartesian_size})"
                )
            )
        return dimod.ExactCQMSolver()

    def _bounded_cartesian_size(self, domain_size: int, n_assets: int) -> int:
        size = 1
        limit = self.max_exact_cartesian_size + 1
        for _ in range(n_assets):
            size *= domain_size
            if size > limit:
                return size
        return size

    def _clean_alpha_scores(
        self,
        estimate: np.ndarray,
        n_assets: int,
    ) -> np.ndarray:
        if self.alpha_scores is None:
            alpha_scores = estimate
        elif hasattr(self.alpha_scores, "reindex") and hasattr(
            self.alpha_scores,
            "to_numpy",
        ):
            if hasattr(self, "feature_names_in_"):
                alpha_scores = self.alpha_scores.reindex(
                    self.feature_names_in_
                ).to_numpy(dtype=float)
            else:
                alpha_scores = self.alpha_scores.to_numpy(dtype=float)
        else:
            alpha_scores = self._clean_input(
                self.alpha_scores,
                n_assets=n_assets,
                fill_value=0,
                name="alpha_scores",
            )
            if np.isscalar(alpha_scores):
                alpha_scores = np.full(n_assets, float(alpha_scores))
            alpha_scores = np.asarray(alpha_scores, dtype=float)
        return np.where(np.isfinite(alpha_scores), alpha_scores, 0.0)

    def _clean_covariance_matrix(
        self,
        estimate: np.ndarray,
        n_assets: int,
    ) -> np.ndarray:
        if self.covariance_matrix is None:
            covariance = estimate
        elif hasattr(self.covariance_matrix, "reindex") and hasattr(
            self.covariance_matrix,
            "to_numpy",
        ):
            if not hasattr(self, "feature_names_in_"):
                covariance = self.covariance_matrix.to_numpy(dtype=float)
            else:
                covariance = self.covariance_matrix.reindex(
                    index=self.feature_names_in_,
                    columns=self.feature_names_in_,
                ).to_numpy(dtype=float)
        else:
            covariance = np.asarray(self.covariance_matrix, dtype=float)

        if covariance.shape != (n_assets, n_assets):
            raise ValueError(
                "covariance_matrix must have shape "
                f"({n_assets}, {n_assets}), got {covariance.shape}"
            )
        covariance = np.where(np.isfinite(covariance), covariance, 0.0)
        return (covariance + covariance.T) / 2.0

    def _estimate_alpha_and_covariance(
        self, X: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        finite = np.isfinite(X)
        counts = finite.sum(axis=0)
        alpha = np.divide(
            np.where(finite, X, 0.0).sum(axis=0),
            counts,
            out=np.zeros(X.shape[1], dtype=float),
            where=counts > 0,
        )

        covariance = np.zeros((X.shape[1], X.shape[1]), dtype=float)
        for i in range(X.shape[1]):
            for j in range(i, X.shape[1]):
                mask = finite[:, i] & finite[:, j]
                count = int(mask.sum())
                if count <= 1:
                    value = 0.0
                else:
                    centered_i = X[mask, i] - alpha[i]
                    centered_j = X[mask, j] - alpha[j]
                    value = float(centered_i.dot(centered_j) / (count - 1))
                covariance[i, j] = value
                covariance[j, i] = value
        return alpha, covariance

    def _is_sample_feasible(self, cqm: Any, sample_data: Any) -> bool:
        is_feasible = getattr(sample_data, "is_feasible", None)
        if is_feasible is not None:
            return bool(is_feasible)
        return bool(cqm.check_feasible(sample_data.sample))

    def _diagnostics_base(
        self,
        n_assets: int,
        total_weight_units: int,
        max_weight_units: int,
        deviation_weight: float | None = None,
        alpha_scores: np.ndarray | None = None,
        covariance: np.ndarray | None = None,
    ) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {
            "n_assets": n_assets,
            "weight_unit": float(self.weight_unit),
            "total_weight_units": int(total_weight_units),
            "max_weight_units": int(max_weight_units),
            "max_weight": float(max_weight_units * self.weight_unit),
            "objective_weights": {
                "alpha": float(self.alpha_weight),
                "risk": float(self.risk_weight),
                "deviation": float(
                    self.deviation_weight
                    if deviation_weight is None
                    else deviation_weight
                ),
                "concentration": float(self.concentration_weight),
            },
        }
        if alpha_scores is not None:
            diagnostics["alpha_scores"] = alpha_scores.tolist()
        if covariance is not None:
            diagnostics["covariance_trace"] = float(np.trace(covariance))
        return diagnostics

    def _objective_components(
        self,
        weights: np.ndarray,
        alpha_scores: np.ndarray,
        covariance: np.ndarray,
        previous_weights: np.ndarray,
        deviation_weight: float,
    ) -> dict[str, float]:
        return {
            "negative_alpha": float(-self.alpha_weight * alpha_scores.dot(weights)),
            "risk": float(self.risk_weight * weights.dot(covariance).dot(weights)),
            "deviation": float(
                deviation_weight * np.square(weights - previous_weights).sum()
            ),
            "concentration": float(
                self.concentration_weight * np.square(weights).sum()
            ),
        }

    def _raise_with_diagnostics(self, reason: str, **diagnostics: Any) -> None:
        self.feasible_ = False
        self.target_weights_ = None
        self.diagnostics_ = diagnostics | {
            "feasible": False,
            "fallback_used": False,
            "fallback_reason": reason,
        }
        raise RuntimeError(reason)
