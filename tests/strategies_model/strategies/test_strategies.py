"""Test main strat class"""
from its.strategies_model.prediction.ma.ma import MA
from its.strategies_model.strategies.strat import Strategies
from tests.strategies_model.common.ohlc_provider import OhlcProviderForTest


async def test_strat() -> None:
    ohlc_provider = OhlcProviderForTest
    predictor = MA(ohlc_provider=ohlc_provider)
    strat = Strategies(
        name="test_strategies",
        predictor=predictor,
    )

    await strat.execute("AAPL")
