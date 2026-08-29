import type {
    BacktestPnlAttributionRow,
    BacktestPnlReport,
    BacktestResult,
    Locale,
} from "./types";

const TRADING_DAYS_PER_YEAR = 252;

export function buildBacktestPnlReport(
    result: BacktestResult,
    from: string,
    to: string,
    locale: Locale,
): BacktestPnlReport {
    if (!from || !to || from > to) {
        throw new Error(
            locale === "ru"
                ? "Проверьте даты периода отчета."
                : "Check the report period dates.",
        );
    }

    const allPoints = [...result.equity_curve.points]
        .filter((point) => Number.isFinite(point.value))
        .sort((left, right) => left.time.localeCompare(right.time));
    const firstIndex = allPoints.findIndex((point) => dateOnly(point.time) >= from);
    const selected = allPoints.filter((point) => {
        const date = dateOnly(point.time);
        return date >= from && date <= to;
    });
    if (!selected.length || firstIndex < 0) {
        throw new Error(
            locale === "ru"
                ? "В выбранном периоде нет наблюдений backtest."
                : "The selected period has no backtest observations.",
        );
    }

    const openingNav =
        firstIndex > 0
            ? allPoints[firstIndex - 1].value
            : (result.pnl_source?.initial_nav ??
              result.metadata.settings.init_cash);
    const endingNav = selected[selected.length - 1].value;
    const totalPnl = endingNav - openingNav;
    const equityCurve = buildEquityCurve(selected, openingNav);
    const returns = equityCurve.map((point) => point.daily_return);
    const dailyPnl = equityCurve.map((point) => point.daily_pnl);
    const twr = openingNav !== 0 ? endingNav / openingNav - 1 : 0;
    const elapsedDays = Math.max(0, daysBetween(from, to));
    const annualizedReturn = annualizeReturn(openingNav, endingNav, elapsedDays);
    const source = result.pnl_source;
    const detailedOrders = source?.orders.filter((order) =>
        isInside(order.time, from, to),
    );
    const fees = detailedOrders
        ? -sum(detailedOrders.map((order) => order.fees))
        : -Math.abs(numericStat(result, "Total Fees Paid") ?? 0);
    const slippage = detailedOrders
        ? -sum(detailedOrders.map((order) => order.slippage_cost))
        : 0;
    const turnover = detailedOrders
        ? sum(detailedOrders.map((order) => order.size * order.price))
        : 0;
    const orderCount = detailedOrders
        ? detailedOrders.length
        : Math.round(numericStat(result, "Total Trades") ?? 0);
    const buys = detailedOrders?.filter((order) => order.side === "buy").length ?? 0;
    const sells = detailedOrders?.filter((order) => order.side === "sell").length ?? 0;
    const realizedPnl = source
        ? sum(
              source.trades
                  .filter(
                      (trade) =>
                          trade.status === "closed" &&
                          isInside(trade.exit_time, from, to),
                  )
                  .map((trade) => trade.pnl ?? 0),
          )
        : 0;
    const taxRate = normalizeTaxRate(result.metadata.settings.tax_rate);
    const estimatedTax = Math.max(0, totalPnl) * taxRate;
    const maxDrawdown = Math.min(
        0,
        ...equityCurve.map((point) => point.drawdown),
    );
    const annualizedVolatility = sampleStandardDeviation(returns) * Math.sqrt(TRADING_DAYS_PER_YEAR);
    const sharpeRatio = ratio(
        mean(returns) * Math.sqrt(TRADING_DAYS_PER_YEAR),
        sampleStandardDeviation(returns),
    );
    const downsideDeviation = Math.sqrt(
        mean(returns.map((value) => Math.min(0, value) ** 2)),
    );
    const sortinoRatio = ratio(
        mean(returns) * Math.sqrt(TRADING_DAYS_PER_YEAR),
        downsideDeviation,
    );
    const positiveDays = dailyPnl.filter((value) => value > 0).length;
    const negativeDays = dailyPnl.filter((value) => value < 0).length;
    const profitFactor = ratio(
        sum(dailyPnl.filter((value) => value > 0)),
        Math.abs(sum(dailyPnl.filter((value) => value < 0))),
    );
    const historicalVarReturn = returns.length ? quantile(returns, 0.05) : null;
    const attribution = source
        ? buildAttribution(result, from, to)
        : [];
    const hasDetailedSource = Boolean(source);
    const language = reportLanguage(locale);

    return {
        generated_at: new Date().toISOString(),
        model_name: result.metadata.model_name,
        strategy_name: result.metadata.strategy_name,
        test_name: result.metadata.test_name,
        period: {
            from,
            to,
            calendar_days: elapsedDays + 1,
            observations: selected.length,
        },
        currency: source?.currency ?? "RUB",
        summary: {
            opening_nav: openingNav,
            ending_nav: endingNav,
            total_pnl: totalPnl,
            twr,
            mwr: annualizedReturn,
            annualized_return: annualizedReturn,
            realized_pnl: realizedPnl,
            unrealized_pnl_estimate: totalPnl - realizedPnl,
            fees,
            slippage,
            estimated_tax: estimatedTax,
            after_tax_pnl_estimate: totalPnl - estimatedTax,
            turnover,
            turnover_ratio: ratio(turnover, (openingNav + endingNav) / 2),
            orders: orderCount,
            buys,
            sells,
        },
        risk: {
            annualized_volatility: annualizedVolatility,
            sharpe_ratio: sharpeRatio,
            sortino_ratio: sortinoRatio,
            max_drawdown: maxDrawdown,
            calmar_ratio: ratio(annualizedReturn, Math.abs(maxDrawdown)),
            profit_factor: profitFactor,
            positive_days: positiveDays,
            negative_days: negativeDays,
            win_rate:
                positiveDays + negativeDays > 0
                    ? positiveDays / (positiveDays + negativeDays)
                    : null,
            best_day_pnl: dailyPnl.length ? Math.max(...dailyPnl) : 0,
            worst_day_pnl: dailyPnl.length ? Math.min(...dailyPnl) : 0,
            average_day_pnl: mean(dailyPnl),
            historical_var_95_return: historicalVarReturn,
            historical_var_95_amount:
                historicalVarReturn === null
                    ? null
                    : historicalVarReturn * endingNav,
        },
        components: [
            {
                key: "gross_trading",
                label: language.grossTrading,
                value: totalPnl - fees - slippage,
            },
            { key: "fees", label: language.fees, value: fees },
            { key: "slippage", label: language.slippage, value: slippage },
        ],
        equity_curve: equityCurve,
        monthly_returns: buildMonthlyReturns(equityCurve),
        attribution,
        methodology: {
            method:
                source?.method ??
                "equity curve fallback (legacy cached backtest)",
            engine: "vectorbt",
            has_detailed_source: hasDetailedSource,
            external_flows: false,
            taxes_applied: false,
            warnings: [
                language.noExternalFlows,
                language.taxEstimate,
                language.noIncomeSeparation,
                ...(!hasDetailedSource ? [language.legacySource] : []),
            ],
        },
    };
}

