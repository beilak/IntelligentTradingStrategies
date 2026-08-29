import type { Locale } from "./types";

export interface PnlMetricHelp {
    title: string;
    meaning: string;
    calculation: string;
    interpretation: string;
    caveat?: string;
}

type HelpCopy = [string, string, string, string?];

function entry(title: string, copy: HelpCopy): PnlMetricHelp {
    return {
        title,
        meaning: copy[0],
        calculation: copy[1],
        interpretation: copy[2],
        ...(copy[3] ? { caveat: copy[3] } : {}),
    };
}

export function backtestPnlHelp(locale: Locale) {
    const ru = locale === "ru";
    const pick = (title: string, russian: HelpCopy, english: HelpCopy) =>
        entry(title, ru ? russian : english);

    return {
        periodFrom: pick(
            ru ? "Начало периода" : "Period start",
            [
                "Первый календарный день, включенный в PnL-отчет.",
                "Начальный NAV берется на последнем наблюдении перед этой датой; заявки выбранного дня относятся уже к отчетному периоду.",
                "Позволяет анализировать любой подпериод готового backtest без повторного запуска модели.",
            ],
            [
                "The first calendar day included in the PnL report.",
                "Opening NAV is the last observation before this date; orders on the selected day belong to the report period.",
                "Use it to analyze any sub-period of a completed backtest without rerunning the model.",
            ],
        ),
        periodTo: pick(
            ru ? "Конец периода" : "Period end",
            [
                "Последний календарный день, включенный в отчет.",
                "Конечный NAV — последняя точка equity curve не позднее выбранной даты.",
                "Выходной день допустим: будет использовано последнее доступное торговое наблюдение.",
            ],
            [
                "The last calendar day included in the report.",
                "Ending NAV is the last equity-curve point no later than this date.",
                "A non-trading day is valid; the latest available observation is used.",
            ],
        ),
        model: pick(
            ru ? "Модель и стратегия" : "Model and strategy",
            [
                "Идентифицирует модель или TradingStrategy, породившую симуляцию.",
                "Берется из metadata сохраненного результата backtest.",
                "Все показатели ниже относятся именно к этому запуску и его настройкам.",
            ],
            [
                "Identifies the model or TradingStrategy that produced the simulation.",
                "Read from the saved backtest metadata.",
                "Every metric below belongs to this run and its settings.",
            ],
        ),
        reportPeriod: pick(
            ru ? "Период отчета" : "Report period",
            [
                "Интервал, по которому пересчитаны PnL, доходность и риск.",
                "Календарные дни считаются включительно; наблюдения — точки equity curve внутри периода.",
                "Число наблюдений обычно меньше числа календарных дней из-за выходных.",
            ],
            [
                "The interval used to recalculate PnL, returns, and risk.",
                "Calendar days are inclusive; observations are equity-curve points in the period.",
                "Observation count is normally lower than calendar days because of non-trading days.",
            ],
        ),
        engine: pick(
            ru ? "Движок расчета" : "Calculation engine",
            [
                "Показывает источник симулированных заявок и портфельной стоимости.",
                "ITS использует VectorBT Portfolio.from_orders и ежедневную mark-to-market переоценку.",
                "Это результат симуляции, а не данные реального брокерского счета.",
            ],
            [
                "Shows the source of simulated orders and portfolio values.",
                "ITS uses VectorBT Portfolio.from_orders with daily mark-to-market valuation.",
                "This is a simulation result, not a live brokerage account statement.",
            ],
        ),
        generatedAt: pick(
            ru ? "Время формирования" : "Generated at",
            [
                "Момент, когда отчет был рассчитан в браузере из результата backtest.",
                "Используется текущее локальное время; исходный backtest при этом не меняется.",
                "Помогает отличить время отчета от времени запуска симуляции.",
            ],
            [
                "The moment this report was calculated in the browser from the backtest result.",
                "Current local time is used; the source backtest is unchanged.",
                "It distinguishes report generation time from simulation run time.",
            ],
        ),
        totalPnl: pick(
            "PnL",
            [
                "Денежное изменение стоимости симулированного портфеля за выбранный период.",
                "PnL = NAV конца − NAV начала. Внешних вводов и выводов в backtest нет.",
                "Положительное значение — стратегия заработала, отрицательное — потеряла.",
            ],
            [
                "The money change in simulated portfolio value over the selected period.",
                "PnL = ending NAV − opening NAV. A backtest has no external cash flows.",
                "Positive means the strategy earned money; negative means it lost money.",
            ],
        ),
        twr: pick(
            "TWR — Time-Weighted Return",
            [
                "Доходность управления, не зависящая от размера внешних денежных потоков.",
                "Дневная rₜ = NAVₜ / NAVₜ₋₁ − 1; TWR = ∏(1 + rₜ) − 1.",
                "В backtest без вводов и выводов это обычная совокупная доходность выбранного периода.",
            ],
            [
                "Management return independent of the size of external cash flows.",
                "Daily rₜ = NAVₜ / NAVₜ₋₁ − 1; TWR = ∏(1 + rₜ) − 1.",
                "With no contributions or withdrawals, this is the ordinary cumulative backtest return.",
            ],
        ),
        mwr: pick(
            "MWR / XIRR",
            [
                "Годовая доходность капитала с учетом дат и размеров внешних потоков.",
                "Для backtest есть только начальный отток NAV и конечный приток NAV: MWR = (NAV конца / NAV начала)^(365 / дней) − 1.",
                "Здесь MWR совпадает с annualized TWR, потому что промежуточных пополнений и выводов нет.",
                "Не интерпретируйте разницу TWR и MWR как эффект тайминга: в этой симуляции такого эффекта нет.",
            ],
            [
                "Annual capital return accounting for the dates and sizes of external cash flows.",
                "A backtest has only opening NAV outflow and ending NAV inflow: MWR = (ending NAV / opening NAV)^(365 / days) − 1.",
                "MWR equals annualized TWR here because there are no intermediate contributions or withdrawals.",
                "Do not interpret TWR versus MWR as a cash-flow timing effect in this simulation.",
            ],
        ),
        nav: pick(
            "NAV — Net Asset Value",
            [
                "Полная стоимость симулированного портфеля.",
                "NAV = свободные деньги + Σ(количество бумаги × текущая цена) после комиссий и проскальзывания.",
                "Пара значений показывает базу в начале и итоговый капитал в конце периода.",
            ],
            [
                "The total value of the simulated portfolio.",
                "NAV = cash + Σ(position quantity × current price), after fees and slippage.",
                "The pair shows the opening base and ending capital for the period.",
            ],
        ),
        maxDrawdown: pick(
            ru ? "Максимальная просадка" : "Maximum drawdown",
            [
                "Самое глубокое падение NAV от предыдущего максимума внутри периода.",
                "DDₜ = NAVₜ / max(NAV начала…NAVₜ) − 1; Max Drawdown = min(DDₜ).",
                "−20% означает падение на 20% от прошлого пика в худший момент.",
            ],
            [
                "The deepest decline in NAV from a prior high within the period.",
                "DDₜ = NAVₜ / max(opening NAV…NAVₜ) − 1; Maximum Drawdown = min(DDₜ).",
                "−20% means the portfolio fell 20% from its prior peak at the worst point.",
            ],
        ),
        sharpeSortino: pick(
            "Sharpe / Sortino",
            [
                "Доходность на единицу риска: Sharpe учитывает все колебания, Sortino — только отрицательные.",
                "Sharpe = mean(r) / std(r) × √252. Sortino = mean(r) / downside deviation × √252. Безрисковая ставка 0%.",
                "Чем выше, тем больше доходности приходилось на единицу наблюдавшегося риска.",
            ],
            [
                "Return per unit of risk: Sharpe uses all variation, while Sortino uses downside variation only.",
                "Sharpe = mean(r) / std(r) × √252. Sortino = mean(r) / downside deviation × √252. Risk-free rate is 0%.",
                "Higher values mean more return per unit of observed risk.",
            ],
        ),
        volatility: pick(
            ru ? "Годовая волатильность" : "Annualized volatility",
            [
                "Оценка разброса дневной доходности, приведенная к году.",
                "Volatility = выборочное стандартное отклонение дневных доходностей × √252.",
                "Большая величина означает менее стабильную траекторию, но не обязательно убыток.",
            ],
            [
                "Dispersion of daily returns expressed on an annual basis.",
                "Volatility = sample standard deviation of daily returns × √252.",
                "A larger value means a less stable path, but not necessarily a loss.",
            ],
        ),
        profitWin: pick(
            ru ? "Profit factor / Win rate" : "Profit factor / Win rate",
            [
                "Соотношение прибыльных и убыточных дней и доля положительных дней.",
                "Profit factor = Σ положительного daily PnL / |Σ отрицательного daily PnL|. Win rate = positive days / (positive + negative days).",
                "Показатели описывают дневную кривую NAV, а не отдельные закрытые сделки.",
            ],
            [
                "The balance of profitable versus losing days and the share of positive days.",
                "Profit factor = Σ positive daily PnL / |Σ negative daily PnL|. Win rate = positive days / (positive + negative days).",
                "These metrics describe daily NAV, not individual closed trades.",
            ],
        ),
        performanceChart: pick(
            ru ? "Графики результата" : "Performance charts",
            [
                "Совмещает NAV, накопленный и дневной PnL, а также просадку.",
                "Все ряды строятся из equity curve выбранного подпериода относительно начального NAV.",
                "Помогает увидеть, когда именно сформировалась прибыль и какой риск переживал портфель.",
            ],
            [
                "Combines NAV, cumulative and daily PnL, and drawdown.",
                "All series are built from the selected equity-curve sub-period relative to opening NAV.",
                "It shows when profit emerged and what drawdown the portfolio experienced.",
            ],
        ),
        decomposition: pick(
            ru ? "Декомпозиция PnL" : "PnL decomposition",
            [
                "Разбивает результат на торговую часть и моделируемые издержки.",
                "Gross trading = итоговый PnL − комиссии-компонент − slippage-компонент; комиссии и slippage показаны отрицательными.",
                "Сумма столбцов всегда равна итоговому PnL до оценочного налога.",
            ],
            [
                "Splits the result into trading performance and simulated costs.",
                "Gross trading = total PnL − fee component − slippage component; fees and slippage are negative.",
                "The bars always sum to total PnL before estimated tax.",
            ],
        ),
        realized: pick(
            ru ? "Realized PnL" : "Realized PnL",
            [
                "Результат сделок VectorBT, закрытых внутри выбранного периода.",
                "Сумма PnL записей trades со status=closed и датой выхода внутри периода.",
                "Учитывает торговые издержки, назначенные VectorBT закрытым сделкам.",
            ],
            [
                "Result of VectorBT trades closed inside the selected period.",
                "Sum of trade PnL records with status=closed and exit date within the period.",
                "Includes trading costs assigned by VectorBT to those closed trades.",
            ],
        ),
        unrealized: pick(
            ru ? "Открытый и residual PnL" : "Open and residual PnL",
            [
                "Остаток результата, не вошедший в realized PnL закрытых сделок периода.",
                "Residual = итоговый PnL − realized PnL.",
                "Включает переоценку открытых позиций и часть результата сделок, пересекающих границы подпериода.",
                "Это аналитическая оценка, а не бухгалтерский unrealized PnL по налоговым лотам.",
            ],
            [
                "The result not included in realized PnL of trades closed during the period.",
                "Residual = total PnL − realized PnL.",
                "It includes open-position mark-to-market and trades crossing sub-period boundaries.",
                "This is an analytical estimate, not tax-lot unrealized PnL.",
            ],
        ),
        fees: pick(
            ru ? "Комиссии" : "Fees",
            [
                "Комиссии, списанные движком при исполнении заявок.",
                "−Σ order.fees для заявок выбранного периода.",
                "Показываются отрицательным компонентом PnL.",
            ],
            [
                "Fees charged by the simulation engine on order execution.",
                "−Σ order.fees for orders in the selected period.",
                "Shown as a negative PnL component.",
            ],
        ),
        slippage: pick(
            ru ? "Проскальзывание" : "Slippage",
            [
                "Стоимость ухудшения цены исполнения относительно reference price.",
                "Для покупки: qty × (execution − reference); для продажи: qty × (reference − execution), со знаком минус в отчете.",
                "Равно нулю, если backtest запущен без slippage.",
            ],
            [
                "Cost of execution-price deterioration relative to the reference price.",
                "Buy: qty × (execution − reference); sell: qty × (reference − execution), shown as negative.",
                "It is zero when the backtest runs without slippage.",
            ],
        ),
        estimatedTax: pick(
            ru ? "Оценочный налог" : "Estimated tax",
            [
                "Упрощенная оценка налога на положительный результат периода.",
                "Estimated tax = max(PnL, 0) × tax_rate из настроек backtest.",
                "Используется только для сценария after-tax и не меняет NAV симуляции.",
                "Не учитывает перенос убытков, льготы, налоговые лоты и фактические удержания.",
            ],
            [
                "A simplified tax estimate on a positive period result.",
                "Estimated tax = max(PnL, 0) × the backtest tax_rate setting.",
                "Used only for the after-tax scenario and does not change simulated NAV.",
                "It ignores loss carryforwards, exemptions, tax lots, and actual withholding.",
            ],
        ),
        afterTax: pick(
            ru ? "PnL после оценочного налога" : "PnL after estimated tax",
            [
                "Сценарный результат после упрощенной налоговой оценки.",
                "After-tax PnL = итоговый PnL − estimated tax.",
                "Подходит для грубой оценки, но не заменяет налоговый расчет.",
            ],
            [
                "Scenario result after the simplified tax estimate.",
                "After-tax PnL = total PnL − estimated tax.",
                "Useful for a rough scenario, but not a tax calculation.",
            ],
        ),
        orders: pick(
            ru ? "Заявки" : "Orders",
            [
                "Количество исполненных order records в выбранном периоде.",
                "Считаются записи VectorBT orders, а не число ребалансировок.",
                "Одна ребалансировка может породить много заявок по разным бумагам.",
            ],
            [
                "Number of executed order records in the selected period.",
                "Counts VectorBT order records, not rebalance events.",
                "One rebalance may generate many orders across instruments.",
            ],
        ),
        buysSells: pick(
            ru ? "Покупки / продажи" : "Buys / sells",
            [
                "Количество заявок отдельно по стороне операции.",
                "BUY и SELL считаются по полю side записей VectorBT orders.",
                "Показывает направленность торговой активности.",
            ],
            [
                "Order count split by side.",
                "BUY and SELL are counted from the side field in VectorBT order records.",
                "Shows the direction of trading activity.",
            ],
        ),
        turnover: pick(
            ru ? "Оборот" : "Turnover",
            [
                "Суммарный денежный объем исполненных покупок и продаж.",
                "Turnover = Σ |quantity × execution price|.",
                "Большой оборот обычно усиливает влияние комиссий и slippage.",
            ],
            [
                "Total notional value of executed buys and sells.",
                "Turnover = Σ |quantity × execution price|.",
                "High turnover usually increases the effect of fees and slippage.",
            ],
        ),
        turnoverRatio: pick(
            "Turnover ratio",
            [
                "Оборот относительно среднего капитала периода.",
                "Turnover ratio = turnover / ((NAV начала + NAV конца) / 2).",
                "100% означает, что объем торгов примерно равен среднему размеру портфеля.",
            ],
            [
                "Turnover relative to average period capital.",
                "Turnover ratio = turnover / ((opening NAV + ending NAV) / 2).",
                "100% means traded notional is approximately equal to average portfolio size.",
            ],
        ),
        bestDay: pick(
            ru ? "Лучший день" : "Best day",
            [
                "Максимальный дневной денежный результат периода.",
                "max(NAVₜ − NAVₜ₋₁).",
                "Показывает самый сильный положительный вклад одного наблюдения.",
            ],
            [
                "Largest daily money result in the period.",
                "max(NAVₜ − NAVₜ₋₁).",
                "Shows the strongest positive contribution from one observation.",
            ],
        ),
        worstDay: pick(
            ru ? "Худший день" : "Worst day",
            [
                "Минимальный дневной денежный результат периода.",
                "min(NAVₜ − NAVₜ₋₁).",
                "Показывает самый тяжелый дневной убыток.",
            ],
            [
                "Smallest daily money result in the period.",
                "min(NAVₜ − NAVₜ₋₁).",
                "Shows the worst daily loss.",
            ],
        ),
        historicalVar: pick(
            "Historical VaR 95%",
            [
                "Исторический порог неблагоприятного дневного результата при уровне 95%.",
                "5-й процентиль дневных доходностей × конечный NAV.",
                "Примерно 5% наблюдавшихся дней были хуже этого значения.",
                "Это ретроспективная оценка на данных backtest, не прогноз максимального убытка.",
            ],
            [
                "Historical threshold for an adverse daily result at 95% confidence.",
                "5th percentile of daily returns × ending NAV.",
                "Approximately 5% of observed days were worse than this value.",
                "This is a retrospective backtest estimate, not a forecast of maximum loss.",
            ],
        ),
        calmar: pick(
            "Calmar ratio",
            [
                "Годовая доходность относительно максимальной просадки.",
                "Calmar = annualized return / |Maximum Drawdown|.",
                "Чем выше, тем больше годовой доходности приходилось на единицу просадки.",
            ],
            [
                "Annualized return relative to maximum drawdown.",
                "Calmar = annualized return / |Maximum Drawdown|.",
                "Higher means more annual return per unit of drawdown.",
            ],
        ),
        attribution: pick(
            ru ? "Атрибуция по инструментам" : "Instrument attribution",
            [
                "Раскладывает денежный PnL по бумагам.",
                "Дневной вклад = изменение стоимости позиции + денежный поток заявок по бумаге; вклад периода — сумма дневных вкладов.",
                "Сумма вкладов инструментов сверяется с общим PnL портфеля.",
            ],
            [
                "Decomposes money PnL by instrument.",
                "Daily contribution = change in position value + instrument order cash flow; period contribution is their sum.",
                "Instrument contributions reconcile to total portfolio PnL.",
            ],
        ),
        ticker: pick(
            "Ticker",
            ["Биржевой код инструмента.", "Берется из колонки портфеля и order records VectorBT.", "Идентифицирует строку атрибуции."],
            ["The instrument exchange code.", "Read from VectorBT portfolio columns and order records.", "Identifies an attribution row."],
        ),
        openingQuantity: pick(
            ru ? "Количество на начало" : "Opening quantity",
            ["Позиция непосредственно перед первым днем периода.", "Σ покупок − Σ продаж до даты начала.", "Это дробные единицы симуляции, а не реальные брокерские лоты."],
            ["Position immediately before the first period day.", "Σ buys − Σ sells before the start date.", "These are simulated fractional units, not real broker lots."],
        ),
        endingQuantity: pick(
            ru ? "Количество на конец" : "Ending quantity",
            ["Позиция после заявок последнего дня периода.", "Σ покупок − Σ продаж до даты окончания включительно.", "Показывает, что осталось открытым к концу периода."],
            ["Position after orders on the final period day.", "Σ buys − Σ sells through the end date, inclusive.", "Shows what remained open at period end."],
        ),
        openingValue: pick(
            ru ? "Стоимость на начало" : "Opening value",
            ["Рыночная стоимость позиции перед периодом.", "Восстанавливается из накопленных дневных вкладов и денежных потоков заявок.", "Входит в начальный NAV."],
            ["Position market value before the period.", "Reconstructed from cumulative daily contributions and order cash flows.", "Included in opening NAV."],
        ),
        endingValue: pick(
            ru ? "Стоимость на конец" : "Ending value",
            ["Рыночная стоимость позиции на последнем наблюдении периода.", "Восстанавливается из ежедневной mark-to-market стоимости VectorBT.", "Входит в конечный NAV."],
            ["Position market value at the last period observation.", "Reconstructed from daily VectorBT mark-to-market values.", "Included in ending NAV."],
        ),
        pnlContribution: pick(
            ru ? "Вклад в PnL" : "PnL contribution",
            ["Денежная часть общего результата, связанная с инструментом.", "Σ(изменение position value + cash flow orders) внутри периода.", "Положительное значение увеличило PnL, отрицательное — уменьшило."],
            ["The part of total money result attributable to an instrument.", "Σ(change in position value + order cash flow) inside the period.", "Positive increased PnL; negative reduced it."],
        ),
        instrumentRealized: pick(
            ru ? "Realized инструмента" : "Instrument realized PnL",
            ["PnL закрытых сделок данного тикера.", "Σ trade.pnl для closed trades с выходом внутри периода.", "Не включает переоценку открытой позиции."],
            ["PnL of closed trades for this ticker.", "Σ trade.pnl for closed trades exiting within the period.", "Excludes mark-to-market of an open position."],
        ),
        instrumentTurnover: pick(
            ru ? "Оборот инструмента" : "Instrument turnover",
            ["Денежный объем заявок по одной бумаге.", "Σ |quantity × execution price| по тикеру.", "Показывает концентрацию торговой активности."],
            ["Order notional for one instrument.", "Σ |quantity × execution price| by ticker.", "Shows where trading activity was concentrated."],
        ),
        instrumentOrders: pick(
            ru ? "Заявки инструмента" : "Instrument orders",
            ["Число исполненных order records по тикеру.", "Количество записей VectorBT orders внутри периода.", "Не равно числу ребалансировок."],
            ["Number of executed order records for the ticker.", "Count of VectorBT order records inside the period.", "It is not the rebalance count."],
        ),
        monthlyPerformance: pick(
            ru ? "Доходность по месяцам" : "Monthly performance",
            ["Группирует результат по календарным месяцам.", "Месячная доходность геометрически связывает дневные returns; PnL суммирует дневной денежный результат.", "Показывает стабильность и сезонность стратегии."],
            ["Groups results by calendar month.", "Monthly return geometrically links daily returns; PnL sums daily money results.", "Shows strategy consistency and seasonality."],
        ),
        month: pick(
            ru ? "Месяц" : "Month",
            ["Календарный месяц YYYY-MM.", "Определяется по датам equity curve.", "Первый и последний месяцы могут быть неполными."],
            ["Calendar month in YYYY-MM format.", "Derived from equity-curve dates.", "The first and final months may be partial."],
        ),
        monthReturn: pick(
            ru ? "Месячная доходность" : "Monthly return",
            ["Совокупная доходность наблюдений месяца.", "∏(1 + daily return) − 1.", "Сопоставима между месяцами разного размера портфеля."],
            ["Cumulative return of the month observations.", "∏(1 + daily return) − 1.", "Comparable across months with different portfolio sizes."],
        ),
        monthPnl: pick(
            ru ? "Месячный PnL" : "Monthly PnL",
            ["Денежный результат за месяц.", "Σ daily PnL за календарный месяц.", "Зависит от размера капитала, поэтому смотрите вместе с return."],
            ["Money result for the month.", "Σ daily PnL in the calendar month.", "Depends on capital size, so read it together with return."],
        ),
        monthEndingNav: pick(
            ru ? "NAV на конец месяца" : "Month-end NAV",
            ["Стоимость портфеля на последнем наблюдении месяца.", "Последний NAV соответствующей месячной группы.", "Показывает базу капитала перед следующим месяцем."],
            ["Portfolio value at the last observation of the month.", "The final NAV in that monthly group.", "Shows the capital base entering the next month."],
        ),
        methodology: pick(
            ru ? "Методика" : "Methodology",
            ["Описывает происхождение и границы надежности отчета.", "VectorBT order replay + daily mark-to-market; подпериод считается из сохраненных equity, order, trade и asset-PnL данных.", "Свежий backtest дает точную атрибуцию в рамках допущений симуляции.", "Результат зависит от качества исходных цен, модели комиссий, slippage и отсутствия look-ahead bias; это не брокерский и не налоговый отчет."],
            ["Describes the report source and reliability boundaries.", "VectorBT order replay + daily mark-to-market; a sub-period uses saved equity, order, trade, and asset-PnL data.", "A newly generated backtest provides exact attribution within simulation assumptions.", "Results depend on price quality, cost models, and absence of look-ahead bias; this is not a brokerage or tax statement."],
        ),
    };
}

export type BacktestPnlHelp = ReturnType<typeof backtestPnlHelp>;
