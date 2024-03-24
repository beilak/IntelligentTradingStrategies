"""Adapter connect to Broker and provide Info of instruments"""

from tinkoff.invest import Client, Currency, CurrencyResponse, Share
from tinkoff.invest.schemas import ShareResponse, SharesResponse
from tinkoff.invest.services import InstrumentIdType, InstrumentsService

from ..common import models as cm


class ShareInfoAdapter:
    # STOCK_CLASS_CODE = "CETS"  # "TQBR"

    def __init__(self, token: str, class_code: str) -> None:
        self._token = token
        self._class_code = class_code

    def fetch_share_info_by_tickers(self, tickers: set[str]) -> cm.SharesCatalog:
        """Fetching tickers info"""

        with Client(self._token) as client:
            instruments: InstrumentsService = client.instruments
            share_catalog: cm.SharesCatalog = {}

            for ticker in tickers:
                share: ShareResponse = instruments.share_by(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                    class_code=self._class_code,
                    id=ticker,
                )
                share_catalog[ticker] = share.instrument

            return share_catalog

    def fetch_shares_info(self, shares_filter: cm.ShareInfoFilter) -> cm.SharesCatalog:
        """Fetching tickers info with filters"""

        with Client(self._token) as client:
            instruments: InstrumentsService = client.instruments
            share_catalog: cm.SharesCatalog = {}

            shares: SharesResponse = instruments.shares()
            share: Share
            for share in shares.instruments:
                if not shares_filter.is_share_pass_filter(share=share):
                    continue

                share_catalog[share.ticker] = share

        return share_catalog

    def fetch_curr_info(self, curr_ticker: str) -> Currency:
        with Client(self._token) as client:
            instruments: InstrumentsService = client.instruments

            currency: CurrencyResponse = instruments.currency_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                class_code=self._class_code,
                id=curr_ticker,
            )

        return currency.instrument
