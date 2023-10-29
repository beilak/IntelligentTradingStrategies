from datetime import timedelta
from tinkoff.invest.utils import now
from tinkoff.invest import CandleInterval


class Config:
    LOAD_SHARE_DATE_FROM = now() - timedelta(days=30 * 12)
    LOAD_CURRENCY_DATE_FROM = now() - timedelta(days=30 * 12)

    CANDLE_INTERVAL = CandleInterval.CANDLE_INTERVAL_HOUR
    
    SHARES_FOR_LOAD = {
        "SBER",
    }
