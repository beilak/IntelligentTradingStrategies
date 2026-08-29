from types import SimpleNamespace

import pandas as pd

from services.data_backend.app.main import (
    filter_stocks,
    filter_instruments,
    normalize_tradable_instrument,
    resolve_instruments,
)


def test_normalize_tradable_instrument_from_sdk_like_object() -> None:
    instrument = SimpleNamespace(
        figi="figi-1",
        ticker="SBER",
        uid="uid-1",
        position_uid="position-1",
        isin="isin-1",
        name="Sber",
        class_code="TQBR",
        currency="rub",
        exchange="MOEX",
        lot=10,
        api_trade_available_flag=True,
        buy_available_flag=True,
        sell_available_flag=True,
        limit_order_available_flag=True,
        market_order_available_flag=False,
        bestprice_order_available_flag=True,
    )

    assert normalize_tradable_instrument(instrument, "share") == {
        "figi": "figi-1",
        "ticker": "SBER",
        "uid": "uid-1",
        "instrument_uid": "uid-1",
        "position_uid": "position-1",
        "isin": "isin-1",
        "name": "Sber",
        "class_code": "TQBR",
        "instrument_type": "share",
        "currency": "rub",
        "exchange": "MOEX",
        "lot": 10,
        "trading_status": None,
        "real_exchange": None,
        "buy_available_flag": True,
        "sell_available_flag": True,
        "api_trade_available_flag": True,
        "limit_order_available_flag": True,
        "market_order_available_flag": False,
        "bestprice_order_available_flag": True,
    }


def test_filter_instruments_keeps_api_tradable_items() -> None:
    instruments_df = pd.DataFrame(
        [
            {
                "figi": "figi-1",
                "ticker": "SBER",
                "name": "Sber",
                "uid": "uid-1",
                "isin": "isin-1",
                "instrument_type": "share",
                "class_code": "TQBR",
                "exchange": "MOEX",
                "currency": "rub",
                "api_trade_available_flag": True,
            },
            {
                "figi": "figi-2",
                "ticker": "TEST",
                "name": "Blocked",
                "uid": "uid-2",
                "isin": "isin-2",
                "instrument_type": "bond",
                "class_code": "TQOB",
                "exchange": "MOEX",
                "currency": "rub",
                "api_trade_available_flag": False,
            },
        ]
    )

    filtered = filter_instruments(
        instruments_df=instruments_df,
        search="sber",
        instrument_types=["stocks"],
        class_code=None,
        exchange=None,
        currency="rub",
        api_trade_available=True,
    )

    assert filtered["figi"].tolist() == ["figi-1"]


def test_filter_stocks_accepts_multiple_sectors() -> None:
    stocks_df = pd.DataFrame(
        [
            {
                "figi": "figi-1",
                "ticker": "SBER",
                "name": "Sber",
                "class_code": "TQBR",
                "exchange": "MOEX",
                "sector": "financial",
                "country_of_risk": "RU",
            },
            {
                "figi": "figi-2",
                "ticker": "VKCO",
                "name": "VK",
                "class_code": "TQBR",
                "exchange": "MOEX",
                "sector": "it",
                "country_of_risk": "RU",
            },
            {
                "figi": "figi-3",
                "ticker": "GAZP",
                "name": "Gazprom",
                "class_code": "TQBR",
                "exchange": "MOEX",
                "sector": "energy",
                "country_of_risk": "RU",
            },
        ]
    )

    filtered = filter_stocks(
        stocks_df=stocks_df,
        class_code="TQBR",
        search=None,
        tickers=[],
        exchange=None,
        sectors=["it", "energy"],
        country_of_risk=None,
    )

    assert filtered["ticker"].tolist() == ["VKCO", "GAZP"]


def test_resolve_instruments_accepts_figi_without_matching_class_code() -> None:
    instruments_df = pd.DataFrame(
        [
            {
                "figi": "figi-1",
                "ticker": "FUT1",
                "class_code": "SPBFUT",
            }
        ]
    )

    resolved_figis, _ = resolve_instruments(
        instruments_df=instruments_df,
        figis=["figi-1"],
        tickers=[],
        class_code="TQBR",
    )

    assert resolved_figis == ["figi-1"]
