import typing as tp
import pandas as pd


class BarConvertorProtocol(tp.Protocol):
    def make_custom_bars(self, trades: pd.DataFrame) -> pd.DataFrame: ...
