# from __future__ import annotations

# from its.strategies.core.optimization import EqualWeighted, InverseVolatility
# from its.strategies.core.selectors import (
#     KeepAllSelector,
#     IntradayTurnoverSelector,
#     SafeEmptySelector,
#     TrendSelector,
#     TrendThresholdSelector,
# )


# def turnover_selector(
#     *,
#     asset_universe_prices=None,
#     lookback_bars: int = 10,
#     min_turnover: float = 1_000_000,
# ):
#     return IntradayTurnoverSelector(
#         asset_universe_prices=asset_universe_prices,
#         lookback_bars=lookback_bars,
#         min_turnover=min_turnover,
#         allow_empty_selection=False,
#     )


# def pass_through_signal():
#     return KeepAllSelector()


# def safe_trend_signal(*, window: int = 20):
#     return SafeEmptySelector(TrendSelector(window=window))


# def safe_trend_threshold_signal(*, window: int = 20, slope_threshold: float = 0.0):
#     return SafeEmptySelector(
#         TrendThresholdSelector(window=window, slope_threshold=slope_threshold)
#     )


# def equal_weighted_allocator():
#     return EqualWeighted()


# def inverse_volatility_allocator():
#     return InverseVolatility(raise_on_failure=False)
