import pandas as pd

from its.strategies.testing.cpcv.core import generate_cpcv_report


def test_cpcv_uses_cash_when_model_tickers_are_absent() -> None:
    dates = pd.bdate_range("2024-01-01", periods=30)
    prices = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "figi": f"figi-{ticker}",
                "close": 100.0 + index,
                "high": 101.0 + index,
            }
            for index, date in enumerate(dates)
            for ticker in ["GAZP", "LKOH"]
        ]
    )
    stocks = [
        {"ticker": "GAZP", "figi": "figi-GAZP"},
        {"ticker": "LKOH", "figi": "figi-LKOH"},
    ]

    report = generate_cpcv_report(
        model_name="ModelPullbackWithEQBuilder",
        stocks=stocks,
        prices=prices,
        settings={
            "n_folds": 3,
            "n_test_folds": 2,
            "test_size": 0.33,
        },
    )

    assert report["paths"]
    assert all(path["final_return"] == 0.0 for path in report["paths"])
