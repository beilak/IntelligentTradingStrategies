import pandas as pd

from its.ga import engine


def test_run_returns_top_strategies_when_materialization_fails(monkeypatch):
    class FakeGA:
        def __init__(self, *args, **kwargs):
            self.population = [[0, 0, 0]]

        def run(self):
            return None

    scored = pd.DataFrame(
        [
            {
                "solution_key": (0, 0, 0),
                "strategy_name": "[GA][selector][signal][allocation]",
                "selector_name": "selector",
                "signal_name": "signal",
                "allocation_name": "allocation",
                "TOTAL_SCORE": 10.0,
                "TOTAL_SCORE_BASE": 10.0,
                "TOTAL_PENALTY": 0.0,
                "WF_Return": 0.1,
                "WF_Calmar": 1.0,
                "WF_Max_Drawdown_Abs": 0.05,
                "WF_Mean_Active_Assets": 5.0,
                "Robustness_Delta": 0.01,
                "Sharpe_Stability": 0.02,
                "evaluation_ok": True,
                "error": None,
            }
        ]
    ).set_index("solution_key", drop=False)

    monkeypatch.setattr(engine.pygad, "GA", FakeGA)
    monkeypatch.setattr(
        engine,
        "build_returns_matrix",
        lambda prices: pd.DataFrame(
            {"AAA": [0.01, 0.02, -0.01, 0.03]},
            index=pd.date_range("2026-01-01", periods=4),
        ),
    )
    monkeypatch.setattr(engine.GASearchRunner, "split_returns", lambda self, returns: (returns.iloc[:2], returns.iloc[2:]))
    monkeypatch.setattr(engine.GASearchRunner, "rank_population", lambda self, population: scored)
    monkeypatch.setattr(engine.GASearchRunner, "rank_all_evaluated", lambda self: scored)
    monkeypatch.setattr(
        engine,
        "materialize_top_strategies",
        lambda **kwargs: (_ for _ in ()).throw(OSError(30, "Read-only file system")),
    )

    result = engine.run_ga_search(
        prices=pd.DataFrame(),
        stocks=[{"figi": "figi", "ticker": "AAA", "name": "AAA"}],
        settings={
            "run_id": "test_run",
            "test_name": "test",
            "sol_per_pop": 2,
            "num_parents_mating": 1,
            "num_generations": 1,
            "top_n": 1,
            "materialize_top": True,
        },
    )

    assert len(result["top_strategies"]) == 1
    assert result["materialized"] == []
    assert "Read-only file system" in result["materialization_error"]
