from fastapi import FastAPI

import its.container as container
from its.data_loader.rest_api.share_info import share_info_router
from its.data_loader.rest_api.history import history_router
from its.api.custom_bars import cust_bar_router


async def on_startup():
    await container.AdaptersIOC.aopen()
    await container.UseCasesIOC.aopen()


async def on_shutdown() -> None:
    await container.AdaptersIOC.aclose()
    await container.UseCasesIOC.aclose()


def create_web_app() -> FastAPI:
    app: FastAPI = FastAPI(
        debug=True,
        title="I.T.S.",
        description="Intelligent Trading Strategies",
        docs_url="/docs",
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )
    prefix: str = "/api/v1"
    app.include_router(router=share_info_router, prefix="/info", tags=["Share"])
    app.include_router(router=history_router, prefix="/history", tags=["Share"])
    app.include_router(router=cust_bar_router, prefix=prefix, tags=["Custom bars"])

    return app
