"""Main ARIMA container"""

from its.strategies_model.core.arima.arima_fitter import ArimaFitter


class ArimaContainer:
    @classmethod
    def make_model(cls, ohlc_history: dict, catalog: dict):
        fitter: ArimaFitter = ArimaFitter(
            ohlc_history=ohlc_history,
            catalog=catalog,
        )
