"""Use case OHLC history"""
from datetime import datetime

from ..use_cases import interfaces as protocols
from t_tech.invest import CandleInterval

from ..common import models as cm


class HistoryUseCase:
    def __init__(self, history_adapter: protocols.HistoryAdapterProtocol):
        self._history_adapter = history_adapter

    async def execute(
        self,
        *,
        figis: set[cm.FiGlobalId],
        from_: datetime,
        interval: CandleInterval,
    ) -> cm.HistoryCatalog:
        return await self._history_adapter.fetch_history_by_figis(
            figis=figis,
            from_=from_,
            interval=interval,
        )
