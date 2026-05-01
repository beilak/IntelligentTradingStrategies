import asyncio
import math
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from t_tech.invest import CandleInterval

from its.data_loader.custom_bar.gold_bar import (
    build_custom_gold_bars,
    build_gold_bar_types,
    parse_gold_bar_type as parse_gold_bar_type_name,
)
from its.data_loader.t_invest_data_readers.prices_reader import get_prices
from its.data_loader.t_invest_data_readers.dividents_reader import get_dividends
from its.data_loader.t_invest_data_readers.stock_info import (
    get_currencies_info,
    get_stock_info,
)

API_PREFIX = "/api/v1"
DEFAULT_CLASS_CODE = "TQBR"
DEFAULT_INTERVAL = "CANDLE_INTERVAL_DAY"
DEFAULT_DIVIDEND_START_YEAR = 2010
DEFAULT_GOLD_TICKER = "GLDRUB_TOM"
DEFAULT_GOLD_CLASS_CODE = "CETS"
DEFAULT_INSTRUMENT_TYPE = "stocks"

DIVIDEND_COLUMNS = [
    "dividend_net",
    "payment_date",
    "declared_date",
    "last_buy_date",
    "dividend_type",
    "record_date",
    "regularity",
    "close_price",
    "yield_value",
    "created_at",
    "figi",
    "ticker",
]

STOCK_COLUMNS = [
    "figi",
    "ticker",
    "uid",
    "isin",
    "name",
    "class_code",
    "currency",
    "exchange",
    "sector",
    "country_of_risk",
    "country_of_risk_name",
    "share_type",
    "lot",
    "trading_status",
    "real_exchange",
    "buy_available_flag",
    "sell_available_flag",
    "api_trade_available_flag",
    "short_enabled_flag",
    "for_qual_investor_flag",
]

CURRENCY_COLUMNS = [
    "figi",
    "ticker",
    "uid",
    "position_uid",
    "iso_currency_name",
    "name",
    "class_code",
    "currency",
    "exchange",
    "country_of_risk",
    "country_of_risk_name",
    "lot",
    "trading_status",
    "real_exchange",
    "buy_available_flag",
    "sell_available_flag",
    "api_trade_available_flag",
    "for_qual_investor_flag",
    "weekend_flag",
]

PRICE_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "time",
    "is_complete",
    "candle_source",
    "volume_buy",
    "volume_sell",
    "figi",
    "ticker",
]

