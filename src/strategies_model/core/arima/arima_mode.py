"""ARIMA Model"""


class ARIMAmodel:

    def __init__(self, model) -> None:
        self._model = model
        
    def predict_next_bar(self) -> None:
        ...
    