function buildEquityCurve(
    points: BacktestResult["equity_curve"]["points"],
    openingNav: number,
) {
    let previousNav = openingNav;
    let highWaterMark = openingNav;
    return points.map((point) => {
        const dailyPnl = point.value - previousNav;
        const dailyReturn = previousNav !== 0 ? point.value / previousNav - 1 : 0;
        highWaterMark = Math.max(highWaterMark, point.value);
        const result = {
            date: dateOnly(point.time),
            nav: point.value,
            daily_pnl: dailyPnl,
            cumulative_pnl: point.value - openingNav,
            daily_return: dailyReturn,
            cumulative_return:
                openingNav !== 0 ? point.value / openingNav - 1 : 0,
            drawdown:
                highWaterMark !== 0 ? point.value / highWaterMark - 1 : 0,
        };
        previousNav = point.value;
        return result;
    });
}

function buildMonthlyReturns(
    equityCurve: BacktestPnlReport["equity_curve"],
): BacktestPnlReport["monthly_returns"] {
    const rows = new Map<string, BacktestPnlReport["equity_curve"]>();
    equityCurve.forEach((point) => {
        const month = point.date.slice(0, 7);
        rows.set(month, [...(rows.get(month) ?? []), point]);
    });
    return [...rows.entries()].map(([month, points]) => ({
        month,
        return: points.reduce(
            (value, point) => value * (1 + point.daily_return),
            1,
        ) - 1,
        pnl: sum(points.map((point) => point.daily_pnl)),
        ending_nav: points[points.length - 1].nav,
    }));
}