SUPPORTED_INTERVALS = {
    "CANDLE_INTERVAL_1_MIN": CandleInterval.CANDLE_INTERVAL_1_MIN,
    "CANDLE_INTERVAL_5_MIN": CandleInterval.CANDLE_INTERVAL_5_MIN,
    "CANDLE_INTERVAL_15_MIN": CandleInterval.CANDLE_INTERVAL_15_MIN,
    "CANDLE_INTERVAL_HOUR": CandleInterval.CANDLE_INTERVAL_HOUR,
    "CANDLE_INTERVAL_DAY": CandleInterval.CANDLE_INTERVAL_DAY,
    "CANDLE_INTERVAL_WEEK": CandleInterval.CANDLE_INTERVAL_WEEK,
    "CANDLE_INTERVAL_MONTH": CandleInterval.CANDLE_INTERVAL_MONTH,
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="ITS Data Backend",
        description="Async data API for Intelligent Trading Strategies",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    gateway = TInvestGateway()

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/sources")
    async def sources() -> dict[str, object]:
        return {
            "items": [
                {
                    "id": "tinkoff-invest",
                    "name": "Tinkoff Invest",
                    "status": "active",
                    "resources": ["stocks", "currencies", "prices"],
                    "intervals": list(SUPPORTED_INTERVALS),
                },
                {
                    "id": "dividends",
                    "name": "Dividends",
                    "status": "active",
                    "resources": ["dividends"],
                    "intervals": [],
                },
            ]
        }

    @app.get(f"{API_PREFIX}/stocks")
    async def stocks(
        class_code: str | None = DEFAULT_CLASS_CODE,
        search: str | None = None,
        tickers: Annotated[list[str] | None, Query()] = None,
        exchange: str | None = None,
        sector: str | None = None,
        country_of_risk: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, object]:
        token = get_tinvest_token()
        stocks_df = await gateway.get_stocks(token)
        filtered = filter_stocks(
            stocks_df=stocks_df,
            class_code=class_code,
            search=search,
            tickers=split_query_list(tickers),
            exchange=exchange,
            sector=sector,
            country_of_risk=country_of_risk,
        )
        total = len(filtered)
        page = filtered.iloc[offset : offset + limit]

        return {
            "items": dataframe_to_records(page, STOCK_COLUMNS),
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": build_stock_filters(stocks_df),
        }

    @app.get(f"{API_PREFIX}/currencies")
    async def currencies(
        class_code: str | None = None,
        search: str | None = None,
        tickers: Annotated[list[str] | None, Query()] = None,
        exchange: str | None = None,
        country_of_risk: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, object]:
        token = get_tinvest_token()
        currencies_df = await gateway.get_currencies(token)
        filtered = filter_currencies(
            currencies_df=currencies_df,
            class_code=class_code,
            search=search,
            tickers=split_query_list(tickers),
            exchange=exchange,
            country_of_risk=country_of_risk,
        )
        total = len(filtered)
        page = filtered.iloc[offset : offset + limit]

        return {
            "items": dataframe_to_records(page, CURRENCY_COLUMNS),
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": build_currency_filters(currencies_df),
        }

    @app.get(f"{API_PREFIX}/prices")
    async def prices(
        figis: Annotated[list[str] | None, Query()] = None,
        tickers: Annotated[list[str] | None, Query()] = None,
        class_code: str | None = DEFAULT_CLASS_CODE,
        instrument_type: str = DEFAULT_INSTRUMENT_TYPE,
        start_date: date | None = None,
        end_date: date | None = None,
        interval: str = DEFAULT_INTERVAL,
        is_complete: bool = True,
    ) -> dict[str, object]:
        token = get_tinvest_token()
        parsed_interval = parse_interval(interval)
        requested_figis = split_query_list(figis)
        requested_tickers = split_query_list(tickers)

        if not requested_figis and not requested_tickers:
            raise HTTPException(
                status_code=422,
                detail="Pass at least one figi or ticker.",
            )

        current_end = pd.Timestamp(end_date or datetime.utcnow().date())
        current_start = pd.Timestamp(
            start_date or (current_end - pd.Timedelta(days=180)).date()
        )
        if current_start > current_end:
            raise HTTPException(
                status_code=422, detail="start_date must be before end_date."
            )

        instruments_df = await get_instruments_frame(gateway, token, instrument_type)
        resolved_figis, figi_ticker_map = resolve_instruments(
            instruments_df=instruments_df,
            figis=requested_figis,
            tickers=requested_tickers,
            class_code=class_code,
        )

        if not resolved_figis:
            raise HTTPException(
                status_code=404, detail="No instruments found for request."
            )

        prices_df = await get_prices(
            figis=resolved_figis,
            start_date=current_start,
            end_date=current_end,
            interval=parsed_interval,
            token=token,
            is_complete=is_complete,
        )

        if prices_df.empty:
            return {
                "items": [],
                "meta": build_prices_meta(
                    resolved_figis,
                    figi_ticker_map,
                    current_start,
                    current_end,
                    interval,
                    is_complete,
                ),
                "summary": [],
            }

        prices_df = prices_df.copy()
        if "ticker" not in prices_df.columns:
            prices_df["ticker"] = prices_df["figi"].map(figi_ticker_map)
        prices_df = prices_df.sort_values(["ticker", "time"])

        return {
            "items": dataframe_to_records(prices_df, PRICE_COLUMNS),
            "meta": build_prices_meta(
                resolved_figis,
                figi_ticker_map,
                current_start,
                current_end,
                interval,
                is_complete,
            ),
            "summary": build_price_summary(prices_df),
        }

    @app.get(f"{API_PREFIX}/custom-gold-bars")
    async def custom_gold_bars(
        figis: Annotated[list[str] | None, Query()] = None,
        tickers: Annotated[list[str] | None, Query()] = None,
        class_code: str | None = DEFAULT_CLASS_CODE,
        instrument_type: str = DEFAULT_INSTRUMENT_TYPE,
        gold_ticker: str = DEFAULT_GOLD_TICKER,
        gold_class_code: str | None = DEFAULT_GOLD_CLASS_CODE,
        start_date: date | None = None,
        end_date: date | None = None,
        interval: str = DEFAULT_INTERVAL,
        is_complete: bool = True,
        count: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
        bar_type: str = "T_OUNCE_400",
    ) -> dict[str, object]:
        token = get_tinvest_token()
        parsed_interval = parse_interval(interval)
        requested_figis = split_query_list(figis)
        requested_tickers = split_query_list(tickers)
        gold_bar_type = parse_gold_bar_type(bar_type)

        if not requested_figis and not requested_tickers:
            raise HTTPException(
                status_code=422,
                detail="Pass at least one figi or ticker.",
            )

        current_end = pd.Timestamp(end_date or datetime.utcnow().date())
        current_start = pd.Timestamp(
            start_date or (current_end - pd.Timedelta(days=180)).date()
        )
        if current_start > current_end:
            raise HTTPException(
                status_code=422, detail="start_date must be before end_date."
            )

        instruments_df = await get_instruments_frame(gateway, token, instrument_type)
        resolved_figis, figi_ticker_map = resolve_instruments(
            instruments_df=instruments_df,
            figis=requested_figis,
            tickers=requested_tickers,
            class_code=class_code,
        )
        if not resolved_figis:
            raise HTTPException(
                status_code=404, detail="No instruments found for request."
            )

        currencies_df = await gateway.get_currencies(token)
        gold_figis, gold_figi_ticker_map = resolve_instruments(
            instruments_df=currencies_df,
            figis=[],
            tickers=[gold_ticker],
            class_code=gold_class_code,
        )
        if not gold_figis:
            raise HTTPException(
                status_code=404,
                detail=f"Gold instrument {gold_ticker} was not found.",
            )

        prices_df, gold_prices_df = await asyncio.gather(
            get_prices(
                figis=resolved_figis,
                start_date=current_start,
                end_date=current_end,
                interval=parsed_interval,
                token=token,
                is_complete=is_complete,
            ),
            get_prices(
                figis=gold_figis,
                start_date=current_start,
                end_date=current_end,
                interval=parsed_interval,
                token=token,
                is_complete=is_complete,
            ),
        )

        custom_bars_df = build_custom_gold_bars(
            prices_df=prices_df,
            gold_prices_df=gold_prices_df,
            count=count,
            bar_type=gold_bar_type,
        )

        if not custom_bars_df.empty and "ticker" not in custom_bars_df.columns:
            custom_bars_df["ticker"] = custom_bars_df["figi"].map(figi_ticker_map)
        if not custom_bars_df.empty:
            custom_bars_df = custom_bars_df.sort_values(["ticker", "time"])

        return {
            "items": dataframe_to_records(custom_bars_df, PRICE_COLUMNS),
            "meta": {
                **build_prices_meta(
                    resolved_figis,
                    figi_ticker_map,
                    current_start,
                    current_end,
                    interval,
                    is_complete,
                ),
                "instrument_type": instrument_type,
                "gold_figi": gold_figis[0],
                "gold_ticker": gold_figi_ticker_map.get(gold_figis[0], gold_ticker),
                "count": count,
                "bar_type": gold_bar_type.name,
                "gold_bar_types": build_gold_bar_types(),
            },
            "summary": build_price_summary(custom_bars_df),
        }

    @app.get(f"{API_PREFIX}/dividends")
    async def dividends(
        figis: Annotated[list[str] | None, Query()] = None,
        tickers: Annotated[list[str] | None, Query()] = None,
        class_code: str = DEFAULT_CLASS_CODE,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, object]:
        token = get_tinvest_token()
        requested_figis = split_query_list(figis)
        requested_tickers = split_query_list(tickers)

        if not requested_figis and not requested_tickers:
            raise HTTPException(
                status_code=422,
                detail="Pass at least one figi or ticker.",
            )

        current_end = pd.Timestamp(end_date or datetime.utcnow().date())
        current_start = pd.Timestamp(
            start_date
            or (
                current_end
                - pd.Timedelta(
                    days=365 * (datetime.utcnow().year - DEFAULT_DIVIDEND_START_YEAR)
                )
            ).date()
        )
        if current_start > current_end:
            raise HTTPException(
                status_code=422, detail="start_date must be before end_date."
            )

        stocks_df = await gateway.get_stocks(token)
        resolved_figis, figi_ticker_map = resolve_instruments(
            instruments_df=stocks_df,
            figis=requested_figis,
            tickers=requested_tickers,
            class_code=class_code,
        )

        if not resolved_figis:
            raise HTTPException(
                status_code=404, detail="No instruments found for request."
            )

        dividends_df = await get_dividends(
            figis=resolved_figis,
            start_date=current_start,
            end_date=current_end,
            token=token,
        )

        if dividends_df.empty:
            return {
                "items": [],
                "meta": build_dividends_meta(
                    resolved_figis,
                    figi_ticker_map,
                    current_start,
                    current_end,
                ),
                "summary": [],
            }

        dividends_df = dividends_df.copy()
        if "ticker" not in dividends_df.columns:
            dividends_df["ticker"] = dividends_df["figi"].map(figi_ticker_map)
        dividends_df = dividends_df.sort_values(["ticker", "payment_date"])

        return {
            "items": dataframe_to_records(dividends_df, DIVIDEND_COLUMNS),
            "meta": build_dividends_meta(
                resolved_figis,
                figi_ticker_map,
                current_start,
                current_end,
            ),
            "summary": build_dividends_summary(dividends_df),
        }

    return app


class TInvestGateway:
    def __init__(self) -> None:
        ttl_minutes = int(os.getenv("DATA_BACKEND_STOCKS_TTL_MINUTES", "30"))
        self._stocks_ttl = timedelta(minutes=ttl_minutes)
        self._stocks_cache: pd.DataFrame | None = None
        self._stocks_loaded_at: datetime | None = None
        self._currencies_cache: pd.DataFrame | None = None
        self._currencies_loaded_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def get_stocks(self, token: str) -> pd.DataFrame:
        if self._is_stocks_cache_fresh():
            return self._stocks_cache.copy()  # type: ignore[union-attr]

        async with self._lock:
            if self._is_stocks_cache_fresh():
                return self._stocks_cache.copy()  # type: ignore[union-attr]

            stocks_df = await get_stock_info(tikers=None, as_df=True, token=token)
            self._stocks_cache = normalize_stocks_frame(stocks_df)
            self._stocks_loaded_at = datetime.utcnow()
            return self._stocks_cache.copy()

    async def get_currencies(self, token: str) -> pd.DataFrame:
        if self._is_currencies_cache_fresh():
            return self._currencies_cache.copy()  # type: ignore[union-attr]

        async with self._lock:
            if self._is_currencies_cache_fresh():
                return self._currencies_cache.copy()  # type: ignore[union-attr]

            currencies_df = await get_currencies_info(
                tikers=None, as_df=True, token=token
            )
            self._currencies_cache = normalize_currencies_frame(currencies_df)
            self._currencies_loaded_at = datetime.utcnow()
            return self._currencies_cache.copy()

    def _is_stocks_cache_fresh(self) -> bool:
        if self._stocks_cache is None or self._stocks_loaded_at is None:
            return False
        return datetime.utcnow() - self._stocks_loaded_at < self._stocks_ttl

    def _is_currencies_cache_fresh(self) -> bool:
        if self._currencies_cache is None or self._currencies_loaded_at is None:
            return False
        return datetime.utcnow() - self._currencies_loaded_at < self._stocks_ttl


def get_tinvest_token() -> str:
    token = (
        os.getenv("tinvest_token")
        or os.getenv("TINVEST_TOKEN")
        or os.getenv("TINKOFF_INVEST_API_TOKEN")
    )
    if not token:
        raise HTTPException(
            status_code=503,
            detail=(
                "Tinkoff Invest token is not configured. Set tinvest_token, "
                "TINVEST_TOKEN or TINKOFF_INVEST_API_TOKEN."
            ),
        )
    return token


def parse_interval(interval: str) -> CandleInterval:
    interval_key = interval.strip().upper()
    if interval_key not in SUPPORTED_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported interval. Use one of: {', '.join(SUPPORTED_INTERVALS)}.",
        )
    return SUPPORTED_INTERVALS[interval_key]


