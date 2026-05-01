"""Model predict of as last change"""


class PredictorDto:
    last_days: int
    devider: int


class LastChangePredict:
    def __init__(self, dto: PredictorDto) -> None:
        self._last_days = dto["last_days"]
        self._devider = dto["devider"]

    async def predict(self, *, ticker) -> list[PredictResponse]: ...
