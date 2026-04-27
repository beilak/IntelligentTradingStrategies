from t_tech.invest import (
    AsyncClient,
)
from t_tech.invest import (
    AsyncClient,
    CandleInterval,
    Client,
    MoneyValue,
    Quotation,
    TradeDirection,
    utils,
    InstrumentType,
    InstrumentStatus,
    AssetsRequest,
    InstrumentsRequest,
)
import types

from decimal import Decimal
from dataclasses import fields, is_dataclass
import datetime
from t_tech.invest.schemas import(
    IndicativesRequest,
    IndicativeResponse,
)

import pandas as pd



async def get_stock_info(
        tikers: set[str] | None,
        token: str,
        as_df: bool = False,
    ) -> dict[str, IndicativeResponse]:
    figis: dict[str, IndicativeResponse] = dict()
    async with AsyncClient(token) as client:
        for shere in (await client.instruments.shares(
        #     request=InstrumentsRequest(
        #     instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE,
        # )
        )).instruments:
            if tikers:
                if shere.ticker in tikers:
                    figis[shere.ticker] = shere
            else:
                figis[shere.ticker] = shere
    if as_df:
        return pd.DataFrame.from_dict(figis.values())
    return figis

# def get_stock_info_to_df(stock_info: dict[str, IndicativeResponse]) -> pd.DataFrame:
#     return pd.DataFrame.from_dict(stock_info)



async def get_currencies_info(
        tikers: set[str] | None,
        token: str,
        as_df: bool = False,
    ) -> dict[str, IndicativeResponse]:
    figis: dict[str, IndicativeResponse] = dict()
    async with AsyncClient(token) as client:
        for shere in (await client.instruments.currencies(
        #     request=InstrumentsRequest(
        #     instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE,
        # )
        )).instruments:
            if tikers:
                if shere.ticker in tikers:
                    figis[shere.ticker] = shere
            else:
                figis[shere.ticker] = shere
    if as_df:
        return pd.DataFrame.from_dict(figis.values())
    return figis
