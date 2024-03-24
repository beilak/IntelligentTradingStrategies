import fastapi

from its.data_loader.common import models as cm
from its.data_loader.use_cases import ShareInfoUseCase
from its.container import UseCasesIOC


share_info_router = fastapi.APIRouter()


@share_info_router.get("/share")
async def get_share_info(
    share_info: ShareInfoUseCase = fastapi.Depends(UseCasesIOC.share_info),
    class_code: str | None = None,
    currency: str | None = None,
    ticker_name: str | None = None,
):
    return share_info.execute(
        shares_filter=cm.ShareInfoFilter(
            class_code=class_code,
            currency=currency,
            tickers_name={
                ticker_name,
            },
        )
    )
