<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { StrategyRunResult } from "../types";

use([BarChart, CanvasRenderer, GridComponent, TitleComponent, TooltipComponent]);

const props = defineProps<{
  result: StrategyRunResult | null;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const targetRows = computed(() =>
  [...(props.result?.target_weights ?? [])]
    .filter((item) => item.target_weight > 0)
    .sort((a, b) => b.target_weight - a.target_weight)
    .slice(0, 12),
);

const orderRows = computed(() =>
  [...(props.result?.orders ?? [])]
    .sort((a, b) => Math.abs(b.estimated_amount) - Math.abs(a.estimated_amount))
    .slice(0, 12),
);

onMounted(async () => {
  await nextTick();
  if (!chartEl.value) return;
  chart = init(chartEl.value, "dark", { renderer: "canvas" });
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartEl.value);
  renderChart();
});

watch(() => props.result, () => renderChart(), { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
});

function renderChart() {
  if (!chart) return;

  if (!props.result || (!targetRows.value.length && !orderRows.value.length)) {
    chart.setOption(
      {
        backgroundColor: "transparent",
        title: {
          text: "Нет расчетного плана",
          left: "center",
          top: "center",
          textStyle: { color: "#7d8596", fontSize: 14, fontWeight: 500 },
        },
      } as EChartsCoreOption,
      true,
    );
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
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(15, 17, 23, 0.94)",
        borderColor: "#2b3342",
        textStyle: { color: "#f4f6fb" },
      },
      grid: [
        { left: 54, right: 18, top: 28, height: "38%" },
        { left: 54, right: 18, bottom: 34, height: "34%" },
      ],
      xAxis: [
        {
          type: "category",
          data: targetRows.value.map((item) => item.ticker),
          axisLabel: { color: "#8992a3", rotate: 28 },
          axisLine: { lineStyle: { color: "#2b3342" } },
          axisTick: { show: false },
        },
        {
          type: "category",
          gridIndex: 1,
          data: orderRows.value.map((item) => item.ticker),
          axisLabel: { color: "#8992a3", rotate: 28 },
          axisLine: { lineStyle: { color: "#2b3342" } },
          axisTick: { show: false },
        },
      ],
      yAxis: [
        {
          type: "value",
          name: "Вес, %",
          nameTextStyle: { color: "#8992a3" },
          axisLabel: { color: "#8992a3" },
          splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.24)" } },
        },
        {
          type: "value",
          gridIndex: 1,
          name: "Сумма",
          nameTextStyle: { color: "#8992a3" },
          axisLabel: { color: "#8992a3" },
          splitLine: { lineStyle: { color: "rgba(78, 88, 110, 0.24)" } },
        },
      ],
      series: [
        {
          name: "Целевой вес",
          type: "bar",
          data: targetRows.value.map((item) => +(item.target_weight * 100).toFixed(3)),
          itemStyle: { color: "#54d6a4" },
          barMaxWidth: 28,
        },
        {
          name: "План приказов",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: orderRows.value.map((item) =>
            item.side === "buy" ? item.estimated_amount : -item.estimated_amount,
          ),
          itemStyle: {
            color: (params: { value: number }) =>
              params.value >= 0 ? "#54d6a4" : "#ff8f70",
          },
          barMaxWidth: 28,
        },
      ],
    } as EChartsCoreOption,
    true,
  );
}
</script>

<template>
  <div ref="chartEl" class="strategy-plan-chart"></div>
</template>
