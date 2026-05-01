"""Main Strategies class."""

from stsp import PredictionProtocol


class Strategies:
    def __init__(
        self,
        name: str,
        predictor: PredictionProtocol,
    ) -> None:
        self._name = name
        self._predictor = predictor

    async def execute(self, symbol: str) -> None:
        predict_trend = await self._predictor.execute(symbol)
