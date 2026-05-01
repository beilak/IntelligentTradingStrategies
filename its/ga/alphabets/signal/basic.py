from its.ga.types import GeneDefinition
from its.strategies.core.signals import (
    KeepAllSignal,
    PriceBreakoutSignal,
    SMACrossSignal,
    TwoCandlePositiveTrendSignal,
)

GENES = [
    GeneDefinition(
        id="pass_signal",
        title="Pass-signal",
        description="Do not apply an additional signal filter after pre-selection.",
        group="signal",
        component=KeepAllSignal,
    ),
    GeneDefinition(
        id="PriceBreakoutSignal",
        title="Price breakout signal",
        description="Select assets where current price breaks above the highest price of the last `lookback_window` candles.",
        group="signal",
        component=PriceBreakoutSignal,
    ),
    GeneDefinition(
        id="SMACrossSignal",
        title="SMA Cross",
        description="Select assets where the short-term SMA crosses above the long-term SMA (golden cross).",
        group="signal",
        component=SMACrossSignal,
    ),
    GeneDefinition(
        id="TwoCandlePositiveTrendSignal",
        title="2 Candle Trends",
        description="Select assets where the last `n_candles` have positive returns >= `min_pct_increase`.",
        group="signal",
        component=TwoCandlePositiveTrendSignal,
    ),
]