def parse_instrument_type(instrument_type: str) -> str:
    normalized = instrument_type.strip().lower()
    if normalized not in {"stocks", "currencies"}:
        raise HTTPException(
            status_code=422,
            detail="Unsupported instrument_type. Use stocks or currencies.",
        )
    return normalized


async def get_instruments_frame(
    gateway: TInvestGateway,
    token: str,
    instrument_type: str,
) -> pd.DataFrame:
    normalized = parse_instrument_type(instrument_type)
    if normalized == "currencies":
        return await gateway.get_currencies(token)
    return await gateway.get_stocks(token)


def parse_gold_bar_type(bar_type: str):
    try:
        return parse_gold_bar_type_name(bar_type)
    except KeyError as error:
        supported = ", ".join(item["name"] for item in build_gold_bar_types())
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported gold bar type. Use one of: {supported}.",
        ) from error


def split_query_list(values: list[str] | None) -> list[str]:
    if not values:
        return []

    normalized: list[str] = []
    for value in values:
        normalized.extend(part.strip() for part in value.split(",") if part.strip())
    return list(dict.fromkeys(normalized))


def normalize_stocks_frame(stocks_df: pd.DataFrame) -> pd.DataFrame:
    if stocks_df.empty:
        return pd.DataFrame(columns=STOCK_COLUMNS)

    prepared = stocks_df.copy()
    for column in STOCK_COLUMNS:
        if column not in prepared.columns:
            prepared[column] = None

    return prepared.sort_values(["ticker", "figi"], na_position="last").reset_index(
        drop=True
    )


