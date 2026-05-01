"""ARIMA model fitter"""

import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.arima.model import ARIMAResultsWrapper as ARIMAmodel

import its.data_loader.common.models as common_model


class ArimaFitter:
    def __init__(self, ohlc_history: dict, catalog: dict) -> None:
        self._ohlc_history = ohlc_history
        self._catalog: dict = catalog

    @staticmethod
    def __fit_arima_model(
        ohlc: pd.DataFrame, order: tuple, seasonal_order: tuple
    ) -> any:
        arima_model = ARIMA(
            pd.to_numeric(ohlc.close),
            order=order,
            seasonal_order=seasonal_order,
        )

        return arima_model.fit()

    def arima_rolling_modeling_execute(
        self,
        *,
        arima_order_catalog: dict,
        split_train_rate: int,  # train rate.
    ) -> dict[common_model.FiGlobalId, dict]:
        modeling_result: dict = {}
        for ticker in self._catalog:
            figi = self._catalog[ticker].figi

            ohlc = self._ohlc_history[figi]

            train_count = int(len(ohlc) * (split_train_rate / 100))
            train_ohlc = ohlc[:train_count]
            test_ohlc = ohlc[train_count:]

            predictions = []

            ohlc_for_fit = pd.DataFrame(train_ohlc)

            model_order = arima_order_catalog[figi]

            for t in range(len(test_ohlc)):
                fitted_model: ARIMAmodel = self.__fit_arima_model(
                    ohlc=ohlc_for_fit,
                    order=model_order.order,
                    seasonal_order=model_order.seasonal_order,
                )

                forecast_output = fitted_model.forecast()
                forecast_val = forecast_output.values[0]
                predictions.append(forecast_val)
                next_ohlc_for_train = test_ohlc[t : t + 1]

                ohlc_for_fit = pd.concat([ohlc_for_fit, next_ohlc_for_train])

                modeling_result[figi] = {
                    "fitted_model": fitted_model,
                    "predictions": predictions,
                }
        return modeling_result