function buildAttribution(
    result: BacktestResult,
    from: string,
    to: string,
): BacktestPnlAttributionRow[] {
    const source = result.pnl_source;
    if (!source) return [];
    const tickers = new Set<string>();
    source.daily_asset_pnl.forEach((day) =>
        Object.keys(day.contributions).forEach((ticker) => tickers.add(ticker)),
    );
    source.orders.forEach((order) => tickers.add(order.ticker));
    const assetNames = new Map(
        result.metadata.assets.map((asset) => [asset.ticker, asset.name]),
    );

    return [...tickers]
        .map((ticker) => {
            const contributions = source.daily_asset_pnl.flatMap((day) => {
                const value = day.contributions[ticker];
                return value === undefined
                    ? []
                    : [{ date: dateOnly(day.time), value }];
            });
            const orders = source.orders.filter((order) => order.ticker === ticker);
            const contributionBefore = sum(
                contributions
                    .filter((item) => item.date < from)
                    .map((item) => item.value),
            );
            const contributionThrough = sum(
                contributions
                    .filter((item) => item.date <= to)
                    .map((item) => item.value),
            );
            const cashFlowBefore = sum(
                orders
                    .filter((order) => dateOnly(order.time) < from)
                    .map(orderCashFlow),
            );
            const cashFlowThrough = sum(
                orders
                    .filter((order) => dateOnly(order.time) <= to)
                    .map(orderCashFlow),
            );
            const periodOrders = orders.filter((order) =>
                isInside(order.time, from, to),
            );
            const periodContribution = sum(
                contributions
                    .filter((item) => item.date >= from && item.date <= to)
                    .map((item) => item.value),
            );
            const realizedPnl = sum(
                source.trades
                    .filter(
                        (trade) =>
                            trade.ticker === ticker &&
                            trade.status === "closed" &&
                            isInside(trade.exit_time, from, to),
                    )
                    .map((trade) => trade.pnl ?? 0),
            );
            return {
                ticker,
                name: assetNames.get(ticker) ?? ticker,
                opening_quantity: sum(
                    orders
                        .filter((order) => dateOnly(order.time) < from)
                        .map(signedOrderSize),
                ),
                ending_quantity: sum(
                    orders
                        .filter((order) => dateOnly(order.time) <= to)
                        .map(signedOrderSize),
                ),
                opening_value: contributionBefore - cashFlowBefore,
                ending_value: contributionThrough - cashFlowThrough,
                pnl_contribution: periodContribution,
                contribution_pct: null,
                realized_pnl: realizedPnl,
                turnover: sum(
                    periodOrders.map((order) => order.size * order.price),
                ),
                orders: periodOrders.length,
            };
        })
        .filter(
            (row) =>
                Math.abs(row.opening_value) > 1e-8 ||
                Math.abs(row.ending_value) > 1e-8 ||
                Math.abs(row.pnl_contribution) > 1e-8 ||
                row.orders > 0,
        )
        .map((row, _index, rows) => {
            const total = sum(rows.map((item) => item.pnl_contribution));
            return {
                ...row,
                contribution_pct:
                    Math.abs(total) > 1e-12
                        ? row.pnl_contribution / total
                        : null,
            };
        })
        .sort(
            (left, right) =>
                Math.abs(right.pnl_contribution) -
                Math.abs(left.pnl_contribution),
        );
}

