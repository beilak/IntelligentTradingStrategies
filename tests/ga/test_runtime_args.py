import warnings

import pandas as pd
from sklearn.pipeline import Pipeline

from its.ga.materialization import render_static_component
from its.ga.registry import build_component, get_gene
from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import SafeEmptySelector


def test_sector_selector_receives_assets_info_from_runtime_context():
    gene = get_gene("pre_selection", "sector_it_telecom")
    selector = build_component(
        gene,
        runtime_context={
            "asset_universe_prices": pd.DataFrame(),
            "assets_info": pd.DataFrame(
                [
                    {"ticker": "AAA", "sector": "it"},
                    {"ticker": "BBB", "sector": "finance"},
                ]
            ),
        },
    )

    selector.fit(pd.DataFrame([[1.0, 2.0]], columns=["AAA", "BBB"]))

    assert isinstance(selector, SafeEmptySelector)
    assert selector.get_support().tolist() == [True, False]


def test_sector_selector_materialization_uses_builder_assets_info():
    gene = get_gene("pre_selection", "sector_it_telecom")

    component = render_static_component(gene)

    assert "assets_info=self._assets_info" in component.expression


def test_dividend_selector_receives_dividends_info_from_runtime_context():
    gene = get_gene("pre_selection", "DividendHistorySelector")
    selector = build_component(
        gene,
        runtime_context={
            "asset_universe_prices": pd.DataFrame(),
            "dividends_info": pd.DataFrame(
                [
                    {"ticker": "AAA", "last_buy_date": "2023-02-01"},
                    {"ticker": "AAA", "last_buy_date": "2024-02-01"},
                    {"ticker": "AAA", "last_buy_date": "2025-02-01"},
                    {"ticker": "BBB", "last_buy_date": "2025-02-01"},
                ]
            ),
        },
    )

    selector.fit(
        pd.DataFrame(
            [[1.0, 2.0]],
            columns=["AAA", "BBB"],
            index=pd.to_datetime(["2026-01-15"]),
        )
    )

    assert isinstance(selector, SafeEmptySelector)
    assert selector.get_support().tolist() == [True, False]


def test_dividend_selector_materialization_uses_builder_dividends_info():
    gene = get_gene("pre_selection", "DividendHistorySelector")

    component = render_static_component(gene)

    assert "dividends_df=self._dividends_info" in component.expression


def test_ga_signal_empty_selection_falls_back_before_inverse_volatility():
    gene = get_gene("signal", "TwoCandlePositiveTrendSignal")
    signal = build_component(gene)
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 99.0, 98.0],
            "BBB": [100.0, 99.0, 98.0],
        }
    )
    pipeline = Pipeline(
        [
            ("signal", signal),
            ("allocation", InverseVolatility(raise_on_failure=False)),
        ]
    )

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        pipeline.fit(prices)

    assert caught_warnings == []
    assert isinstance(signal, SafeEmptySelector)
    assert signal.empty_selection_ is True
    assert pipeline.named_steps["allocation"].weights_.tolist() == [0.5, 0.5]
