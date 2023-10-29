"""Common models"""

import typing as tp
from dataclasses import dataclass
from tinkoff.invest.schemas import HistoricCandle
from tinkoff.invest import Share


FiGlobalId: tp.TypeAlias = int
TickerID: tp.TypeAlias = str
SharesCatalog: tp.TypeAlias = dict[TickerID, Share]
HistoryCatalog: tp.TypeAlias = dict[TickerID, HistoricCandle]


@dataclass
class ShareInfoFilter:
    class_code: str | None = None
    currency: str | None = None
    tickers_name: set[str] | None = None


@dataclass
class ShareInfoFilter:
    class_code: str | None = None
    currency: str | None = None
    tickers_name: set[str] | None = None

    def is_share_pass_filter(self, share: Share) -> bool:
        """Checking this share can pas this filter"""
        if self.class_code and share.class_code != self.class_code:
            return False
        if self.currency and share.currency != self.currency:
            return False
        if self.tickers_name and share.ticker not in self.tickers_name:
            return False

        return True
