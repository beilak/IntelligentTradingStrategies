<script setup lang="ts">
import { FileChartColumn, X } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import { buildBacktestPnlReport } from "../backtestPnl";
import { backtestPnlHelp } from "../backtestPnlHelp";
import type { BacktestPnlReport, BacktestResult, Locale } from "../types";
import BacktestPnlCharts from "./BacktestPnlCharts.vue";
import MetricHelp from "./MetricHelp.vue";

const props = defineProps<{
    result: BacktestResult;
    locale: Locale;
}>();
const emit = defineEmits<{ close: [] }>();

const availableFrom = computed(
    () => props.result.equity_curve.points[0]?.time.slice(0, 10) ?? "",
);
const availableTo = computed(
    () =>
        props.result.equity_curve.points[
            props.result.equity_curve.points.length - 1
        ]?.time.slice(0, 10) ?? "",
);
const fromDate = ref(availableFrom.value);
const toDate = ref(availableTo.value);
const report = ref<BacktestPnlReport | null>(null);
const error = ref("");
const help = computed(() => backtestPnlHelp(props.locale));
const ru = computed(() => props.locale === "ru");

watch(
    () => props.result,
    () => {
        fromDate.value = availableFrom.value;
        toDate.value = availableTo.value;
        generateReport();
    },
);

onMounted(generateReport);

function generateReport() {
    error.value = "";
    try {
        report.value = buildBacktestPnlReport(
            props.result,
            fromDate.value,
            toDate.value,
            props.locale,
        );
    } catch (reason) {
        report.value = null;
        error.value = reason instanceof Error ? reason.message : String(reason);
    }
}

function formatMoney(value: number | null | undefined) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
    const currency = report.value?.currency?.toUpperCase() || "RUB";
    try {
        return new Intl.NumberFormat(ru.value ? "ru-RU" : "en-US", {
            style: "currency",
            currency,
            maximumFractionDigits: 2,
        }).format(value);
    } catch {
        return formatNumber(value, 2);
    }
}

function formatPercent(value: number | null | undefined) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
    return new Intl.NumberFormat(ru.value ? "ru-RU" : "en-US", {
        style: "percent",
        maximumFractionDigits: 2,
    }).format(value);
}

function formatNumber(value: number | null | undefined, digits = 2) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
    return new Intl.NumberFormat(ru.value ? "ru-RU" : "en-US", {
        maximumFractionDigits: digits,
    }).format(value);
}

function formatDate(value: string) {
    if (!value) return "—";
    return new Intl.DateTimeFormat(ru.value ? "ru-RU" : "en-US").format(
        new Date(`${value.slice(0, 10)}T00:00:00`),
    );
}

function formatDateTime(value: string) {
    return new Intl.DateTimeFormat(ru.value ? "ru-RU" : "en-US", {
        dateStyle: "short",
        timeStyle: "medium",
    }).format(new Date(value));
}
</script>