function orderCashFlow(
    order: NonNullable<BacktestResult["pnl_source"]>["orders"][number],
) {
    const gross = order.size * order.price;
    return order.side === "buy"
        ? -(gross + order.fees)
        : gross - order.fees;
}

function signedOrderSize(
    order: NonNullable<BacktestResult["pnl_source"]>["orders"][number],
) {
    return order.side === "buy" ? order.size : -order.size;
}

function numericStat(result: BacktestResult, metric: string) {
    return result.report.find((row) => row.metric === metric)?.numeric_value ?? null;
}

function normalizeTaxRate(value: number) {
    if (!Number.isFinite(value) || value <= 0) return 0;
    return value > 1 ? value / 100 : value;
}

function annualizeReturn(opening: number, ending: number, elapsedDays: number) {
    if (opening <= 0 || ending <= 0 || elapsedDays <= 0) return null;
    return (ending / opening) ** (365 / elapsedDays) - 1;
}

function dateOnly(value: string) {
    return value.slice(0, 10);
}

function isInside(value: string, from: string, to: string) {
    const date = dateOnly(value);
    return date >= from && date <= to;
}

function daysBetween(from: string, to: string) {
    return Math.round(
        (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) /
            86_400_000,
    );
}

function sum(values: number[]) {
    return values.reduce((total, value) => total + value, 0);
}

function mean(values: number[]) {
    return values.length ? sum(values) / values.length : 0;
}

function sampleStandardDeviation(values: number[]) {
    if (values.length < 2) return 0;
    const average = mean(values);
    return Math.sqrt(
        sum(values.map((value) => (value - average) ** 2)) /
            (values.length - 1),
    );
}

function ratio(numerator: number | null, denominator: number) {
    if (
        numerator === null ||
        !Number.isFinite(numerator) ||
        !Number.isFinite(denominator) ||
        Math.abs(denominator) < 1e-12
    ) {
        return null;
    }
    return numerator / denominator;
}

function quantile(values: number[], probability: number) {
    if (!values.length) return 0;
    const sorted = [...values].sort((left, right) => left - right);
    const position = (sorted.length - 1) * probability;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    if (lower === upper) return sorted[lower];
    return (
        sorted[lower] +
        (sorted[upper] - sorted[lower]) * (position - lower)
    );
}

function reportLanguage(locale: Locale) {
    return locale === "ru"
        ? {
              grossTrading: "Рынок и торговый результат до издержек",
              fees: "Комиссии симуляции",
              slippage: "Проскальзывание",
              noExternalFlows:
                  "Backtest не содержит внешних вводов и выводов. Поэтому MWR/XIRR совпадает с годовой доходностью TWR и не является отдельной оценкой тайминга денежных потоков.",
              taxEstimate:
                  "Налог показан оценочно и не вычитается из NAV симуляции.",
              noIncomeSeparation:
                  "Дивиденды и купоны не выделяются отдельно: их влияние зависит от исходного ряда цен модели.",
              legacySource:
                  "Это старый сохраненный backtest без детального PnL-источника: атрибуция и заявки недоступны, комиссии показаны для всего теста.",
          }
        : {
              grossTrading: "Market and trading result before costs",
              fees: "Simulation fees",
              slippage: "Slippage",
              noExternalFlows:
                  "The backtest has no external contributions or withdrawals. MWR/XIRR therefore equals annualized TWR and is not a separate cash-flow timing measure.",
              taxEstimate:
                  "Tax is an estimate and is not deducted from the simulated NAV.",
              noIncomeSeparation:
                  "Dividends and coupons are not separated; their effect depends on the model price series.",
              legacySource:
                  "This is a legacy saved backtest without detailed PnL source data: attribution and orders are unavailable, and fees cover the full test.",
          };
}
