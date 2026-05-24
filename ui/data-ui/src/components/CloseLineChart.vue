<script setup lang="ts">
import { LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { MARKET_TIME_ZONE } from "../marketTime";
import type { Locale, MonteCarloClosePoint } from "../types";

use([
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LineChart,
  TitleComponent,
  TooltipComponent,
]);

const props = defineProps<{
  points: MonteCarloClosePoint[];
  locale: Locale;
  interval: string;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const orderedPoints = computed(() =>
  [...props.points]
    .filter((point) => Number.isFinite(point.close))
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
);

onMounted(async () => {
  await nextTick();
  if (!chartEl.value) {
    return;
  }

  chart = init(chartEl.value, "dark", { renderer: "canvas" });
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartEl.value);
  renderChart();
});

watch(
  () => [props.points, props.locale, props.interval],
  () => renderChart(),
  { deep: true },
);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
});

function renderChart() {
  if (!chart) {
    return;
  }

  if (!orderedPoints.value.length) {
    chart.setOption(
      {
        backgroundColor: "transparent",
        title: {
          text: props.locale === "ru" ? "Нет данных" : "No data",
          left: "center",
          top: "center",
          textStyle: { color: "#7d8596", fontSize: 14, fontWeight: 500 },
        },
      } as EChartsCoreOption,
      true,
    );
    return;
  }

  const labels = orderedPoints.value.map((point) => point.time);
  const values = orderedPoints.value.map((point) => point.close);

  chart.setOption(
    {
      animation: false,
      backgroundColor: "transparent",
      textStyle: {
        color: "#c8ceda",
        fontFamily:
          "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 17, 23, 0.94)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
        formatter: (params: unknown) => formatTooltip(params),
      },
      grid: { left: 54, right: 22, top: 20, bottom: 52 },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#2b3342" } },
        axisLabel: {
          color: "#7d8596",
          formatter: (value: string) => formatAxisTime(value),
          hideOverlap: true,
        },
        axisTick: { show: false },
        splitLine: { show: false },
        min: "dataMin",
        max: "dataMax",
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: "#7d8596" },
        splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.24)" } },
      },
      dataZoom: [
        {
          type: "inside",
          start: Math.max(0, 100 - Math.min(100, (120 / orderedPoints.value.length) * 100)),
          end: 100,
        },
        {
          show: true,
          type: "slider",
          bottom: 12,
          height: 18,
          borderColor: "#2b3342",
          fillerColor: "rgba(84, 214, 164, 0.16)",
          handleStyle: { color: "#54d6a4" },
          textStyle: { color: "#7d8596" },
        },
      ],
      series: [
        {
          name: props.locale === "ru" ? "Закрытие" : "Close",
          type: "line",
          data: values,
          showSymbol: false,
          smooth: false,
          lineStyle: { color: "#54d6a4", width: 2 },
          itemStyle: { color: "#54d6a4" },
        },
      ],
    } as EChartsCoreOption,
    true,
  );
}

function formatTooltip(params: unknown) {
  const rows = Array.isArray(params) ? params : [];
  const firstRow = rows[0] as { dataIndex?: number } | undefined;
  const point = orderedPoints.value[firstRow?.dataIndex ?? 0];
  const close = point ? formatNumber(point.close) : "";

  return [point ? formatFullTime(point.time) : "", close].filter(Boolean).join("<br />");
}

function formatAxisTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  if (isIntradayInterval()) {
    return `${formatDatePart(parsed)}\n${formatTimePart(parsed)}`;
  }

  if (props.interval === "CANDLE_INTERVAL_MONTH") {
    return new Intl.DateTimeFormat(currentLocale(), {
      timeZone: MARKET_TIME_ZONE,
      month: "short",
      year: "2-digit",
    }).format(parsed);
  }

  return formatDatePart(parsed);
}

function formatFullTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const options: Intl.DateTimeFormatOptions = isIntradayInterval()
    ? {
        timeZone: MARKET_TIME_ZONE,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }
    : {
        timeZone: MARKET_TIME_ZONE,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      };

  return new Intl.DateTimeFormat(currentLocale(), options).format(parsed);
}

function formatDatePart(value: Date) {
  return new Intl.DateTimeFormat(currentLocale(), {
    timeZone: MARKET_TIME_ZONE,
    month: "short",
    day: "2-digit",
  }).format(value);
}

function formatTimePart(value: Date) {
  return new Intl.DateTimeFormat(currentLocale(), {
    timeZone: MARKET_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
  }).format(value);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat(currentLocale(), {
    maximumFractionDigits: 4,
  }).format(value);
}

function isIntradayInterval() {
  return props.interval.includes("_MIN") || props.interval.includes("_HOUR");
}

function currentLocale() {
  return props.locale === "ru" ? "ru-RU" : "en-US";
}
</script>

<template>
  <div ref="chartEl" class="close-chart"></div>
</template>

<style scoped>
.close-chart {
  min-height: 320px;
  width: 100%;
}

@media (max-width: 780px) {
  .close-chart {
    min-height: 280px;
  }
}
</style>
