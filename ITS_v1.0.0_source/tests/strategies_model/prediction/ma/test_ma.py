from its.strategies_model.prediction import MA
from tests.strategies_model.common.ohlc_provider import OhlcProviderForTest


class TestMA:
    @classmethod
    def setup_class(cls):
        """setup any state specific to the execution of the given class (which usually contains tests)."""
        # symbol = "AAPL"
        # start_date = "2020-01-01"
        # end_date = "2022-01-01"
        # cls._stock_data = cls._get_stock_data(symbol, start_date, end_date)

    # @classmethod
    # def _get_stock_data(cls, symbol, start_date, end_date):
    # Download historical stock data using yfinance
    # stock_data = yf.download(symbol, start=start_date, end=end_date)
    # return stock_data

    def test_MA_ok(self) -> None:
        predictor: MA = MA(ohlc_provider=OhlcProviderForTest())
        resutl = predictor.execute("AAPL")

        print(resutl)
        # print(resutl[resutl["Position"] != "0.0"])

        # assert resutl["symbol"] == "AAPL"
        # print(self._stock_data)
