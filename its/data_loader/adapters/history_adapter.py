"""Adapter connect to Broker and provide History of instruments"""
import asyncio
from datetime import datetime
from functools import lru_cache

from tinkoff.invest import AsyncClient, CandleInterval
from tinkoff.invest.async_services import AsyncServices
from ..common import models as cm


class HistoryAdapter:
    def __init__(self, token: str) -> None:
        self._token = token

    @staticmethod
    @lru_cache(maxsize=None)
    async def __fetch_all_candles(
        figi: cm.FiGlobalId,
        client: AsyncServices,
        from_,
        interval,
    ):
        result: list = []

        # ToDo Add retrys. it is limited for 200 RPS
        async for candle in client.get_all_candles(
            figi=figi,
            from_=from_,
            interval=interval,
        ):
            result.append(candle)

        return figi, result

    async def fetch_history_by_figis(
        self,
        *,
        figis: set[cm.FiGlobalId],
        from_: datetime,
        interval: CandleInterval,
    ) -> cm.HistoryCatalog:
        async with AsyncClient(self._token) as client:
            aio_tasks: set = {
                # asyncio.create_task(
                self.__fetch_all_candles(
                    figi=figi, client=client, from_=from_, interval=interval
                )
                # )
                for figi in figis
            }
            result = await asyncio.gather(*aio_tasks)

        share_history = {figi: candles for figi, candles in result}

        return share_history
