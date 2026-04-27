from datetime import datetime
from t_tech.invest import CandleInterval
from its.data_loader.adapters.share_info_adapter import ShareInfoAdapter
from its.data_loader.use_cases.history import HistoryUseCase
from its.data_loader.use_cases.share_info import ShareInfoUseCase
from its.use_cases.custom_bars.protocols.bar_converter import BarConvertorProtocol
import pandas as pd


class CustomBar:
    def __init__(
        self,
        bar_converters: dict[str, BarConvertorProtocol],
        trade_loader: HistoryUseCase,
        share_info: ShareInfoAdapter,
    ) -> None:
        self._bar_convertors: dict[str, BarConvertorProtocol] = bar_converters
        self._trade_loader = trade_loader
        self._share_info = share_info

    async def execute(
        self,
        ticker_name: str,
        bar_type,
        date_from: datetime,
    ) -> pd.DataFrame:
        infos: dict = self._share_info.fetch_share_info_by_tickers(
            tickers={
                ticker_name,
            }
        )
        # print("*" * 100, date_from)
        figi = infos[ticker_name].figi
        trades = await self._trade_loader.execute(
            figis={
                figi,
            },
            from_=date_from,
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        )
        # print(trades[])
        # for i

        # trades_df = trades[ticker_name]

        # print(">>" * 10, trades_df)
        #
        # convertor = self._bar_convertors[bar_type]
        # if not convertor:
        #     raise TypeError
        # return convertor.make_custom_bars(trades=trades_df)

        return pd.DataFrame()
