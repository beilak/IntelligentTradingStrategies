"""Common models"""

import typing as tp
from dataclasses import dataclass

from t_tech.invest import Share
from t_tech.invest.schemas import HistoricCandle

FiGlobalId: tp.TypeAlias = str
TickerID: tp.TypeAlias = str
SharesCatalog: tp.TypeAlias = dict[TickerID, Share]
HistoryCatalog: tp.TypeAlias = dict[TickerID, HistoricCandle]


# @dataclass
# class ShareInfoFilter:
#     class_code: str | None = None
#     currency: str | None = None
#     tickers_name: set[str] | None = None
#     exchange: set[str] | None = None


@dataclass
class ShareInfoFilter:
    class_code: str | None = None
    currency: str | None = None
    tickers_name: set[str] | None = None
    exchange: set[str] | None = None

    def is_share_pass_filter(self, share: Share) -> bool:
        """Checking this share can pas this filter"""
        if self.class_code and share.class_code != self.class_code:
            return False
        if self.currency and share.currency != self.currency:
            return False
        if self.tickers_name and share.ticker not in self.tickers_name:
            return False
        if self.exchange and share.exchange not in self.exchange:
            return False

        return True