def normalize_currencies_frame(currencies_df: pd.DataFrame) -> pd.DataFrame:
    if currencies_df.empty:
        return pd.DataFrame(columns=CURRENCY_COLUMNS)

    prepared = currencies_df.copy()
    for column in CURRENCY_COLUMNS:
        if column not in prepared.columns:
            prepared[column] = None

    return prepared.sort_values(["ticker", "figi"], na_position="last").reset_index(
        drop=True
    )


def filter_stocks(
    stocks_df: pd.DataFrame,
    class_code: str | None,
    search: str | None,
    tickers: list[str],
    exchange: str | None,
    sector: str | None,
    country_of_risk: str | None,
) -> pd.DataFrame:
    filtered = stocks_df.copy()

    if class_code:
        filtered = filtered.loc[
            filtered["class_code"].astype(str).str.upper() == class_code.upper()
        ]
    if tickers:
        ticker_set = {ticker.upper() for ticker in tickers}
        filtered = filtered.loc[
            filtered["ticker"].astype(str).str.upper().isin(ticker_set)
        ]
    if search:
        needle = search.strip().lower()
        filtered = filtered.loc[
            filtered["ticker"].astype(str).str.lower().str.contains(needle, na=False)
            | filtered["name"].astype(str).str.lower().str.contains(needle, na=False)
        ]
    if exchange:
        filtered = filtered.loc[
            filtered["exchange"].astype(str).str.upper() == exchange.upper()
        ]
    if sector:
        filtered = filtered.loc[
            filtered["sector"].astype(str).str.lower() == sector.lower()
        ]
    if country_of_risk:
        filtered = filtered.loc[
            filtered["country_of_risk"].astype(str).str.upper()
            == country_of_risk.upper()
        ]

    return filtered.reset_index(drop=True)


