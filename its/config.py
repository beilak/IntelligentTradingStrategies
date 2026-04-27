import typing as tp
from datetime import timedelta, datetime

from pydantic import Field
from pydantic_settings import BaseSettings
from t_tech.invest.utils import now
from t_tech.invest import CandleInterval


class Config(BaseSettings):
    debug: bool = True

    tinkoff_invest_api_token: str = Field(alias="TINKOFF_INVEST_API_TOKEN")

    load_share_date_from: datetime = now() - timedelta(days=30 * 12)
    load_currency_date_from: datetime = now() - timedelta(days=30 * 12)

    candle_interval: int = CandleInterval.CANDLE_INTERVAL_HOUR

    shares_for_load: set = {
        "SBER",
    }

    class Config:
        env_file = ".env"  # Works with uvicorn run command from my-app/project/

    @classmethod
    def provide_config(cls) -> tp.Self:
        return Config()
