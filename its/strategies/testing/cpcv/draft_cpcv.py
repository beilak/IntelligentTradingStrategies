# CombinatorialPurgedCV
from skfolio import Population
from skfolio.model_selection import CombinatorialPurgedCV, cross_val_predict

from its.strategies.core.types.strategy_types import Strategy

strategues: set[Strategy] = set()


asset_universe_prices_close_returns = asset_universe_prices_close.pct_change(
    fill_method=None
).fillna(0)
asset_universe_prices_close_returns.head()

X_train, X_test = train_test_split(
    asset_universe_prices_close_returns, test_size=0.33, shuffle=False
)


cross_val_predict_result_combinatorial_purged_cv: dict[str, Population] = {}
print("CombinatorialPurgedCV")
for strat in strategues:
    print(f"{strat.name = }")

    cv_purgedCV = CombinatorialPurgedCV(n_folds=10, n_test_folds=6)
    cv_purgedCV.summary(X_test)
    cross_val_predict_result_combinatorial_purged_cv[strat.name] = cross_val_predict(
        strat.pipeline,
        X_test,
        cv=cv_purgedCV,
        n_jobs=-1,
        portfolio_params=dict(annualized_factor=252, tag=strat.name),
    )
    print("*" * 10)


def build_predict_population_result(predict_result):
    predict_population = predict_result[0]
    for item in predict_result[1:]:
        predict_population += item
    return predict_population


cross_val_predict_population_purged_cv = build_predict_population_result(
    list(cross_val_predict_result_combinatorial_purged_cv.values())
)
cross_val_predict_population_purged_cv.plot_cumulative_returns()


def get_cpcv_report(results_list):
    report_frames = []

    for name, res in results_list.items():
        df_full = res.summary()

        target_metrics = list(df_full.T.columns)

        # Извлекаем и чистим данные
        df_target = df_full.loc[target_metrics].T

        def clean_metric(series):
            if series.dtype == object:
                return series.str.replace("%", "", regex=False).astype(float) / 100
            return series

        stats = df_target.copy()
        for col in stats.columns:
            if "Sharpe" not in col:
                stats[col] = clean_metric(stats[col])
            else:
                stats[col] = stats[col].astype(float)

        # Формируем расширенный отчет
        strategy_report = {
            "Strategy": name,
            "Ann. Ret (Mean)": f"{stats['Annualized Mean'].mean():.2%}",
            "Ann. Ret (Median)": f"{stats['Annualized Mean'].median():.2%}",
            "Max DD (Median)": f"{stats['MAX Drawdown'].median():.2%}",
            "Worst Case DD (90% Prob)": f"{stats['MAX Drawdown'].quantile(0.9):.2%}",  # Худшая просадка
            "Sharpe (Median)": f"{stats['Annualized Sharpe Ratio'].median():.2f}",
            "Sharpe Stability (Std)": f"{stats['Annualized Sharpe Ratio'].std():.2f}",
            "90% Prob. Ret >": f"{stats['Annualized Mean'].quantile(0.1):.2%}",  # Минимум в 90% случаев
            "Mean CVaR (95%)": f"{stats['CVaR at 95%'].mean():.2%}",  # Средний ожидаемый убыток в 5% самых экстремальных рыночных ситуаций ("среднее дно" кризиса)
            "Mean Kurtosis": f"{stats['Kurtosis'].mean():.2%}",
            "Mean Skew": f"{stats['Skew'].mean():.2%}",  # Асимметрия: отрицательный Skew означает, что риск редких крупных падений выше, чем шансы на резкий рост.
            "Mean Kurtosis": f"{stats['Kurtosis'].mean():.2%}",  # Эксцесс: высокий Kurtosis указывает на «толстые хвосты» (высокую вероятность аномальных шоков и обвалов).
            "Paths Count": len(stats),  # Сколько сценариев было в популяции
        }

        report_frames.append(strategy_report)

    return pd.DataFrame(report_frames).set_index("Strategy").T


# Пример запуска для CPCV
combinatorial_purged_report = get_cpcv_report(
    cross_val_predict_result_combinatorial_purged_cv
)


print("Combinatorial Purged Report")
combinatorial_purged_report.T
