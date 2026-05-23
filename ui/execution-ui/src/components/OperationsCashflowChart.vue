<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { OperationItem } from "../types";

use([BarChart, CanvasRenderer, GridComponent, TitleComponent, TooltipComponent]);

const props = defineProps<{
  operations: OperationItem[];
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const rows = computed(() => {
  const grouped = new Map<string, number>();
  props.operations.forEach((operation) => {
    if (!operation.date || !Number.isFinite(operation.payment?.value ?? NaN)) return;
    const day = operation.date.slice(0, 10);
    grouped.set(day, (grouped.get(day) ?? 0) + Number(operation.payment?.value ?? 0));
  });
  return Array.from(grouped.entries())
    .map(([date, value]) => ({ date, value }))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-40);
});

onMounted(async () => {
  await nextTick();
  if (!chartEl.value) return;
  chart = init(chartEl.value, "dark", { renderer: "canvas" });
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartEl.value);
  renderChart();
});

watch(() => props.operations, () => renderChart(), { deep: true });

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
        valueFormatter: (value: number) => formatMoney(value),
      },
      grid: { left: 56, right: 22, top: 16, bottom: 44 },
      xAxis: {
        type: "category",
        data: rows.value.map((row) => row.date),
        axisLabel: { color: "#7d8596", hideOverlap: true },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#2b3342" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#7d8596" },
        splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.24)" } },
      },
      series: [
        {
          name: "Cashflow",
          type: "bar",
          data: rows.value.map((row) => row.value),
          itemStyle: {
            color: (params: { value: number }) => (params.value >= 0 ? "#54d6a4" : "#ff8f70"),
            borderRadius: [4, 4, 0, 0],
          },
          barMaxWidth: 18,
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

function formatMoney(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
    signDisplay: "exceptZero",
  }).format(value);
}
</script>

<template>
  <div ref="chartEl" class="chart-host"></div>
</template>
