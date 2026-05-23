<script setup lang="ts">
import { PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { AllocationItem } from "../types";

use([CanvasRenderer, GridComponent, LegendComponent, PieChart, TitleComponent, TooltipComponent]);

const props = defineProps<{
  allocation: AllocationItem[];
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const rows = computed(() =>
  props.allocation
    .filter((item) => Number.isFinite(item.value ?? NaN) && Number(item.value) > 0)
    .map((item) => ({
      name: bucketName(item.bucket),
      value: Number(item.value),
    })),
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
      color: ["#54d6a4", "#66d9ef", "#ffcc66", "#ff8f70", "#b48cf2", "#e9edf5"],
      textStyle: {
        color: "#c8ceda",
        fontFamily:
          "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
      },
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(15, 17, 23, 0.94)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
        valueFormatter: (value: number) => formatCompact(value),
      },
      legend: {
        bottom: 2,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "#8992a3", fontSize: 11 },
      },
      series: [
        {
          name: "Allocation",
          type: "pie",
          radius: ["48%", "72%"],
          center: ["50%", "44%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "#11141b", borderWidth: 2 },
          label: {
            color: "#c8ceda",
            formatter: "{b}",
            fontSize: 11,
          },
          labelLine: { lineStyle: { color: "#4e586e" } },
          data: rows.value,
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

function formatCompact(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
    notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
  }).format(value);
}
</script>

<template>
  <div ref="chartEl" class="chart-host"></div>
</template>