def filter_currencies(
    currencies_df: pd.DataFrame,
    class_code: str | None,
    search: str | None,
    tickers: list[str],
    exchange: str | None,
    country_of_risk: str | None,
) -> pd.DataFrame:
    filtered = currencies_df.copy()

    if class_code:
        filtered = filtered.loc[
            filtered["class_code"].astype(str).str.upper() == class_code.upper()
        ]
    if tickers:
        ticker_set = {ticker.upper() for ticker in tickers}
        filtered = filtered.loc[
            filtered["ticker"].astype(str).str.upper().isin(ticker_set)
        ]
    if search:
        needle = search.strip().lower()
        filtered = filtered.loc[
            filtered["ticker"].astype(str).str.lower().str.contains(needle, na=False)
            | filtered["name"].astype(str).str.lower().str.contains(needle, na=False)
            | filtered["iso_currency_name"]
            .astype(str)
            .str.lower()
            .str.contains(needle, na=False)
        ]
    if exchange:
        filtered = filtered.loc[
            filtered["exchange"].astype(str).str.upper() == exchange.upper()
        ]
    if country_of_risk:
        filtered = filtered.loc[
            filtered["country_of_risk"].astype(str).str.upper()
            == country_of_risk.upper()
        ]

    return filtered.reset_index(drop=True)


def resolve_instruments(
    instruments_df: pd.DataFrame,
    figis: list[str],
    tickers: list[str],
    class_code: str | None,
) -> tuple[list[str], dict[str, str]]:
    filtered = instruments_df.copy()
    if class_code:
        filtered = filtered.loc[
            filtered["class_code"].astype(str).str.upper() == class_code.upper()
        ]

    figi_ticker_map = {
        str(row.figi): str(row.ticker)
        for row in filtered[["figi", "ticker"]].dropna().itertuples(index=False)
    }

    resolved_figis = [figi for figi in figis if figi]
    if tickers:
        ticker_set = {ticker.upper() for ticker in tickers}
        ticker_matches = filtered.loc[
            filtered["ticker"].astype(str).str.upper().isin(ticker_set),
            ["figi", "ticker"],
        ]
        resolved_figis.extend(
            str(row.figi) for row in ticker_matches.itertuples(index=False)
        )
        figi_ticker_map.update(
            {
                str(row.figi): str(row.ticker)
                for row in ticker_matches.itertuples(index=False)
                if row.figi
            }
        )

    return list(dict.fromkeys(resolved_figis)), figi_ticker_map


