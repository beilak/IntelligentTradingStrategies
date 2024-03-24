from decimal import Decimal
from stsp import EntryPointResponse, PredictResponse
from stsp.protocols.predict.models import datetime
from its.strategies_model.oc_possition.percent.percent import (
    OpenPossitionByPredictPrec,
    OpenPosstionDto,
)


async def test_percent_definition_entry_point() -> None:
    model = OpenPossitionByPredictPrec(dto=OpenPosstionDto(percent=10))

    resp: EntryPointResponse = await model.definition_entry_point(
        ticker="TEST",
        prediction=PredictResponse(
            for_date=datetime.now(),
            next_price=Decimal(1000),
        ),
    )
    assert resp["price"] == 900