<template>
    <div class="pnl-backdrop" @click.self="emit('close')">
        <section
            class="pnl-modal"
            role="dialog"
            aria-modal="true"
            :aria-label="ru ? 'Отчет PnL Backtesting' : 'Backtesting PnL report'"
        >
            <header class="pnl-modal-head">
                <div>
                    <span>Strategy Lab · VectorBT</span>
                    <strong>{{ ru ? "Отчет PnL Backtesting" : "Backtesting PnL Report" }}</strong>
                </div>
                <button
                    class="pnl-close"
                    type="button"
                    :title="ru ? 'Закрыть' : 'Close'"
                    :aria-label="ru ? 'Закрыть' : 'Close'"
                    @click="emit('close')"
                >
                    <X :size="18" />
                </button>
            </header>

            <div class="pnl-modal-body">
                <section class="pnl-toolbar">
                    <label>
                        <span class="metric-label-with-help">
                            {{ ru ? "Период с" : "Period from" }}
                            <MetricHelp :help="help.periodFrom" :locale="locale" />
                        </span>
                        <input
                            v-model="fromDate"
                            type="date"
                            :min="availableFrom"
                            :max="toDate"
                        />
                    </label>
                    <label>
                        <span class="metric-label-with-help">
                            {{ ru ? "Период по" : "Period to" }}
                            <MetricHelp :help="help.periodTo" :locale="locale" />
                        </span>
                        <input
                            v-model="toDate"
                            type="date"
                            :min="fromDate"
                            :max="availableTo"
                        />
                    </label>
                    <button class="pnl-generate" type="button" @click="generateReport">
                        <FileChartColumn :size="17" />
                        {{ ru ? "Сгенерировать отчет" : "Generate report" }}
                    </button>
                </section>

                <div v-if="error" class="pnl-error">{{ error }}</div>

                <template v-if="report">
                    <section class="pnl-identity">
                        <div>
                            <span class="metric-label-with-help">
                                {{ ru ? "Модель" : "Model" }}
                                <MetricHelp :help="help.model" :locale="locale" />
                            </span>
                            <strong>{{ report.model_name }}</strong>
                            <small>{{ report.strategy_name }}</small>
                        </div>
                        <div>
                            <span class="metric-label-with-help">
                                {{ ru ? "Период" : "Period" }}
                                <MetricHelp :help="help.reportPeriod" :locale="locale" />
                            </span>
                            <strong>{{ formatDate(report.period.from) }} — {{ formatDate(report.period.to) }}</strong>
                            <small>
                                {{ report.period.calendar_days }} {{ ru ? "дней" : "days" }} ·
                                {{ report.period.observations }} {{ ru ? "наблюдений" : "observations" }}
                            </small>
                        </div>
                        <div>
                            <span class="metric-label-with-help">
                                {{ ru ? "Движок" : "Engine" }}
                                <MetricHelp :help="help.engine" :locale="locale" />
                            </span>
                            <strong>{{ report.methodology.engine }}</strong>
                            <small>{{ report.test_name || "baseline" }}</small>
                        </div>
                        <div>
                            <span class="metric-label-with-help">
                                {{ ru ? "Сформирован" : "Generated" }}
                                <MetricHelp :help="help.generatedAt" :locale="locale" />
                            </span>
                            <strong>{{ formatDateTime(report.generated_at) }}</strong>
                            <small>{{ report.methodology.has_detailed_source ? (ru ? "детальная атрибуция" : "detailed attribution") : (ru ? "legacy-режим" : "legacy mode") }}</small>
                        </div>
                    </section>

                    <ul class="pnl-warnings">
                        <li v-for="warning in report.methodology.warnings" :key="warning">
                            {{ warning }}
                        </li>
                    </ul>

                    <section class="pnl-kpi-grid">
                        <article class="pnl-kpi primary">
                            <span class="metric-label-with-help">
                                {{ ru ? "Итоговый PnL" : "Total PnL" }}
                                <MetricHelp :help="help.totalPnl" :locale="locale" />
                            </span>
                            <strong :class="report.summary.total_pnl >= 0 ? 'positive' : 'negative'">
                                {{ formatMoney(report.summary.total_pnl) }}
                            </strong>
                            <small>{{ ru ? "без внешних денежных потоков" : "without external cash flows" }}</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                TWR
                                <MetricHelp :help="help.twr" :locale="locale" />
                            </span>
                            <strong :class="report.summary.twr >= 0 ? 'positive' : 'negative'">
                                {{ formatPercent(report.summary.twr) }}
                            </strong>
                            <small>time-weighted return</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                MWR / XIRR
                                <MetricHelp :help="help.mwr" :locale="locale" />
                            </span>
                            <strong>{{ formatPercent(report.summary.mwr) }}</strong>
                            <small>{{ ru ? "годовых · без промежуточных flows" : "annual · no intermediate flows" }}</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                {{ ru ? "NAV начало → конец" : "Opening → ending NAV" }}
                                <MetricHelp :help="help.nav" :locale="locale" />
                            </span>
                            <strong>{{ formatMoney(report.summary.opening_nav) }}</strong>
                            <small>{{ formatMoney(report.summary.ending_nav) }}</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                Max drawdown
                                <MetricHelp :help="help.maxDrawdown" :locale="locale" />
                            </span>
                            <strong class="negative">{{ formatPercent(report.risk.max_drawdown) }}</strong>
                            <small>{{ ru ? "внутри выбранного периода" : "within selected period" }}</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                Sharpe / Sortino
                                <MetricHelp :help="help.sharpeSortino" :locale="locale" />
                            </span>
                            <strong>{{ formatNumber(report.risk.sharpe_ratio) }} / {{ formatNumber(report.risk.sortino_ratio) }}</strong>
                            <small>{{ ru ? "безрисковая ставка 0%" : "0% risk-free rate" }}</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                {{ ru ? "Волатильность" : "Volatility" }}
                                <MetricHelp :help="help.volatility" :locale="locale" />
                            </span>
                            <strong>{{ formatPercent(report.risk.annualized_volatility) }}</strong>
                            <small>annualized · 252</small>
                        </article>
                        <article class="pnl-kpi">
                            <span class="metric-label-with-help">
                                Profit factor / Win rate
                                <MetricHelp :help="help.profitWin" :locale="locale" />
                            </span>
                            <strong>{{ formatNumber(report.risk.profit_factor) }} / {{ formatPercent(report.risk.win_rate) }}</strong>
                            <small>{{ report.risk.positive_days }}+ / {{ report.risk.negative_days }}− {{ ru ? "дней" : "days" }}</small>
                        </article>
                    </section>

                    <BacktestPnlCharts
                        :report="report"
                        :locale="locale"
                        :help="help"
                    />

                    <section class="pnl-detail-grid">
                        <article class="pnl-detail-card">
                            <header>
                                <span>{{ ru ? "Денежный результат" : "Money result" }}</span>
                                <strong>Costs &amp; result</strong>
                            </header>
                            <dl>
                                <div>
                                    <dt class="metric-label-with-help">Realized PnL <MetricHelp :help="help.realized" :locale="locale" /></dt>
                                    <dd>{{ formatMoney(report.summary.realized_pnl) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Открытый / residual PnL" : "Open / residual PnL" }} <MetricHelp :help="help.unrealized" :locale="locale" /></dt>
                                    <dd>{{ formatMoney(report.summary.unrealized_pnl_estimate) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Комиссии" : "Fees" }} <MetricHelp :help="help.fees" :locale="locale" /></dt>
                                    <dd class="negative">{{ formatMoney(report.summary.fees) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Проскальзывание" : "Slippage" }} <MetricHelp :help="help.slippage" :locale="locale" /></dt>
                                    <dd class="negative">{{ formatMoney(report.summary.slippage) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Оценочный налог" : "Estimated tax" }} <MetricHelp :help="help.estimatedTax" :locale="locale" /></dt>
                                    <dd class="negative">{{ formatMoney(-report.summary.estimated_tax) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "PnL после оценки налога" : "PnL after tax estimate" }} <MetricHelp :help="help.afterTax" :locale="locale" /></dt>
                                    <dd>{{ formatMoney(report.summary.after_tax_pnl_estimate) }}</dd>
                                </div>
                            </dl>
                        </article>

                        <article class="pnl-detail-card">
                            <header>
                                <span>{{ ru ? "Торговая активность" : "Trading activity" }}</span>
                                <strong>Execution statistics</strong>
                            </header>
                            <dl>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Заявок" : "Orders" }} <MetricHelp :help="help.orders" :locale="locale" /></dt>
                                    <dd>{{ report.summary.orders }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Покупок / продаж" : "Buys / sells" }} <MetricHelp :help="help.buysSells" :locale="locale" /></dt>
                                    <dd>{{ report.summary.buys }} / {{ report.summary.sells }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Оборот" : "Turnover" }} <MetricHelp :help="help.turnover" :locale="locale" /></dt>
                                    <dd>{{ formatMoney(report.summary.turnover) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">Turnover ratio <MetricHelp :help="help.turnoverRatio" :locale="locale" /></dt>
                                    <dd>{{ formatPercent(report.summary.turnover_ratio) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Лучший день" : "Best day" }} <MetricHelp :help="help.bestDay" :locale="locale" /></dt>
                                    <dd class="positive">{{ formatMoney(report.risk.best_day_pnl) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">{{ ru ? "Худший день" : "Worst day" }} <MetricHelp :help="help.worstDay" :locale="locale" /></dt>
                                    <dd class="negative">{{ formatMoney(report.risk.worst_day_pnl) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">Historical VaR 95% <MetricHelp :help="help.historicalVar" :locale="locale" /></dt>
                                    <dd>{{ formatMoney(report.risk.historical_var_95_amount) }}</dd>
                                </div>
                                <div>
                                    <dt class="metric-label-with-help">Calmar <MetricHelp :help="help.calmar" :locale="locale" /></dt>
                                    <dd>{{ formatNumber(report.risk.calmar_ratio) }}</dd>
                                </div>
                            </dl>
                        </article>
                    </section>

                    <section class="pnl-table-card">
                        <header>
                            <div>
                                <span class="metric-label-with-help">
                                    Attribution
                                    <MetricHelp :help="help.attribution" :locale="locale" />
                                </span>
                                <strong>{{ ru ? "Вклад инструментов в PnL" : "Instrument PnL contribution" }}</strong>
                            </div>
                            <small>{{ report.attribution.length }} {{ ru ? "инструментов" : "instruments" }}</small>
                        </header>
                        <div class="pnl-table-shell">
                            <table class="pnl-table">
                                <thead>
                                    <tr>
                                        <th><span class="metric-label-with-help">Ticker <MetricHelp :help="help.ticker" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Кол-во начало" : "Opening qty" }} <MetricHelp :help="help.openingQuantity" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Кол-во конец" : "Ending qty" }} <MetricHelp :help="help.endingQuantity" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Стоимость начало" : "Opening value" }} <MetricHelp :help="help.openingValue" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Стоимость конец" : "Ending value" }} <MetricHelp :help="help.endingValue" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Вклад PnL" : "PnL contribution" }} <MetricHelp :help="help.pnlContribution" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">Realized <MetricHelp :help="help.instrumentRealized" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Оборот" : "Turnover" }} <MetricHelp :help="help.instrumentTurnover" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Заявки" : "Orders" }} <MetricHelp :help="help.instrumentOrders" :locale="locale" /></span></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="row in report.attribution" :key="row.ticker">
                                        <td><strong>{{ row.ticker }}</strong><small>{{ row.name }}</small></td>
                                        <td>{{ formatNumber(row.opening_quantity, 4) }}</td>
                                        <td>{{ formatNumber(row.ending_quantity, 4) }}</td>
                                        <td>{{ formatMoney(row.opening_value) }}</td>
                                        <td>{{ formatMoney(row.ending_value) }}</td>
                                        <td :class="row.pnl_contribution >= 0 ? 'positive' : 'negative'">{{ formatMoney(row.pnl_contribution) }}</td>
                                        <td>{{ formatMoney(row.realized_pnl) }}</td>
                                        <td>{{ formatMoney(row.turnover) }}</td>
                                        <td>{{ row.orders }}</td>
                                    </tr>
                                    <tr v-if="!report.attribution.length">
                                        <td colspan="9">{{ ru ? "Нет детальной атрибуции для этого сохраненного backtest" : "No detailed attribution for this saved backtest" }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <section class="pnl-table-card monthly-card">
                        <header>
                            <div>
                                <span class="metric-label-with-help">
                                    Monthly performance
                                    <MetricHelp :help="help.monthlyPerformance" :locale="locale" />
                                </span>
                                <strong>{{ ru ? "Доходность по месяцам" : "Monthly returns" }}</strong>
                            </div>
                        </header>
                        <div class="pnl-table-shell">
                            <table class="pnl-table monthly-table">
                                <thead>
                                    <tr>
                                        <th><span class="metric-label-with-help">{{ ru ? "Месяц" : "Month" }} <MetricHelp :help="help.month" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "Доходность" : "Return" }} <MetricHelp :help="help.monthReturn" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">PnL <MetricHelp :help="help.monthPnl" :locale="locale" /></span></th>
                                        <th><span class="metric-label-with-help">{{ ru ? "NAV на конец" : "Ending NAV" }} <MetricHelp :help="help.monthEndingNav" :locale="locale" /></span></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="row in report.monthly_returns" :key="row.month">
                                        <td>{{ row.month }}</td>
                                        <td :class="row.return >= 0 ? 'positive' : 'negative'">{{ formatPercent(row.return) }}</td>
                                        <td :class="row.pnl >= 0 ? 'positive' : 'negative'">{{ formatMoney(row.pnl) }}</td>
                                        <td>{{ formatMoney(row.ending_nav) }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <footer class="pnl-methodology">
                        <strong class="metric-label-with-help">
                            {{ ru ? "Методика" : "Methodology" }}
                            <MetricHelp :help="help.methodology" :locale="locale" />
                        </strong>
                        <span>{{ report.methodology.method }}.</span>
                        <span>
                            {{ ru
                                ? "Отчет аналитический и не заменяет брокерский или налоговый документ."
                                : "This analytical report does not replace a brokerage or tax statement." }}
                        </span>
                    </footer>
                </template>
            </div>
        </section>
    </div>
</template>

<style scoped>
.pnl-backdrop {
    align-items: center;
    background: rgba(5, 7, 11, 0.86);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: 15px;
    position: fixed;
    z-index: 180;
}

.pnl-modal {
    background: #11141b;
    border: 1px solid #2b3342;
    border-radius: 10px;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
    color: #f4f6fb;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    height: min(960px, calc(100vh - 30px));
    max-width: 1540px;
    overflow: hidden;
    width: min(1540px, calc(100vw - 30px));
}

.pnl-modal-head {
    align-items: center;
    border-bottom: 1px solid #252b36;
    display: flex;
    justify-content: space-between;
    min-height: 64px;
    padding: 12px 14px;
}

.pnl-modal-head > div {
    display: grid;
    gap: 4px;
}

.pnl-modal-head span,
.pnl-toolbar label > span,
.pnl-identity span,
.pnl-kpi > span,
.pnl-detail-card header span,
.pnl-table-card header span {
    color: #8992a3;
    font-size: 12px;
}

.pnl-modal-head strong {
    font-size: 18px;
}

.pnl-close {
    align-items: center;
    background: #151821;
    border: 1px solid #2b3342;
    border-radius: 8px;
    color: #66d9ef;
    cursor: pointer;
    display: inline-flex;
    height: 38px;
    justify-content: center;
    width: 38px;
}

.pnl-modal-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-height: 0;
    overflow: auto;
    padding: 14px;
}

.pnl-toolbar {
    align-items: end;
    background: #0d1017;
    border: 1px solid #2b3342;
    border-radius: 8px;
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(2, minmax(190px, 1fr)) auto;
    padding: 12px;
}

.pnl-toolbar label {
    display: grid;
    gap: 6px;
}

.pnl-toolbar input {
    background: #0b0e14;
    border: 1px solid #2b3342;
    border-radius: 8px;
    color: #f4f6fb;
    min-height: 38px;
    padding: 0 10px;
}

.pnl-generate {
    align-items: center;
    background: #e9edf5;
    border: 1px solid #e9edf5;
    border-radius: 8px;
    color: #11151d;
    cursor: pointer;
    display: inline-flex;
    font-weight: 700;
    gap: 8px;
    justify-content: center;
    min-height: 38px;
    padding: 0 12px;
}

.metric-label-with-help {
    align-items: center;
    display: inline-flex;
    gap: 5px;
    max-width: 100%;
}

.pnl-error,
.pnl-warnings {
    background: rgba(255, 204, 102, 0.08);
    border: 1px solid rgba(255, 204, 102, 0.3);
    border-radius: 8px;
    color: #ffe4a3;
    font-size: 12px;
    line-height: 1.45;
}

.pnl-error {
    padding: 10px 12px;
}

.pnl-warnings {
    display: grid;
    gap: 5px;
    margin: 0;
    padding: 10px 14px 10px 32px;
}

.pnl-identity {
    background: #0d1017;
    border: 1px solid #2b3342;
    border-radius: 8px;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
}

.pnl-identity > div {
    display: grid;
    gap: 5px;
    min-width: 0;
    padding: 12px;
}

.pnl-identity > div + div {
    border-left: 1px solid #252b36;
}

.pnl-identity strong,
.pnl-identity small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.pnl-identity small,
.pnl-kpi small,
.pnl-table-card header small {
    color: #8992a3;
    font-size: 11px;
}

.pnl-kpi-grid {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(4, minmax(150px, 1fr));
}

.pnl-kpi {
    background: #0d1017;
    border: 1px solid #2b3342;
    border-radius: 8px;
    display: grid;
    gap: 6px;
    min-height: 92px;
    padding: 12px;
}

.pnl-kpi.primary {
    background: linear-gradient(135deg, rgba(84, 214, 164, 0.09), #0d1017 70%);
    border-color: rgba(84, 214, 164, 0.42);
}

.pnl-kpi strong {
    font-size: 19px;
    overflow-wrap: anywhere;
}

.positive {
    color: #54d6a4 !important;
}

.negative {
    color: #ff8f70 !important;
}

.pnl-detail-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
}

.pnl-detail-card,
.pnl-table-card,
.pnl-methodology {
    background: #0d1017;
    border: 1px solid #2b3342;
    border-radius: 8px;
}

.pnl-detail-card header,
.pnl-table-card > header {
    align-items: center;
    border-bottom: 1px solid #252b36;
    display: flex;
    justify-content: space-between;
    min-height: 52px;
    padding: 10px 12px;
}

.pnl-detail-card header {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
}

.pnl-detail-card dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin: 0;
}

.pnl-detail-card dl div {
    display: grid;
    gap: 5px;
    padding: 11px 12px;
}

.pnl-detail-card dl div:nth-child(odd) {
    border-right: 1px solid #252b36;
}

.pnl-detail-card dl div:nth-child(n + 3) {
    border-top: 1px solid #252b36;
}

.pnl-detail-card dt {
    color: #8992a3;
    font-size: 12px;
}

.pnl-detail-card dd {
    font-size: 15px;
    font-weight: 650;
    margin: 0;
}

.pnl-table-card > header > div {
    display: grid;
    gap: 4px;
}

.pnl-table-shell {
    max-height: 360px;
    overflow: auto;
}

.pnl-table {
    border-collapse: collapse;
    font-size: 13px;
    min-width: 1120px;
    width: 100%;
}

.pnl-table th,
.pnl-table td {
    border-bottom: 1px solid #252b36;
    padding: 10px 12px;
    text-align: left;
    vertical-align: top;
}

.pnl-table th {
    background: #0d1017;
    color: #8992a3;
    font-size: 12px;
    font-weight: 600;
    position: sticky;
    top: 0;
    z-index: 1;
}

.pnl-table td {
    color: #c8ceda;
}

.pnl-table td:first-child {
    max-width: 260px;
}

.pnl-table td:first-child strong,
.pnl-table td:first-child small {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.monthly-card {
    max-width: 720px;
    width: 100%;
}

.monthly-table {
    min-width: 620px;
}

.pnl-methodology {
    color: #8992a3;
    display: grid;
    font-size: 11px;
    gap: 5px;
    line-height: 1.45;
    padding: 12px;
}

.pnl-methodology strong {
    color: #c8ceda;
}

@media (max-width: 1100px) {
    .pnl-identity,
    .pnl-kpi-grid {
        grid-template-columns: 1fr 1fr;
    }

    .pnl-identity > div + div {
        border-left: 0;
    }

    .pnl-identity > div:nth-child(even) {
        border-left: 1px solid #252b36;
    }

    .pnl-identity > div:nth-child(n + 3) {
        border-top: 1px solid #252b36;
    }
}

@media (max-width: 760px) {
    .pnl-backdrop {
        padding: 10px;
    }

    .pnl-modal {
        height: calc(100vh - 20px);
        width: calc(100vw - 20px);
    }

    .pnl-toolbar,
    .pnl-identity,
    .pnl-kpi-grid,
    .pnl-detail-grid {
        grid-template-columns: 1fr;
    }

    .pnl-identity > div:nth-child(even) {
        border-left: 0;
    }

    .pnl-identity > div + div {
        border-top: 1px solid #252b36;
    }

    .pnl-detail-card dl {
        grid-template-columns: 1fr;
    }

    .pnl-detail-card dl div:nth-child(odd) {
        border-right: 0;
    }

    .pnl-detail-card dl div + div {
        border-top: 1px solid #252b36;
    }
}
</style>
