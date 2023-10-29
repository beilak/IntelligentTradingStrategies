import typing as tp
from datetime import datetime
from tinkoff.invest import CandleInterval

import src.common.models as cm


class HistoryAdapterProtocol(tp.Protocol):

    def fetch_history_by_figis(
        self,
        *,
        figis: set[cm.FiGlobalId],
        from_: datetime,
        interval: CandleInterval,
    ) -> cm.HistoryCatalog:
        """Fetching tickers info with filters"""
