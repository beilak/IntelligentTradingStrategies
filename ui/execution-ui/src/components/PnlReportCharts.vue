<script setup lang="ts">
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { PNL_HELP } from "../pnlHelp";
import type { PnlReport } from "../types";
import MetricHelp from "./MetricHelp.vue";

use([
  BarChart,
  LineChart,
  CanvasRenderer,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
]);

const props = defineProps<{ report: PnlReport }>();
const performanceEl = ref<HTMLDivElement | null>(null);
const componentsEl = ref<HTMLDivElement | null>(null);
let performanceChart: ECharts | null = null;
let componentsChart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

onMounted(async () => {
  await nextTick();
  if (!performanceEl.value || !componentsEl.value) return;
  performanceChart = init(performanceEl.value, "dark", { renderer: "canvas" });
  componentsChart = init(componentsEl.value, "dark", { renderer: "canvas" });
  resizeObserver = new ResizeObserver(() => {
    performanceChart?.resize();
    componentsChart?.resize();
  });
  resizeObserver.observe(performanceEl.value);
  resizeObserver.observe(componentsEl.value);
  renderCharts();
});

watch(() => props.report, renderCharts, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  performanceChart?.dispose();
  componentsChart?.dispose();
});

function renderCharts() {
  renderPerformance();
  renderComponents();
}

function renderPerformance() {
  if (!performanceChart) return;
  const rows = props.report.equity_curve;
  if (!rows.length) {
    performanceChart.setOption(emptyOption("Нет данных для кривой капитала"), true);
    return;
  }
  const dates = rows.map((row) => row.date);
  const axis = (gridIndex: number) => ({
    type: "category" as const,
    gridIndex,
    data: dates,
    boundaryGap: false,
    axisLabel: { color: "#7d8596", hideOverlap: true },
    axisTick: { show: false },
    axisLine: { lineStyle: { color: "#2b3342" } },
  });
  const valueAxis = (gridIndex: number, formatter?: (value: number) => string) => ({
    type: "value" as const,
    gridIndex,
    axisLabel: { color: "#7d8596", formatter },
    splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.22)" } },
  });

  performanceChart.setOption(
    {
      animation: false,
      backgroundColor: "transparent",
      textStyle: chartTextStyle(),
      legend: {
        top: 2,
        left: 12,
        textStyle: { color: "#aeb6c6" },
        data: ["NAV", "Накопленный PnL"],
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 17, 23, 0.96)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
      },
      grid: [
        { left: 70, right: 72, top: 42, height: "40%" },
        { left: 70, right: 72, top: "54%", height: "17%" },
        { left: 70, right: 72, top: "77%", bottom: 44 },
      ],
      xAxis: [axis(0), axis(1), axis(2)],
      yAxis: [
        valueAxis(0, compactNumber),
        { ...valueAxis(0, compactNumber), position: "right" },
        valueAxis(1, compactNumber),
        valueAxis(2, (value) => `${(value * 100).toFixed(0)}%`),
      ],
      series: [
        {
          name: "NAV",
          type: "line",
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: rows.map((row) => row.nav),
          showSymbol: false,
          lineStyle: { width: 2, color: "#70a8ff" },
          areaStyle: { color: "rgba(70, 126, 219, 0.13)" },
        },
        {
          name: "Накопленный PnL",
          type: "line",
          xAxisIndex: 0,
          yAxisIndex: 1,
          data: rows.map((row) => row.cumulative_pnl),
          showSymbol: false,
          lineStyle: { width: 1.5, color: "#54d6a4" },
        },
        {
          name: "PnL за день",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 2,
          data: rows.map((row) => ({
            value: row.daily_pnl,
            itemStyle: { color: row.daily_pnl >= 0 ? "#54d6a4" : "#ff8f70" },
          })),
          barMaxWidth: 14,
        },
        {
          name: "Просадка",
          type: "line",
          xAxisIndex: 2,
          yAxisIndex: 3,
          data: rows.map((row) => row.drawdown),
          showSymbol: false,
          lineStyle: { width: 1.5, color: "#ff8f70" },
          areaStyle: { color: "rgba(255, 105, 91, 0.2)" },
        },
      ],
    } as EChartsCoreOption,
    true,
  );
}

function renderComponents() {
  if (!componentsChart) return;
  const rows = props.report.components.filter((row) => Math.abs(row.value) > 1e-10);
  if (!rows.length) {
    componentsChart.setOption(emptyOption("Нет компонентов PnL"), true);
    return;
  }
  componentsChart.setOption(
    {
      animation: false,
      backgroundColor: "transparent",
      textStyle: chartTextStyle(),
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value: number) => formatMoney(value),
        backgroundColor: "rgba(15, 17, 23, 0.96)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
      },
      grid: { left: 178, right: 34, top: 18, bottom: 36 },
      xAxis: {
        type: "value",
        axisLabel: { color: "#7d8596", formatter: compactNumber },
        splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.22)" } },
      },
      yAxis: {
        type: "category",
        data: rows.map((row) => row.label),
        axisLabel: { color: "#aeb6c6" },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [
        {
          name: "PnL",
          type: "bar",
          data: rows.map((row) => ({
            value: row.value,
            itemStyle: {
              color: row.value >= 0 ? "#54d6a4" : "#ff8f70",
              borderRadius: row.value >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
            },
          })),
          barMaxWidth: 22,
        },
      ],
    } as EChartsCoreOption,
    true,
  );
}

function emptyOption(text: string): EChartsCoreOption {
  return {
    backgroundColor: "transparent",
    title: {
      text,
      left: "center",
      top: "center",
      textStyle: { color: "#7d8596", fontSize: 14, fontWeight: 500 },
    },
  };
}

function chartTextStyle() {
  return {
    color: "#c8ceda",
    fontFamily:
      "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
  };
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value);
}
</script>

<template>
  <div class="pnl-chart-stack">
    <section class="pnl-chart-card">
      <header>
        <span class="metric-label-with-help">Доходность <MetricHelp :help="PNL_HELP.performanceChart" /></span>
        <strong>NAV · Daily PnL · Drawdown</strong>
      </header>
      <div ref="performanceEl" class="pnl-performance-chart"></div>
    </section>
    <section class="pnl-chart-card">
      <header>
        <span class="metric-label-with-help">Декомпозиция <MetricHelp :help="PNL_HELP.decomposition" /></span>
        <strong>Компоненты результата</strong>
      </header>
      <div ref="componentsEl" class="pnl-components-chart"></div>
    </section>
  </div>
</template>
