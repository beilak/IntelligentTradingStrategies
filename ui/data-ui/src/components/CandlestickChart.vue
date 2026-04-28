<script setup lang="ts">
import { BarChart, CandlestickChart } from "echarts/charts";
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { Candle, Locale } from "../types";

use([
  AxisPointerComponent,
  BarChart,
  CandlestickChart,
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  TitleComponent,
  TooltipComponent,
]);

const props = defineProps<{
  candles: Candle[];
  locale: Locale;
  interval: string;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const orderedCandles = computed(() =>
  [...props.candles].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
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
  () => [props.candles, props.locale, props.interval],
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

  if (!orderedCandles.value.length) {
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

  const labels = orderedCandles.value.map((candle) => formatAxisTime(candle.time));
  const candles = orderedCandles.value.map((candle) => [
    candle.open,
    candle.close,
    candle.low,
    candle.high,
  ]);
  const volumes = orderedCandles.value.map((candle) => ({
    value: candle.volume ?? 0,
    itemStyle: {
      color: candle.close >= candle.open ? "rgba(84, 214, 164, 0.42)" : "rgba(255, 107, 138, 0.42)",
    },
  }));

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
        axisPointer: { type: "cross" },
        backgroundColor: "rgba(15, 17, 23, 0.94)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
        formatter: (params: unknown) => formatTooltip(params),
      },
      axisPointer: {
        link: [{ xAxisIndex: "all" }],
        label: { backgroundColor: "#2b3342" },
      },
      grid: [
        { left: 48, right: 20, top: 18, height: "64%" },
        { left: 48, right: 20, bottom: 30, height: "18%" },
      ],
      xAxis: [
        {
          type: "category",
          data: labels,
          boundaryGap: true,
          axisLine: { lineStyle: { color: "#2b3342" } },
          axisLabel: {
            color: "#7d8596",
            hideOverlap: true,
          },
          axisTick: { show: false },
          splitLine: { show: false },
          min: "dataMin",
          max: "dataMax",
        },
        {
          type: "category",
          gridIndex: 1,
          data: labels,
          boundaryGap: true,
          axisLine: { lineStyle: { color: "#2b3342" } },
          axisLabel: {
            color: "#7d8596",
            hideOverlap: true,
          },
          axisTick: { show: false },
          splitLine: { show: false },
          min: "dataMin",
          max: "dataMax",
        },
      ],
      yAxis: [
        {
          scale: true,
          splitArea: { show: false },
          axisLabel: { color: "#7d8596" },
          splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.24)" } },
        },
        {
          scale: true,
          gridIndex: 1,
          axisLabel: { color: "#7d8596" },
          splitNumber: 2,
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: [0, 1],
          start: Math.max(0, 100 - Math.min(100, (80 / orderedCandles.value.length) * 100)),
          end: 100,
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: "slider",
          bottom: 4,
          height: 18,
          borderColor: "#2b3342",
          fillerColor: "rgba(84, 214, 164, 0.16)",
          handleStyle: { color: "#54d6a4" },
          textStyle: { color: "#7d8596" },
        },
      ],
      series: [
        {
          name: props.locale === "ru" ? "Цена" : "Price",
          type: "candlestick",
          data: candles,
          itemStyle: {
            color: "#54d6a4",
            color0: "#ff6b8a",
            borderColor: "#54d6a4",
            borderColor0: "#ff6b8a",
          },
        },
        {
          name: props.locale === "ru" ? "Объем" : "Volume",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          large: true,
        },
      ],
    } as EChartsCoreOption,
    true,
  );
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
      month: "short",
      year: "2-digit",
    }).format(parsed);
  }

  if (props.interval === "CANDLE_INTERVAL_WEEK") {
    return new Intl.DateTimeFormat(currentLocale(), {
      month: "short",
      day: "2-digit",
      year: "2-digit",
    }).format(parsed);
  }

  return formatDatePart(parsed);
}

function formatTooltip(params: unknown) {
  const rows = Array.isArray(params) ? params : [];
  const firstRow = rows[0] as { dataIndex?: number } | undefined;
  const candle = orderedCandles.value[firstRow?.dataIndex ?? 0];
  const title = candle ? formatFullTime(candle.time) : "";

  const body = rows
    .map((row) => {
      const item = row as { marker?: string; seriesName?: string; data?: unknown };
      if (Array.isArray(item.data)) {
        const [open, close, low, high] = item.data;
        return `${item.marker ?? ""}${item.seriesName}: O ${open} H ${high} L ${low} C ${close}`;
      }
      if (typeof item.data === "object" && item.data !== null && "value" in item.data) {
        return `${item.marker ?? ""}${item.seriesName}: ${String(item.data.value)}`;
      }
      return "";
    })
    .filter(Boolean)
    .join("<br />");

  return [title, body].filter(Boolean).join("<br />");
}

function formatFullTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const options: Intl.DateTimeFormatOptions = isIntradayInterval()
    ? {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: isSecondsInterval() ? "2-digit" : undefined,
      }
    : {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      };

  return new Intl.DateTimeFormat(currentLocale(), options).format(parsed);
}

function formatDatePart(value: Date) {
  return new Intl.DateTimeFormat(currentLocale(), {
    month: "short",
    day: "2-digit",
  }).format(value);
}

function formatTimePart(value: Date) {
  return new Intl.DateTimeFormat(currentLocale(), {
    hour: "2-digit",
    minute: "2-digit",
    second: isSecondsInterval() ? "2-digit" : undefined,
  }).format(value);
}

function isIntradayInterval() {
  return (
    props.interval.includes("_SEC") ||
    props.interval.includes("_MIN") ||
    props.interval.includes("_HOUR")
  );
}

function isSecondsInterval() {
  return props.interval.includes("_SEC");
}

function currentLocale() {
  return props.locale === "ru" ? "ru-RU" : "en-US";
}
</script>

<template>
  <div ref="chartEl" class="chart"></div>
</template>

<style scoped>
.chart {
  min-height: 420px;
  width: 100%;
}

@media (max-width: 780px) {
  .chart {
    min-height: 360px;
  }
}
</style>
