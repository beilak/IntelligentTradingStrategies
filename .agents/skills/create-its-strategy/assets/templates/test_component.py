import pandas as pd
import pytest

from its.strategies.core.signals import ExampleSignal


def test_example_signal_selects_expected_assets() -> None:
    data = pd.DataFrame({"SELECTED": [0.0, 0.1], "REJECTED": [0.0, -0.1]})
    signal = ExampleSignal(lookback_bars=2).fit(data)
    assert signal.to_keep_.tolist() == [True, False]
    assert list(signal.transform(data).columns) == ["SELECTED"]


def test_example_signal_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="lookback_bars"):
        ExampleSignal(lookback_bars=0).fit(pd.DataFrame({"AAA": [0.0]}))

