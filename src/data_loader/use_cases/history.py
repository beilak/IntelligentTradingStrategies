"""Use case OHLC history"""
from datetime import datetime
from tinkoff.invest import CandleInterval
import interfaces as protocols

import src.common.models as cm


class HistoryUseCase:
    def __init__(self, history_adapter: protocols.HistoryAdapterProtocol):
        self._history_adapter = history_adapter

    def execute(
        self,
        *,
        figis: set[cm.FiGlobalId],
        from_: datetime,
        interval: CandleInterval,
    ):
        return self._history_adapter.fetch_history_by_figis(
            figis=figis,
            from_=from_,
            interval=interval,
        )
