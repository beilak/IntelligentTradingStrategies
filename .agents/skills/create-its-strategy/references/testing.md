# Testing strategy components

## Component tests

Cover all applicable cases:

- formula selects and rejects named assets with deterministic data;
- output mask and transformed DataFrame preserve input order and names;
- exact threshold boundaries;
- invalid constructor values fail with a specific message;
- missing required columns fail explicitly;
- insufficient per-asset history does not select the asset;
- incomplete candles are ignored;
- fitted diagnostic attributes contain expected values;
- empty selection is represented by an all-false mask.

For custom allocators also cover one asset, zero variance, singular inputs, finite normalized weights, and fallback/error policy.

## Look-ahead test

Fit at timestamp `T`, record the decision, append or alter rows after `T`, and fit again using context truncated to `T`. Assert the decision and diagnostics at `T` are unchanged.

## Pipeline and backtest test

- Build the real `StrategyBuilder` with synthetic context.
- Run `backtest_strategies_vectorbt` over multiple rebalance dates.
- Assert at least one expected non-zero allocation when the fixture has a valid signal.
- Assert a no-signal rebalance is present with all zero weights and does not raise.
- Assert weights are finite and their sum is in `[0, 1]` unless leverage is explicitly intended.
- For rolling models, prove later rebalances receive later context.

## Commands

Run the smallest relevant set first:

```bash
poetry run pytest tests/strategies_model/<domain>/test_<component>.py -q
poetry run ruff check <touched-python-files>
```

Then format touched files and repeat validation:

```bash
poetry run black <touched-python-files>
poetry run isort <touched-python-files>
poetry run pytest <focused-tests> -q
poetry run ruff check <touched-python-files>
git diff --check
```

For UI-visible registry changes, verify the strategy backend registry after rebuilding the service when the user requests live validation.