def build_stock_filters(stocks_df: pd.DataFrame) -> dict[str, list[str]]:
    return {
        "class_codes": unique_values(stocks_df, "class_code"),
        "exchanges": unique_values(stocks_df, "exchange"),
        "sectors": unique_values(stocks_df, "sector"),
        "countries": unique_values(stocks_df, "country_of_risk"),
        "intervals": list(SUPPORTED_INTERVALS),
    }


def build_currency_filters(currencies_df: pd.DataFrame) -> dict[str, list[str]]:
    return {
        "class_codes": unique_values(currencies_df, "class_code"),
        "exchanges": unique_values(currencies_df, "exchange"),
        "countries": unique_values(currencies_df, "country_of_risk"),
        "intervals": list(SUPPORTED_INTERVALS),
    }


def unique_values(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    values = [str(value) for value in df[column].dropna().unique() if str(value)]
    return sorted(values)


def build_prices_meta(
    figis: list[str],
    figi_ticker_map: dict[str, str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    interval: str,
    is_complete: bool,
) -> dict[str, object]:
    return {
        "figis": figis,
        "tickers": [figi_ticker_map.get(figi, figi) for figi in figis],
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
        "interval": interval,
        "is_complete": is_complete,
    }


def build_price_summary(prices_df: pd.DataFrame) -> list[dict[str, object]]:
    if prices_df.empty:
        return []

    summary: list[dict[str, object]] = []
    for ticker, group in prices_df.sort_values("time").groupby("ticker", dropna=False):
        last = group.iloc[-1]
        first = group.iloc[0]
        first_close = safe_float(first.get("close"))
        last_close = safe_float(last.get("close"))
        change_pct = None
        if first_close and last_close:
            change_pct = ((last_close - first_close) / first_close) * 100

        summary.append(
            {
                "ticker": sanitize_scalar(ticker),
                "figi": sanitize_scalar(last.get("figi")),
                "last_close": last_close,
                "change_pct": change_pct,
                "candles": int(len(group)),
                "from": sanitize_scalar(first.get("time")),
                "to": sanitize_scalar(last.get("time")),
            }
        )

    return summary


def build_dividends_meta(
    figis: list[str],
    figi_ticker_map: dict[str, str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> dict[str, object]:
    return {
        "figis": figis,
        "tickers": [figi_ticker_map.get(figi, figi) for figi in figis],
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
    }


def build_dividends_summary(dividends_df: pd.DataFrame) -> list[dict[str, object]]:
    if dividends_df.empty:
        return []

    summary: list[dict[str, object]] = []
    for ticker, group in dividends_df.sort_values("payment_date").groupby(
        "ticker", dropna=False
    ):
        total_net = safe_float(group["dividend_net"].sum())
        count = int(len(group))

        last = group.iloc[-1]
        last_payment = last.get("payment_date")

        summary.append(
            {
                "ticker": sanitize_scalar(ticker),
                "figi": sanitize_scalar(last.get("figi")),
                "total_net": total_net,
                "count": count,
                "last_payment": sanitize_scalar(last_payment),
            }
        )

    return summary


def dataframe_to_records(
    df: pd.DataFrame, columns: list[str]
) -> list[dict[str, object]]:
    if df.empty:
        return []

    existing_columns = [column for column in columns if column in df.columns]
    prepared = df.loc[:, existing_columns].copy()

    return [
        {column: sanitize_scalar(value) for column, value in row.items()}
        for row in prepared.to_dict(orient="records")
    ]


def sanitize_scalar(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "item"):
        try:
            return sanitize_scalar(value.item())
        except (AttributeError, ValueError):
            pass

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


def safe_float(value: object) -> float | None:
    sanitized = sanitize_scalar(value)
    if sanitized is None:
        return None
    try:
        return float(sanitized)
    except (TypeError, ValueError):
        return None


app = create_app()
