# Plan: Implement `LongOnlyCrossSectionalMomentumSignal` (ITS signal component)

## Scope
Implement the `LongOnlyCrossSectionalMomentumSignal` signal component, export it, and
add focused unit + look-ahead tests. Do NOT create a ready-model (StrategyBuilder) or a
GA gene. Scope = signal + tests only (per user).

## Context research
- Base: `Siglans` in `its/strategies/core/types/signals_types.py` (extends
  `DataFrameSelectorMixin` + `skf.SelectorMixin` + `skb.BaseEstimator`). Provides
  `to_keep_`, `_get_support_mask()`, `transform()` (preserves DataFrame columns).
- Closest analog: `ExtremumRangeLongSignal` — reads long-form OHLCV from
  `asset_universe_prices`, iterates per ticker, stores diagnostics as `pd.Series`
  suffixed with `_`, uses a `_prepare_candles` helper that coerces timestamps/numerics,
  drops non-finite / non-positive values / incomplete (`is_complete` falsy) candles.
- During backtest `fit`, `X` is a **return matrix** (close `pct_change`), NOT prices
  (`_build_train_returns` in vectorbt_backtest.py). Momentum needs CLOSE PRICES, so the
  signal reads close prices from the long-form `asset_universe_prices` context (same as
  `ExtremumRangeLongSignal`).
- The engine truncates `asset_universe_prices` to the training end before each fit
  (`_limit_pipeline_price_context`), guaranteeing point-in-time / no look-ahead.
- Export: `its/strategies/core/signals/__init__.py`. Tests:
  `tests/strategies_model/signals/`.

## User decisions
- "Adjusted prices" = the `close` column of `asset_universe_prices` (no separate
  adjusted-close column; treats closes as the adjusted series).
- Scope = signal + tests only.

## Files
1. NEW `its/strategies/core/signals/long_only_cross_sectional_momentum.py`
2. EDIT `its/strategies/core/signals/__init__.py` — import + add to `__all__`
3. NEW `tests/strategies_model/signals/test_long_only_cross_sectional_momentum.py`

## Signal API
Constructor (clone-compatible; every arg stored on `self` unchanged):
- `asset_universe_prices: pd.DataFrame | None = None` (long OHLCV: `ticker, time, close`,
  optional `is_complete`)
- `lookback_days: int = 252` (momentum window in trading sessions)
- `skip_last_days: int = 21` (most-recent sessions excluded)
- `top_n: int = 10` (max assets kept)
- `ticker_column="ticker"`, `time_column="time"`, `close_column="close"`

## Momentum formula
Given per-asset closes sorted by time ascending:
- `required = lookback_days + skip_last_days + 1` observations.
- `past_close = closes[-lookback_days - skip_last_days]`
- `present_close = closes[-skip_last_days]` (0-based from end)
- `momentum = present_close / past_close - 1`

This is the classic Jegadeesh–Titman medium-term momentum (252 sessions, skipping the
last 21), i.e. return from `t - 21 - 252` to `t - 21`.

## `fit(X, y=None)` logic
1. Validate params: `lookback_days > 0`, `skip_last_days >= 0`, `top_n > 0`.
2. `skv.validate_data(self, X, ensure_all_finite="allow-nan")`; asset names from
   `feature_names_in_` or generated `asset_<i>`.
3. Require `asset_universe_prices` (raise `ValueError` if None).
4. `_prepare_candles`: require `{ticker, time, close}`; coerce time to datetime (strip
   tz), close to numeric; drop missing / incomplete (`is_complete` falsy) / non-finite /
   non-positive closes.
5. Per asset:
   - If fewer than `required` valid observations -> score `NaN`, reason
     `"insufficient_history"`, exclude.
   - Else compute `momentum` (formula above); record formation interval dates.
6. Ranking (deterministic): only finite-score assets are ranked. Sort by momentum
   descending with a deterministic secondary tie-break on ticker ascending
   (`kind="mergesort"`). Assign distinct 1-based ranks. Keep the first `top_n`.
   - Rankable-but-not-kept reason = `"below_top_n"`.
   - Long-only: no sign threshold; negative momentum is kept if within Top-N.
7. `to_keep_` = boolean mask aligned with input columns. Empty selection = all-false
   mask (valid all-cash), do NOT raise.
8. Audit diagnostics:
   - `momentum_scores_`: `pd.Series` indexed by asset names (NaN for excluded)
   - `ranking_`: `pd.Series` 1-based ranks for keepable assets (0 otherwise)
   - `selected_assets_`: `np.ndarray` of kept tickers
   - `formation_intervals_`: DataFrame with asset, formation_start, formation_end
   - `formation_start_` / `formation_end_`: overall earliest/latest formation bounds
   - `exclusion_reasons_`: `pd.Series` of reason strings per asset (`""` = kept,
     `"insufficient_history"`, `"below_top_n"`)

## Behavior guarantees per spec
- Point-in-time, deterministic, no future data (context is engine-truncated; look-ahead
  proven by test).
- Insufficient history -> excluded.
- Negative momentum is not an exclusion reason by itself (relative Top-N).
- No shorting; long-only.

## Tests (`tests/strategies_model/signals/test_long_only_cross_sectional_momentum.py`)
- momentum formula selects the Top-N by score; preserves input column order + mask.
- negative-momentum asset still selected when within Top-N (long-only relative ranking).
- diagnostics (scores, ranking, selected_assets, exclusion_reasons, formation dates)
  contain expected values.
- insufficient history -> excluded with reason, score NaN.
- deterministic tie-break when momentum ties.
- `top_n` boundary: keeps exactly top_n, next excluded as "below_top_n".
- invalid constructor values fail with specific messages; missing context/columns fail.
- empty selection -> all-false mask, no exception.
- look-ahead test: fit at `T`, append future candles, re-fit on context truncated to
  `T`; assert decision + scores/formations unchanged.

## Verification
```bash
poetry run pytest tests/strategies_model/signals/test_long_only_cross_sectional_momentum.py -q
poetry run black <touched .py files>
poetry run isort <touched .py files>
poetry run pytest tests/strategies_model/signals/ -q
poetry run ruff check <touched .py files>
git diff --check
```
