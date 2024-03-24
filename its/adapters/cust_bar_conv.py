import custom_bar.converter as conv
import custom_bar.bar_divider.gold_bar_divider as gold
import pandas as pd
from tinkoff.invest import Currency, CurrencyResponse

from its.data_loader.adapters.share_info_adapter import ShareInfoAdapter
from its.data_loader.common.models import ShareInfoFilter


class BarConverter:
    def __init__(
        self,
        base_price_provider,
        base_ticker,
        instrument_info: ShareInfoAdapter,
    ) -> None:
        base_info: Currency = instrument_info.fetch_curr_info(base_ticker)
        self._base_figi = base_info.figi
        self._base_price_provider = base_price_provider

    def _prepare_converter(self) -> conv.BarConverter:
        base_price_date = self._base_price_provider.fetch_history_by_figis(
            self._base_figi,
        )

        base_price_date_df = base_price_date
        base_bar_provider = gold.GoldBarCalc(
            gold_df=base_price_date_df,
        )

        bar_restrict = gold.GoldBar(
            count=10_000,
            bar_type=gold.GoldBarTypes.T_OUNCE_400,
        )

        bar_divider = gold.GoldBarDivider(
            gold_bar_calc=base_bar_provider,
            gold_bars=bar_restrict,
        )

        return conv.BarConverter(
            bar_divider=bar_divider,
        )

    def make_custom_bars(self, trades: pd.DataFrame) -> pd.DataFrame:
        conv = self._prepare_converter()
        return conv.make_custom_bars(trades=trades)
