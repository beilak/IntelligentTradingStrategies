import yfinance as yf  # You may need to install this library: pip install yfinance


class OhlcProviderForTest:
    def get_ohlc(
        self,
        symbol: str,
        start_date,
        end_date,
    ):
        return yf.download(
            symbol,
            start=start_date,
            end=end_date,
        )
