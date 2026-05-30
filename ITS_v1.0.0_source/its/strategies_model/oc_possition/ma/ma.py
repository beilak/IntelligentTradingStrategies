"""Predict price with MA"""

# import pandas as pd
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache

import numpy as np
from dataclasses import dataclass

# from stsp import PredictResponse
# from custom_stock_bar import
# import custom_bar.converter as conv
from typing import TypedDict
from stsp.protocols.position.close_position import ClosePositionProtocol
from stsp.protocols.position.models import EntryPointResponse, ExitPointResponse
from stsp.protocols.position.open_position import OpenPositionProtocol
from stsp.protocols.models.common import OHLC
from stsp.protocols.predict.models import PredictResponse


@dataclass()
class MaMutableParametrs:
    short_window: int = 70
    long_window: int = 200


# class MAPredictResponse(TypedDict):
#     figi: str | None
#     for_date: datetime | None
#     next_price: Decimal | None
#     symbol: str
#     trend: str  # -1, 0, +1


class MA:
    def __init__(
        self,
        ohlc_provider,
    ) -> None:
        self._parametrs: MaMutableParametrs = MaMutableParametrs()
        self._ohlc_provider = ohlc_provider

    def set_parametrs(self, parameters: MaMutableParametrs) -> None:
        self._parametrs: MaMutableParametrs = parameters

    @lru_cache
    def __load_hist_data_with_cache(
        self,
        symbol: str,
        start_date,
        end_date,
    ):
        return self._ohlc_provider.get_ohlc(
            symbol,
            start_date=start_date,
            end_date=end_date,
        )

    def _load_hist_data(self, symbol: str):
        long_window: int = self._parametrs.long_window
        stock_data_start = date.today() - timedelta(
            days=(long_window * 3),
        )
        stock_data_end = date.today()
        return self.__load_hist_data_with_cache(
            symbol,
            start_date=stock_data_start,
            end_date=stock_data_end,
        )

    def execute(self, symbol: str) -> Any:
        stock_data = self._load_hist_data(
            symbol,
        )
        short_window: int = self._parametrs.short_window
        long_window: int = self._parametrs.long_window
        stock_data["Short_MA"] = (
            stock_data["Close"]
            .rolling(
                window=short_window,
                min_periods=1,
                center=False,
            )
            .mean()
        )
        stock_data["Long_MA"] = (
            stock_data["Close"]
            .rolling(
                window=long_window,
                min_periods=1,
                center=False,
            )
            .mean()
        )

        # # Create a "Signal" column based on the crossover of short and long moving averages
        stock_data["Signal"] = 0
        stock_data["Signal"][short_window:] = np.where(
            stock_data["Short_MA"][short_window:]
            > stock_data["Long_MA"][short_window:],
            1,
            0,
        )

        trend: int = 0
        if stock_data.iloc[-1].Signal == 1:
            trend: int = 1


class MaOpen(MA, OpenPositionProtocol):
    async def definition_entry_point(
        self,
        *,
        ticker: str,
        prediction: PredictResponse,
    ) -> EntryPointResponse: ...


class MaClose(MA, ClosePositionProtocol):
    async def definition_exit_point(
        self,
        *,
        ticker: str,
        prediction: PredictResponse,
    ) -> ExitPointResponse: ...
