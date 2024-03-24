"""IoC container"""
import bakery
from bakery import Cake
from its.adapters.cust_bar_conv import BarConverter
import its.data_loader.adapters as adapters
import its.data_loader.use_cases as use_cases
from its.config import Config
from its.use_cases.custom_bars.custom_bar import CustomBar


class AdaptersIOC(bakery.Bakery):
    """Adapter IoC"""

    config: Config = bakery.Cake(Config.provide_config)

    share_info_adapter: adapters.ShareInfoAdapter = Cake(
        adapters.ShareInfoAdapter,
        token=config.tinkoff_invest_api_token,
        class_code="TQBR",
    )

    currency_info_adapter: adapters.ShareInfoAdapter = Cake(
        adapters.ShareInfoAdapter,
        token=config.tinkoff_invest_api_token,
        class_code="CETS",
    )

    history_adapter: adapters.HistoryAdapter = Cake(
        adapters.HistoryAdapter,
        token=config.tinkoff_invest_api_token,
    )

    gold_bar_conv_adapter: BarConverter = Cake(
        BarConverter,
        base_price_provider=history_adapter,
        base_ticker="GLDRUB_TOM",
        instrument_info=currency_info_adapter,
    )


class UseCasesIOC(bakery.Bakery):
    """Use cases IoC"""

    share_info: use_cases.ShareInfoUseCase = Cake(
        use_cases.ShareInfoUseCase,
        share_info_adapter=AdaptersIOC.share_info_adapter,
    )

    ohlc_history: use_cases.HistoryUseCase = Cake(
        use_cases.HistoryUseCase,
        history_adapter=AdaptersIOC.history_adapter,
    )

    cust_bar: CustomBar = Cake(
        CustomBar,
        bar_converters=Cake(
            {
                "gold": AdaptersIOC.gold_bar_conv_adapter,
            }
        ),
        trade_loader=ohlc_history,
        share_info=AdaptersIOC.share_info_adapter,
    )
