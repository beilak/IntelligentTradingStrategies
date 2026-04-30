import pandas as pd
from custom_bar.bar_divider import gold_bar_divider as cust_gold
from custom_bar.converter import BarConverter


def parse_gold_bar_type(bar_type: str) -> cust_gold.GoldBarTypes:
    normalized = bar_type.strip().upper()
    return cust_gold.GoldBarTypes[normalized]


def build_custom_gold_bars(
    prices_df: pd.DataFrame,
    gold_prices_df: pd.DataFrame,
    count: int,
    bar_type: cust_gold.GoldBarTypes,
) -> pd.DataFrame:
    if prices_df.empty or gold_prices_df.empty:
        return pd.DataFrame()

    gold_for_converter = prepare_converter_prices(gold_prices_df)
    gold_bar_provider = cust_gold.GoldBarCalc(gold_df=gold_for_converter)
    bar_divider = cust_gold.GoldBarDivider(
        gold_bar_calc=gold_bar_provider,
        gold_bars=cust_gold.GoldBar(count=count, bar_type=bar_type),
    )
    gold_bar_converter = BarConverter(bar_divider=bar_divider)

    converted: list[pd.DataFrame] = []
    for figi, figi_prices in prices_df.sort_values("time").groupby("figi", dropna=False):
        converter_prices = prepare_converter_prices(figi_prices)
        if converter_prices.empty:
            continue

        figi_bars = gold_bar_converter.make_custom_bars(trades=converter_prices)
        if figi_bars.empty:
            continue

        figi_bars = figi_bars.reset_index(drop=True).rename(
            columns={"date_time": "time"}
        )
        figi_bars["figi"] = figi
        if "is_complete" in figi_prices.columns:
            figi_bars["is_complete"] = True
        converted.append(figi_bars)

    if not converted:
        return pd.DataFrame()

    return pd.concat(converted, ignore_index=True, sort=False)


def prepare_converter_prices(prices_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = ["open", "high", "low", "close", "volume", "time"]
    existing = [column for column in required_columns if column in prices_df.columns]
    prepared = prices_df.loc[:, existing].copy()
    for column in required_columns:
        if column not in prepared.columns:
            prepared[column] = 0

    prepared["date_time"] = pd.to_datetime(prepared["time"], errors="coerce")
    prepared = prepared.loc[prepared["date_time"].notna()].copy()
    for column in ["open", "high", "low", "close", "volume"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype(
            float
        )
    prepared = prepared.dropna(subset=["open", "high", "low", "close", "volume"])
    return prepared.sort_values("date_time").reset_index(drop=True)


def build_gold_bar_types() -> list[dict[str, object]]:
    return [
        {
            "name": item.name,
            "grams": float(item.value),
        }
        for item in cust_gold.GoldBarTypes
    ]
