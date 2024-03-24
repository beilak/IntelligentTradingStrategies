from decimal import Decimal
from typing import TypedDict
from stsp import OpenPositionProtocol
from stsp.protocols.position.models import EntryPointResponse
from stsp.protocols.predict.models import PredictResponse


class OpenPosstionDto(TypedDict):
    percent: int


class OpenPossitionByPredictPrec(OpenPositionProtocol):
    def __init__(self, dto: OpenPosstionDto) -> None:
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
