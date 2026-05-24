<script setup lang="ts">
import { LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { MARKET_TIME_ZONE } from "../marketTime";
import type { Locale, MonteCarloClosePoint, MonteCarloPathPoint } from "../types";

use([
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LineChart,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
]);

const props = defineProps<{
  training: MonteCarloClosePoint[];
  paths: MonteCarloPathPoint[];
  locale: Locale;
  interval: string;
  trainUntil?: string | null;
}>();

const pathColors = [
  "rgba(108, 174, 255, 0.34)",
  "rgba(255, 204, 102, 0.34)",
  "rgba(255, 107, 138, 0.3)",
  "rgba(189, 147, 249, 0.32)",
  "rgba(78, 205, 196, 0.32)",
  "rgba(255, 159, 67, 0.3)",
];

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const orderedTraining = computed(() =>
  [...props.training]
    .filter((point) => Number.isFinite(point.close))
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
);

const groupedPaths = computed(() => {
  const groups = new Map<number, MonteCarloPathPoint[]>();
  for (const point of props.paths) {
    if (!Number.isFinite(point.close)) {
      continue;
    }
    const group = groups.get(point.path_id) ?? [];
    group.push(point);
    groups.set(point.path_id, group);
  }

  return [...groups.entries()]
    .sort(([left], [right]) => left - right)
    .map(([pathId, points]) => ({
      pathId,
      points: points.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
    }));
});

const labels = computed(() => {
  const values = new Set<string>();
  orderedTraining.value.forEach((point) => values.add(point.time));
  groupedPaths.value.forEach((path) => path.points.forEach((point) => values.add(point.time)));

  return [...values].sort((a, b) => new Date(a).getTime() - new Date(b).getTime());
});

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
  () => [props.training, props.paths, props.locale, props.interval, props.trainUntil],
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

  if (!labels.value.length) {
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

  const trainingSeries = {
    name: props.locale === "ru" ? "Факт до обучения" : "Actual before training",
    type: "line",
    data: buildAlignedData(orderedTraining.value),
    showSymbol: false,
    smooth: false,
    connectNulls: false,
    lineStyle: { color: "#54d6a4", width: 2.4 },
    itemStyle: { color: "#54d6a4" },
    markLine: props.trainUntil
      ? {
          silent: true,
          symbol: "none",
          label: {
            color: "#ffcc66",
            formatter: props.locale === "ru" ? "старт" : "start",
          },
          lineStyle: { color: "#ffcc66", type: "dashed", width: 1 },
          data: [{ xAxis: props.trainUntil }],
        }
      : undefined,
  };

  const pathSeries = groupedPaths.value.map((path, index) => ({
    name: `${props.locale === "ru" ? "Путь" : "Path"} ${path.pathId}`,
    type: "line",
    data: buildAlignedData(path.points),
    showSymbol: false,
    smooth: false,
    connectNulls: false,
    lineStyle: {
      color: pathColors[index % pathColors.length],
      width: 1,
      opacity: 0.74,
    },
    itemStyle: { color: pathColors[index % pathColors.length] },
    emphasis: {
      lineStyle: {
        width: 2,
        opacity: 0.95,
      },
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
        backgroundColor: "rgba(15, 17, 23, 0.94)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
        formatter: (params: unknown) => formatTooltip(params),
      },
      grid: { left: 54, right: 22, top: 20, bottom: 52 },
      xAxis: {
        type: "category",
        data: labels.value,
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
          start: Math.max(0, 100 - Math.min(100, (140 / labels.value.length) * 100)),
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
      series: [trainingSeries, ...pathSeries],
    } as EChartsCoreOption,
    true,
  );
}

function buildAlignedData(points: Array<MonteCarloClosePoint | MonteCarloPathPoint>) {
  const byTime = new Map(points.map((point) => [point.time, point.close]));
  return labels.value.map((label) => byTime.get(label) ?? null);
}

function formatTooltip(params: unknown) {
  const rows = Array.isArray(params) ? params : [];
  const firstRow = rows[0] as { axisValue?: string } | undefined;
  const title = firstRow?.axisValue ? formatFullTime(firstRow.axisValue) : "";
  const visibleRows = rows
    .filter((row) => {
      const item = row as { data?: unknown };
      return typeof item.data === "number";
    })
    .slice(0, 12)
    .map((row) => {
      const item = row as { marker?: string; seriesName?: string; data?: number };
      return `${item.marker ?? ""}${item.seriesName}: ${formatNumber(item.data ?? 0)}`;
    });

  if (rows.length > visibleRows.length) {
    visibleRows.push(`+${rows.length - visibleRows.length}`);
  }

  return [title, ...visibleRows].filter(Boolean).join("<br />");
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
  <div ref="chartEl" class="monte-carlo-chart"></div>
</template>

<style scoped>
.monte-carlo-chart {
  min-height: 380px;
  width: 100%;
}

@media (max-width: 780px) {
  .monte-carlo-chart {
    min-height: 320px;
  }
}
</style>
