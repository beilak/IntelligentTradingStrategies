from decimal import Decimal
from typing import TypedDict
from stsp import ExitPointResponse, OpenPositionProtocol, ClosePositionProtocol
from stsp.protocols.position.models import EntryPointResponse
from stsp.protocols.predict.models import PredictResponse


class PosstionDto(TypedDict):
    percent: int


class OpenPossitionByPredictPrec(OpenPositionProtocol):
    def __init__(self, dto: PosstionDto) -> None:
        self._percent = dto["percent"]

    async def definition_entry_point(
        self,
        *,
        ticker: str,
        prediction: PredictResponse,
    ) -> EntryPointResponse:
        """Provide position entry point"""

        return EntryPointResponse(
            price=Decimal(
                prediction["next_price"]
                - (prediction["next_price"] * self._percent / 100)
            )
        )


class ClosePossitionByPredictPrec(ClosePositionProtocol):
    def __init__(self, dto: PosstionDto) -> None:
        self._percent = dto["percent"]

    async def definition_exit_point(
        self,
        *,
        ticker: str,
        prediction: PredictResponse,
    ) -> EntryPointResponse:
        """Provide position entry point"""

        return ExitPointResponse(
            price=Decimal(
                prediction["next_price"]
                + (prediction["next_price"] * self._percent / 100)
            )
        )
