<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { AllocationItem } from "../types";

use([BarChart, CanvasRenderer, GridComponent, TitleComponent, TooltipComponent]);

const props = defineProps<{
  allocation: AllocationItem[];
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const rows = computed(() =>
  props.allocation
    .filter((item) => Number.isFinite(item.value ?? NaN))
    .map((item) => ({ name: bucketName(item.bucket), value: Number(item.value) }))
    .sort((a, b) => b.value - a.value),
);

onMounted(async () => {
  await nextTick();
  if (!chartEl.value) return;
  chart = init(chartEl.value, "dark", { renderer: "canvas" });
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartEl.value);
  renderChart();
});

watch(() => props.allocation, () => renderChart(), { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
});

function renderChart() {
  if (!chart) return;

  if (!rows.value.length) {
    chart.setOption(emptyOption(), true);
    return;
  }

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
        valueFormatter: (value: number) => formatNumber(value),
      },
      grid: { left: 88, right: 22, top: 16, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { color: "#7d8596" },
        splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.24)" } },
      },
      yAxis: {
        type: "category",
        data: rows.value.map((row) => row.name),
        axisLabel: { color: "#aeb7c8" },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#2b3342" } },
      },
      series: [
        {
          name: "Сумма",
          type: "bar",
          data: rows.value.map((row) => row.value),
          itemStyle: {
            color: "#66d9ef",
            borderRadius: [0, 4, 4, 0],
          },
          barMaxWidth: 22,
        },
      ],
    } as EChartsCoreOption,
    true,
  );
}

function emptyOption(): EChartsCoreOption {
  return {
    backgroundColor: "transparent",
    title: {
      text: "Нет данных",
      left: "center",
      top: "center",
      textStyle: { color: "#7d8596", fontSize: 14, fontWeight: 500 },
    },
  };
}

function bucketName(bucket: string): string {
  const names: Record<string, string> = {
    shares: "Акции",
    bonds: "Облигации",
    etf: "ETF",
    currencies: "Валюта",
    futures: "Фьючерсы",
    options: "Опционы",
    structured_products: "СП",
    dfa: "ЦФА",
  };
  return names[bucket] ?? bucket;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value);
}
</script>

<template>
  <div ref="chartEl" class="chart-host"></div>
</template>
