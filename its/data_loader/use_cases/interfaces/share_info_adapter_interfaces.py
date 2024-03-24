import typing as tp

from ...common import models as cm


class ShareInfoAdapterProtocol(tp.Protocol):
    def fetch_shares_info(self, shares_filter: cm.ShareInfoFilter) -> cm.SharesCatalog:
        """Fetching tickers info with filters"""
