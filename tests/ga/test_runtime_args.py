import pandas as pd

from its.ga.materialization import render_static_component
from its.ga.registry import build_component, get_gene


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

    assert selector.get_support().tolist() == [True, False]


def test_sector_selector_materialization_uses_builder_assets_info():
    gene = get_gene("pre_selection", "sector_it_telecom")

    component = render_static_component(gene)

    assert "assets_info=self._assets_info" in component.expression
