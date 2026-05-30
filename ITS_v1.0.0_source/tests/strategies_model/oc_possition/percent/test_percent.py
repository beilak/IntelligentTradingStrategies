from decimal import Decimal
from stsp import EntryPointResponse, ExitPointResponse, PredictResponse
from stsp.protocols.predict.models import datetime
from its.strategies_model.oc_possition.percent.percent import (
    OpenPossitionByPredictPrec,
    ClosePossitionByPredictPrec,
    PosstionDto,
)


async def test_percent_definition_entry_point() -> None:
    model = OpenPossitionByPredictPrec(dto=PosstionDto(percent=10))

    resp: EntryPointResponse = await model.definition_entry_point(
        ticker="TEST",
        prediction=PredictResponse(
            for_date=datetime.now(),
            next_price=Decimal(1000),
        ),
    )
    assert resp["price"] == 900


async def test_percent_definition_exit_point() -> None:
    model = ClosePossitionByPredictPrec(dto=PosstionDto(percent=10))

    resp: ExitPointResponse = await model.definition_exit_point(
        ticker="TEST",
        prediction=PredictResponse(
            for_date=datetime.now(),
            next_price=Decimal(1000),
        ),
    )
    assert resp["price"] == 1100
