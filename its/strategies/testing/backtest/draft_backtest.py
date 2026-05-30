## Бектест лучшей стратегии
import matplotlib.pyplot as plt
from backtesting.vectorbt_backtest import BacktestResult, backtest_strategies_vectorbt

from its.strategies.testing.backtest.vectorbt_backtest import (
    backtest_strategies_vectorbt,
)

asset_universe_prices_full = pd.read_csv(
    f"{data_folder}/asset_universe_prices_full.csv"
)
asset_universe_prices_full.head()

# пример asset_universe_prices_full
#
# 	open	high	low	close	volume	time	is_complete	candle_source	figi	ticker
# 0	55.00	75.00	55.00	73.99	2340	2000-01-04	1.0	1.0	BBG004S682Z6	RTKM
# 1	2.40	2.40	2.40	2.40	8650	2000-01-04	1.0	1.0	BBG004S681M2	SNGSP
# 2	1.02	1.02	1.00	1.00	1787000	2000-01-04	1.0	1.0	BBG004730N88	SBER
# 3	5.40	5.40	5.00	5.00	160	2000-01-04	1.0	1.0	BBG004S683W7	AFLT
# 4	7.89	7.89	7.66	7.66	218	2000-01-04	1.0	1.0	BBG0047315D0	SNGS

asset_universe_prices_close = asset_universe_prices_full.pivot(
    index="time", columns="ticker", values="close"
).sort_index()

asset_universe_prices_close = asset_universe_prices_close.replace(0, np.nan)
asset_universe_prices_close.head()


asset_universe_prices_close_backtesting = asset_universe_prices_close
asset_universe_prices_close_backtesting.index = pd.to_datetime(
    asset_universe_prices_close_backtesting.index
)
best_strat_backtesting_results = backtest_strategies_vectorbt(
    strategies={
        strat for strat in strategues if strat.name == best_strat
    },  # Сюда можно подать сразу несколько стратегий для тестирования
    prices=asset_universe_prices_close_backtesting,
    rebalance_freq="3ME",
    trading_start_date=pd.Timestamp("2010-01-01"),
    fees=0.0008,  # 0.08% fee
    freq="1D",
    init_cash=1_000_000.00,
)


show_backtest_result(best_strat_backtesting_results)


def show_backtest_result(results):
    backtest_result: BacktestResult
    for strat_name, backtest_result in results.items():
        print("*" * 100)
        print(strat_name)
        pf = backtest_result.portfolio
        print(pf.stats())

        pf.plot().show()

        pf.value().vbt.plot()

        pf.drawdowns.plot().show()

        print(f"max_drawdown {pf.drawdowns.max_drawdown()}")
        print(f"max_duration {pf.drawdowns.duration.max()}")

        pf.returns().vbt.histplot()

        rolling_sharpe = (
            pf.returns()
            .rolling(252)
            .apply(lambda x: x.mean() / x.std() * np.sqrt(252), raw=False)
        )

        print(f"Rolling Sharp rate ")

        ax = rolling_sharpe.plot()
        ax.set_title("Rolling Sharpe Ratio")
        plt.show()

        total_return = pf.total_return()

        after_tax_return = total_return * (1 - 0.13)

        labels = ["Доходность до налога", "После налога 13%"]
        values = [total_return, after_tax_return]

        plt.figure(figsize=(6, 6))
        plt.bar(labels, values, color=["skyblue", "orange"])
        plt.ylabel("Итоговая доходность")
        plt.title("Итоговая доходность: до и после налога")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.show()

        print(f"{total_return = }, {after_tax_return = }")

        print("*" * 100)
