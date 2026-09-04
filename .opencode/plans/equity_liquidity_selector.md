# Plan: Implement `EquityLiquiditySelector` (ITS pre-selection component)

## Scope
Implement the `EquityLiquiditySelector` pre-selection component, export it, and add
focused unit + look-ahead tests. Do NOT create a ready-model (StrategyBuilder) or a
GA gene.

## Behavior (per task)
On each call date build a point-in-time universe: keep only assets whose average
daily ruble turnover over the previous `lookback_days` trading sessions is at least
`min_avg_daily_turnover_rub`. Defaults: `lookback_days=63`, `min_avg_daily_turnover_rub=10_000_000`.
Exclude assets with insufficient history, incorrect data, or unsuitable instrument type.
Do not use future info or today's instrument list for historical periods. Write the result
to `to_keep_` as a boolean mask in input-asset order. The selector must NOT compute
momentum, generate a trading signal, or assign weights.

### Refinements from user
- NO `assets_info` / `allowed_instrument_types` parameters (instrument-type filter is
  handled upstream; candle input is already equities).
- NO `ticker_column` parameter (always `"ticker"`).
- Scope = selector + tests only.

## Point-in-time / no look-ahead
`asset_universe_prices` is provided through the builder as `_asset_universe_prices`. The
backtest engine (`_limit_pipeline_price_context` in
`its/strategies/testing/backtest/vectorbt_backtest.py`) truncates this context to the
current training end before each fit, so only past data is used. The selector records
`source_as_of_` = max timestamp in the provided context.

## Files
1. NEW `its/strategies/core/selectors/equity_liquidity_selector.py`
   - `EquityLiquiditySelector(Selectros)` (base `its.strategies.core.types.selectors_types.Selectros`)
   - Modeled on `QuarterlyTopTurnoverSelector` (long-form OHLCV context).
2. EDIT `its/strategies/core/selectors/__init__.py` — import + add to `__all__`.
3. NEW `tests/strategies_model/selectors/test_equity_liquidity_selector.py`.

## Selector API
Constructor (clone-compatible; every arg stored on `self` unchanged):
- `asset_universe_prices: pd.DataFrame | None = None` (columns `ticker, time, open,
  high, low, close, volume`, optional `is_complete`)
- `lookback_days: int = 63`
- `min_avg_daily_turnover_rub: float = 10_000_000`
- `min_history_days: int = 63` (min completed trading days in window to be eligible)
- `time_column="time"`, `open_column="open"`, `high_column="high"`,
  `low_column="low"`, `close_column="close"`, `volume_column="volume"`

`fit(X, y=None)`:
1. Validate params:
   - `lookback_days > 0`
   - `min_avg_daily_turnover_rub >= 0`
   - `min_history_days in [1, lookback_days]`
2. `skv.validate_data(X, ensure_all_finite="allow-nan")`; asset names from
   `feature_names_in_` (or generated `asset_<i>`).
3. Require `asset_universe_prices` (raise `ValueError` if None).
4. Clean candles: coerce time to datetime (drop tz), coerce numerics; drop rows with
   missing required columns, non-finite values, non-positive prices, negative volume,
   and incomplete candles (`is_complete` falsy).
5. Daily turnover: group by `ticker` + trading date, `sum` bar turnover; take the last
   `lookback_days` distinct trading dates globally (point-in-time calendar).
6. Per ticker: `mean_daily_turnover = mean(daily_turnover)`, `trading_days = nunique`;
   require `trading_days >= min_history_days`; keep if
   `mean_daily_turnover >= min_avg_daily_turnover_rub`.
7. `to_keep_ = np.isin(asset_names, selected_tickers)` aligned with input columns.
   Empty selection = all-false mask (valid all-cash), do NOT raise.
8. Diagnostics: `to_keep_`, `asset_names_`, `selected_assets_`, `turnover_summary_`,
   `source_as_of_`.

## Tests (`tests/strategies_model/selectors/test_equity_liquidity_selector.py`)
- selects/rejects named assets by deterministic turnover; preserves input order + mask.
- exact threshold boundary.
- invalid constructor values fail with specific messages.
- missing `asset_universe_prices` and missing required columns fail explicitly.
- insufficient per-asset history (`trading_days < min_history_days`) -> not selected.
- incomplete candles and incorrect data (non-finite/negative) are ignored.
- empty selection -> all-false mask, no exception.
- look-ahead test: fit at `T`, record decision; append future candles; re-fit on
  context truncated to `T`; assert decision + summary unchanged.

## Verification
```bash
poetry run pytest tests/strategies_model/selectors/test_equity_liquidity_selector.py -q
poetry run black <touched .py files>
poetry run isort <touched .py files>
poetry run pytest tests/strategies_model/selectors/ -q
poetry run ruff check <touched .py files>
git diff --check
```
