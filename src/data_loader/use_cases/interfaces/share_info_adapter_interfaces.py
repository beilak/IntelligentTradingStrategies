import typing as tp
import src.common.models as cm


class ShareInfoAdapterProtocol(tp.Protocol):
    def fetch_shares_info(self, shares_filter: cm.ShareInfoFilter) -> cm.SharesCatalog:
        """Fetching tickers info with filters"""
