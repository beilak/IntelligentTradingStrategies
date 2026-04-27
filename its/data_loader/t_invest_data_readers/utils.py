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


async def get_max_requests_per_second(token: str) -> float:
    async with AsyncClient(token) as client:
        unary_limits = (await client.users.get_user_tariff()).unary_limits

    max_per_second = [
        unary_limit.limit_per_minute
        for unary_limit in unary_limits
        for method in unary_limit.methods
        if "GetCandles" in method
    ][0] / 60

    return max_per_second


async def find_figi(
        tiker: str,
        token: str,
        class_code: str | None = None, 
        instrument_kind: InstrumentType | None = None,
        exchange: str | None = None,
    ) -> IndicativeResponse:
    async with AsyncClient(token) as client:
        for asset in (await client.instruments.get_assets(        
            request=AssetsRequest(
                instrument_type=InstrumentType.INSTRUMENT_TYPE_SHARE,
                instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE,
        ))).assets:
            for inst in asset.instruments:
                if inst.ticker == tiker:
                    return inst
                
async def find_figis(
        tikers: set[str],
        token: str,
        class_code: str = "TQBR", 
        instrument_kind: InstrumentType = InstrumentType.INSTRUMENT_TYPE_SHARE,
        # exchange: str | None = None,
    ) -> dict[str, IndicativeResponse]:
    figis: dict[str, IndicativeResponse] = dict()
    async with AsyncClient(token) as client:
        for asset in (await client.instruments.get_assets(        
            request=AssetsRequest(
                instrument_type=InstrumentType.INSTRUMENT_TYPE_SHARE,
                instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL,
        ))).assets:
            for inst in asset.instruments:
                if inst.ticker in tikers and inst.class_code == class_code and inst.instrument_kind == instrument_kind:
                    figis[inst.ticker] = inst
    return figis

def dataclasses_to_dict(obj: any, dict_factory=dict) -> any:
    if isinstance(obj, types.GeneratorType):
        return dataclasses_to_dict([*obj])
    if isinstance(obj, datetime.datetime):
        return _datetime_to_timestamp(obj)
    if isinstance(obj, MoneyValue):
        return _money_value_to_float(obj)
    if isinstance(obj, Quotation):
        return _quotation_to_float(obj)
    if isinstance(obj, TradeDirection):
        return int(obj)
    if is_dataclass(obj):
        return _dataclass_to_dict(obj, dict_factory=dict_factory)
    if isinstance(obj, tuple) and hasattr(obj, "_fields"):
        return type(obj)(*[dataclasses_to_dict(v, dict_factory) for v in obj])
    if isinstance(obj, (list, tuple)):
        return type(obj)(dataclasses_to_dict(v, dict_factory) for v in obj)
    if isinstance(obj, dict):
        return type(obj)(
            (dataclasses_to_dict(k), dataclasses_to_dict(v))
            for k, v in obj.items()
            if v is not None
        )

    return obj

def _dataclass_to_dict(dataclass, dict_factory=dict) -> dict:
    result = []
    for field in fields(dataclass):
        value = dataclasses_to_dict(
            getattr(dataclass, field.name),
            dict_factory,
        )
        result.append((field.name, value))

    return dict_factory(result)

def _datetime_to_timestamp(datetime_: datetime.datetime):
    if datetime_.hour == 0 and datetime_.minute == 0:
        return pd.Timestamp(datetime_.replace(tzinfo=None))

    return pd.Timestamp(datetime_.astimezone(tz=None).replace(tzinfo=None))


def _money_value_to_float(money_value: MoneyValue) -> float:
    fractional = money_value.nano / Decimal("10e8")
    return float(Decimal(money_value.units) + fractional)


def _quotation_to_float(quotation: Quotation) -> float:
    return float(utils.quotation_to_decimal(quotation))


def _float_to_quotation(float_: float):
    return utils.decimal_to_quotation(Decimal(float_))




def _get_additively_adjusted_prices(
    prices: pd.DataFrame,
    dividends: pd.DataFrame,
    map_column: str = "figi",
) -> pd.DataFrame:
    cumulative_dividends = (
        dividends.pivot_table(
            index="last_buy_date",
            columns=map_column,
            values="dividend_net",
        )
        .reindex(index=prices.index, columns=prices.columns)
        .sort_index(ascending=False)
        .cumsum()
        .ffill()
        .fillna(0)
        .sort_index(ascending=True)
    )

    return prices.subtract(cumulative_dividends).dropna(how="all")



def _get_multiplicatively_adjusted_prices(
    prices: pd.DataFrame,
    dividends: pd.DataFrame,
    map_column: str = "figi",
) -> pd.DataFrame:
    multiplicative_dividends = (
        dividends.pivot_table(
            index="last_buy_date",
            columns=map_column,
            values="yield_value",
        )
        .reindex(index=prices.index, columns=prices.columns)
        .sort_index(ascending=False)
        .map(lambda x: (100 - x) / 100)
        .cumprod()
        .ffill()
        .fillna(1)
        .sort_index(ascending=True)
    )
    return prices.multiply(multiplicative_dividends).dropna(how="all")