import typing as tp
from datetime import datetime

from t_tech.invest import CandleInterval

from ...common import models as cm


class HistoryAdapterProtocol(tp.Protocol):
    async def fetch_history_by_figis(
        self,
        *,
        figis: set[cm.FiGlobalId],
        from_: datetime,
        interval: CandleInterval,
    ) -> cm.HistoryCatalog:
        """Fetching tickers info with filters"""
