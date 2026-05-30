 from skfolio import Population
 from skfolio.model_selection import  WalkForward, cross_val_predict



# # # WalkForward
cross_val_predict_result_combinatorial_WalkForward: dict[str, Population] = {}
# * Rebalancing    : pd.DateOffset(months=3)
# * Test Duration  : 1 quarter
# * Train Duration : 3 months
cv_wf = WalkForward(test_size=1, train_size=pd.DateOffset(months=3), freq=pd.DateOffset(months=3)) #, purged_size=1)

X_test_wf = X_test.copy()
X_test_wf.index = pd.to_datetime(X_test_wf.index)

print("WalkForward")
for strat in strategues:
    print(f"{strat.name = }")
    cross_val_predict_result_combinatorial_WalkForward[strat.name] = cross_val_predict(
            strat.pipeline,
            X_test_wf,
            cv=cv_wf,
            n_jobs=-1,
            portfolio_params=dict(annualized_factor=252, tag=strat.name),
        )
    print("*"*10)


import copy
cross_val_predict_result_combinatorial_WalkForward_output = copy.deepcopy(list(cross_val_predict_result_combinatorial_WalkForward.values()))
plot_cumulative_returns(cross_val_predict_result_combinatorial_WalkForward_output)



import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px


def plot_cumulative_returns(predict_result_combinatorial):
    combined_fig = go.Figure()
    colors = px.colors.qualitative.Plotly


    # Проходим по всем результатам и добавляем их трассы в один график
    for window_idx, result in enumerate(predict_result_combinatorial):
        fig = result.plot_cumulative_returns()

        # Выбираем цвет из палитры (зацикливаемся если цветов меньше чем складок)
        color = colors[window_idx % len(colors)]
        # Добавляем все трассы из текущего figure
        for trace in fig.data:
            if result.tag:
                trace.name = f"{result.tag} item {window_idx + 1}"  # Добавляем метку для каждой складки
            else:
                trace.name = f"{result.name} item {window_idx + 1}"  # Добавляем метку для каждой складки

            trace.line.color = color
            trace.line.width = 2  # Делаем линии немного толще
            combined_fig.add_trace(trace)

    # Настраиваем общий график
    combined_fig.update_layout(
        title="Объединенные кумулятивные доходности WalkForward",
        xaxis_title="Время",
        yaxis_title="Кумулятивная доходность",
        showlegend=True
    )

    combined_fig.show()





import pandas as pd

def get_wf_report(results_list):
    """
    Формирует отчет для Walk-Forward результатов.
    Каждая колонка — стратегия, каждая строка — метрика.
    """
    strategy_columns = {}

    for name, res in results_list.items():
        df_summary = res.summary()
        strategy_columns[name] = df_summary

    report_df = pd.DataFrame(strategy_columns)


    return report_df

# Запуск
wf_report = get_wf_report(cross_val_predict_result_combinatorial_WalkForward)

print("\n🚀 WALK-FORWARD REPORT")
wf_report.T
