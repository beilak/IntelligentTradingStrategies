from datetime import date, datetime
import fastapi
from t_tech.invest.utils import now
from its.container import UseCasesIOC

from its.use_cases.custom_bars.custom_bar import CustomBar


cust_bar_router = fastapi.APIRouter()


@cust_bar_router.get("/custom_bars")
async def get_cust_bar(
    ticker_name: str,
    bar_type: str,
    date_from: datetime = now(),  # datetime.now(),
    cust_bar: CustomBar = fastapi.Depends(UseCasesIOC.cust_bar),
):
    await cust_bar.execute(
        ticker_name=ticker_name,
        bar_type=bar_type,
        date_from=date_from,  # datetime.combine(date_from, datetime.min.time()),
    )

    return {}
