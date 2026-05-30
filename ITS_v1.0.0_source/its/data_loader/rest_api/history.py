import fastapi
from typing import Literal
from its.data_loader.common import models as cm
from its.data_loader.use_cases import HistoryUseCase
from its.container import UseCasesIOC
from t_tech.invest import CandleInterval
from t_tech.invest.utils import now
from datetime import timedelta


history_router = fastapi.APIRouter()


Intervals = Literal[
    "CANDLE_INTERVAL_UNSPECIFIED",
    "CANDLE_INTERVAL_1_MIN",
    "CANDLE_INTERVAL_2_MIN",
    "CANDLE_INTERVAL_3_MIN",
    "CANDLE_INTERVAL_5_MIN",
    "CANDLE_INTERVAL_10_MIN",
    "CANDLE_INTERVAL_15_MIN",
    "CANDLE_INTERVAL_30_MIN",
    "CANDLE_INTERVAL_HOUR",
    "CANDLE_INTERVAL_2_HOUR",
    "CANDLE_INTERVAL_4_HOUR",
    "CANDLE_INTERVAL_DAY",
    "CANDLE_INTERVAL_WEEK ",
    "CANDLE_INTERVAL_MONTH ",
]


@history_router.get("/history")
async def get_share_info(
    figi: cm.FiGlobalId,
    interval: Intervals = "CANDLE_INTERVAL_DAY",
    last_days: int = 1,
    ohlc_history: HistoryUseCase = fastapi.Depends(UseCasesIOC.ohlc_history),
):
    return await ohlc_history.execute(
        figis={
            figi,
        },
        from_=now() - timedelta(days=last_days),
        interval=CandleInterval.__getitem__(interval),
    )
