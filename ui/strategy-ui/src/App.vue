<script setup lang="ts">
import {
    BarChart3,
    Boxes,
    BrainCircuit,
    DatabaseZap,
    FolderOpen,
    GitBranch,
    Globe2,
    Layers3,
    PlayCircle,
    RefreshCw,
    Scale,
    SearchCheck,
    Trophy,
    X,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import {
    getBacktestTest,
    getCpcvTest,
    getLatestStrategyComparison,
    getModelDetail,
    getRegistry,
    getTradingStrategyBacktestTest,
    getTradingStrategyDetail,
    getWalkForwardTest,
    listBacktestTests,
    listCpcvTests,
    listTradingStrategyBacktestTests,
    listWalkForwardTests,
    runBacktestTest,
    runCpcvTest,
    runTradingStrategyBacktestTest,
    runWalkForwardTest,
} from "./api";
import { messages, cpcvMetricTranslations } from "./i18n";
import type {
    BacktestResult,
    BacktestSavedTest,
    BacktestSettings,
    CpcvResult,
    CpcvSavedTest,
    CpcvSettings,
    Locale,
    ModelDetail,
    RegistryGroup,
    RegistryItem,
    RegistryResponse,
    StrategyComparisonResult,
    WalkForwardResult,
    WalkForwardSavedTest,
    WalkForwardSettings,
} from "./types";

const savedLocale = localStorage.getItem(
    "its-strategy-locale",
) as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");
const t = computed(() => messages[locale.value]);

const registry = ref<RegistryResponse | null>(null);
const selectedGroupId = ref("strategy_model");
const selectedModelName = ref("");
const modelDetail = ref<ModelDetail | null>(null);
const isLoading = ref(false);
const isModelLoading = ref(false);
const isCpcvRunning = ref(false);
const isCpcvLoading = ref(false);
const isWalkForwardRunning = ref(false);
const isWalkForwardLoading = ref(false);
const isBacktestRunning = ref(false);
const isBacktestLoading = ref(false);
const isComparisonLoading = ref(false);
const error = ref("");
const cpcvError = ref("");
const walkForwardError = ref("");
const backtestError = ref("");
const comparisonError = ref("");
const savedCpcvTests = ref<CpcvSavedTest[]>([]);
const savedWalkForwardTests = ref<WalkForwardSavedTest[]>([]);
const savedBacktestTests = ref<BacktestSavedTest[]>([]);
const cpcvResult = ref<CpcvResult | null>(null);
const walkForwardResult = ref<WalkForwardResult | null>(null);
const backtestResult = ref<BacktestResult | null>(null);
const comparisonResult = ref<StrategyComparisonResult | null>(null);
const cpcvSettings = ref<CpcvSettings>(defaultCpcvSettings());
const walkForwardSettings = ref<WalkForwardSettings>(
    defaultWalkForwardSettings(),
);
const backtestSettings = ref<BacktestSettings>(defaultBacktestSettings());
const showCpcvModal = ref(false);
const showWalkForwardModal = ref(false);
const showBacktestModal = ref(false);
const showComparisonModal = ref(false);
const showAssetsModal = ref(false);
const showWeightsModal = ref(false);
const activeAssetsSource = ref<"cpcv" | "walkForward">("cpcv");
const selectedWeightRecord = ref<
    BacktestResult["rebalance_weights"][number] | null
>(null);
const xAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const yAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const wfXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const wfYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const wfOosXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const wfOosYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const backtestEquityXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const backtestEquityYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const backtestDrawdownXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const backtestDrawdownYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const backtestSharpeXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const backtestSharpeYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const isFullscreen = ref(false);
const chartContainer = ref<HTMLElement | null>(null);
const walkForwardChartContainer = ref<HTMLElement | null>(null);

const groups = computed(() => registry.value?.groups ?? []);
const selectedGroup = computed<RegistryGroup | undefined>(() =>
    groups.value.find((group) => group.id === selectedGroupId.value),
);
const selectedItems = computed<RegistryItem[]>(
    () => selectedGroup.value?.items ?? [],
);
const isCoreStrategyTab = computed(
    () => selectedGroupId.value === "strategy_model",
);
const isTradingStrategyTab = computed(
    () => selectedGroupId.value === "trading_strategy_model",
);
const isTestableStrategyTab = computed(
    () => isCoreStrategyTab.value || isTradingStrategyTab.value,
);
const chartLines = computed(() => buildChartLines(cpcvResult.value));
const walkForwardChartLines = computed(() =>
    buildChartLines(walkForwardResult.value, wfXAxisLabels, wfYAxisLabels),
);
const walkForwardOosChartLines = computed(() =>
    buildChartLines(
        walkForwardOosChartResult.value,
        wfOosXAxisLabels,
        wfOosYAxisLabels,
    ),
);
const walkForwardOosChartResult = computed(() => {
    const curve = walkForwardResult.value?.oos_curve;
    if (!curve?.points?.length) return null;
    const segments = curve.segments?.length
        ? curve.segments
        : [
              {
                  name: curve.name,
                  final_return: curve.final_return ?? 0,
                  points: curve.points,
              },
          ];
    return {
        paths: segments,
    };
});
const backtestEquityLines = computed(() =>
    buildChartLines(
        curveToChartResult(backtestResult.value?.equity_curve),
        backtestEquityXAxisLabels,
        backtestEquityYAxisLabels,
        "money",
        ["#aee9d1"],
    ),
);
const backtestDrawdownLines = computed(() =>
    buildChartLines(
        curveToChartResult(backtestResult.value?.drawdown_curve),
        backtestDrawdownXAxisLabels,
        backtestDrawdownYAxisLabels,
        "percent",
        ["#ff6b8a"],
    ),
);
const backtestSharpeLines = computed(() =>
    buildChartLines(
        curveToChartResult(backtestResult.value?.rolling_sharpe),
        backtestSharpeXAxisLabels,
        backtestSharpeYAxisLabels,
        "number",
        ["#ffcc66"],
    ),
);
const activeAssets = computed(() =>
    activeAssetsSource.value === "walkForward"
        ? (walkForwardResult.value?.metadata.assets ?? [])
        : (cpcvResult.value?.metadata.assets ?? []),
);
const activeAssetCount = computed(() =>
    activeAssetsSource.value === "walkForward"
        ? (walkForwardResult.value?.metadata.asset_count ?? 0)
        : (cpcvResult.value?.metadata.asset_count ?? 0),
);
const pieSegments = computed(() =>
    buildPieSegments(selectedWeightRecord.value),
);
const sectorRows = computed(() =>
    buildSectorRows(selectedWeightRecord.value, backtestResult.value),
);
const sectorPieSegments = computed(() =>
    buildSectorPieSegments(sectorRows.value),
);
const comparisonExplanations = computed(() =>
    Array.isArray(t.value.comparisonExplanations)
        ? t.value.comparisonExplanations
        : [],
);

watch(locale, (value) => localStorage.setItem("its-strategy-locale", value));

onMounted(async () => {
    await loadRegistry();
    document.addEventListener("fullscreenchange", () => {
        isFullscreen.value = !!document.fullscreenElement;
    });
});

async function loadRegistry() {
    isLoading.value = true;
    error.value = "";
    try {
        registry.value = await getRegistry();
        selectedModelName.value = registry.value.models[0]?.name ?? "";
        if (selectedModelName.value) {
            await loadModel(selectedModelName.value);
        }
    } catch (err) {
        error.value = formatError(err);
    } finally {
        isLoading.value = false;
    }
}

async function loadModel(modelName: string) {
    selectedModelName.value = modelName;
    isModelLoading.value = true;
    error.value = "";
    try {
        modelDetail.value = await getModelDetail(modelName);
        cpcvResult.value = null;
        walkForwardResult.value = null;
        backtestResult.value = null;
        cpcvError.value = "";
        walkForwardError.value = "";
        backtestError.value = "";
        comparisonError.value = "";
        await loadSavedCpcvTests(modelName);
        await loadSavedWalkForwardTests(modelName);
        await loadSavedBacktestTests(modelName);
    } catch (err) {
        error.value = formatError(err);
    } finally {
        isModelLoading.value = false;
    }
}

async function loadTradingStrategy(strategyName: string) {
    selectedModelName.value = strategyName;
    isModelLoading.value = true;
    error.value = "";
    try {
        modelDetail.value = await getTradingStrategyDetail(strategyName);
        cpcvResult.value = null;
        walkForwardResult.value = null;
        backtestResult.value = null;
        cpcvError.value = "";
        walkForwardError.value = "";
        backtestError.value = "";
        comparisonError.value = "";
        savedCpcvTests.value = [];
        savedWalkForwardTests.value = [];
        await loadSavedBacktestTests(strategyName);
    } catch (err) {
        error.value = formatError(err);
    } finally {
        isModelLoading.value = false;
    }
}

async function openComparison() {
    showComparisonModal.value = true;
    await loadComparison();
}

async function loadComparison() {
    isComparisonLoading.value = true;
    comparisonError.value = "";
    try {
        comparisonResult.value = await getLatestStrategyComparison();
    } catch (err) {
        comparisonError.value = formatError(err);
    } finally {
        isComparisonLoading.value = false;
    }
}

async function setGroup(groupId: string) {
    selectedGroupId.value = groupId;
    const firstItem = registry.value?.groups.find(
        (group) => group.id === groupId,
    )?.items[0];
    if (!firstItem) return;
    if (groupId === "strategy_model") {
        await loadModel(firstItem.name);
    } else if (groupId === "trading_strategy_model") {
        await loadTradingStrategy(firstItem.name);
    }
}

async function selectRegistryItem(itemName: string) {
    if (selectedGroupId.value === "strategy_model") {
        await loadModel(itemName);
    } else if (selectedGroupId.value === "trading_strategy_model") {
        await loadTradingStrategy(itemName);
    }
}

function iconFor(groupId: string) {
    return (
        {
            pre_selection: SearchCheck,
            signal_model: BrainCircuit,
            allocation: Scale,
            strategy_model: Boxes,
            trading_strategy_model: PlayCircle,
        }[groupId] ?? Layers3
    );
}

function labelFor(groupId: string) {
    const value = (t.value as Record<string, string | string[]>)[groupId];
    return typeof value === "string" ? value : groupId;
}

function formatError(err: unknown) {
    return err instanceof Error ? err.message : String(err);
}

async function loadSavedCpcvTests(modelName = selectedModelName.value) {
    if (!modelName) return;
    isCpcvLoading.value = true;
    try {
        savedCpcvTests.value = (await listCpcvTests(modelName)).items;
    } catch (err) {
        cpcvError.value = formatError(err);
    } finally {
        isCpcvLoading.value = false;
    }
}

async function openCpcvTest(testName: string) {
    if (!selectedModelName.value) return;
    isCpcvLoading.value = true;
    cpcvError.value = "";
    try {
        cpcvResult.value = await getCpcvTest(selectedModelName.value, testName);
        cpcvSettings.value = {
            ...cpcvSettings.value,
            ...cpcvResult.value.metadata.settings,
        };
    } catch (err) {
        cpcvError.value = formatError(err);
    } finally {
        isCpcvLoading.value = false;
    }
}

async function runCpcv() {
    if (!selectedModelName.value) return;
    isCpcvRunning.value = true;
    cpcvError.value = "";
    try {
        cpcvResult.value = await runCpcvTest(
            selectedModelName.value,
            cpcvSettings.value,
        );
        await loadSavedCpcvTests(selectedModelName.value);
    } catch (err) {
        cpcvError.value = formatError(err);
    } finally {
        isCpcvRunning.value = false;
    }
}

async function loadSavedWalkForwardTests(modelName = selectedModelName.value) {
    if (!modelName) return;
    isWalkForwardLoading.value = true;
    try {
        savedWalkForwardTests.value = (
            await listWalkForwardTests(modelName)
        ).items;
    } catch (err) {
        walkForwardError.value = formatError(err);
    } finally {
        isWalkForwardLoading.value = false;
    }
}

async function openWalkForwardTest(testName: string) {
    if (!selectedModelName.value) return;
    isWalkForwardLoading.value = true;
    walkForwardError.value = "";
    try {
        walkForwardResult.value = await getWalkForwardTest(
            selectedModelName.value,
            testName,
        );
        walkForwardSettings.value = {
            ...walkForwardSettings.value,
            ...walkForwardResult.value.metadata.settings,
        };
    } catch (err) {
        walkForwardError.value = formatError(err);
    } finally {
        isWalkForwardLoading.value = false;
    }
}

async function runWalkForward() {
    if (!selectedModelName.value) return;
    isWalkForwardRunning.value = true;
    walkForwardError.value = "";
    try {
        walkForwardResult.value = await runWalkForwardTest(
            selectedModelName.value,
            walkForwardSettings.value,
        );
        await loadSavedWalkForwardTests(selectedModelName.value);
    } catch (err) {
        walkForwardError.value = formatError(err);
    } finally {
        isWalkForwardRunning.value = false;
    }
}

async function loadSavedBacktestTests(modelName = selectedModelName.value) {
    if (!modelName) return;
    isBacktestLoading.value = true;
    try {
        savedBacktestTests.value = isTradingStrategyTab.value
            ? (await listTradingStrategyBacktestTests(modelName)).items
            : (await listBacktestTests(modelName)).items;
    } catch (err) {
        backtestError.value = formatError(err);
    } finally {
        isBacktestLoading.value = false;
    }
}

async function openBacktestTest(testName: string) {
    if (!selectedModelName.value) return;
    isBacktestLoading.value = true;
    backtestError.value = "";
    try {
        backtestResult.value = isTradingStrategyTab.value
            ? await getTradingStrategyBacktestTest(
                  selectedModelName.value,
                  testName,
              )
            : await getBacktestTest(selectedModelName.value, testName);
        backtestSettings.value = {
            ...backtestSettings.value,
            ...backtestResult.value.metadata.settings,
            fees: (backtestResult.value.metadata.settings.fees ?? 0) * 100,
            tax_rate:
                (backtestResult.value.metadata.settings.tax_rate ?? 0) * 100,
        };
    } catch (err) {
        backtestError.value = formatError(err);
    } finally {
        isBacktestLoading.value = false;
    }
}

async function runBacktest() {
    if (!selectedModelName.value) return;
    isBacktestRunning.value = true;
    backtestError.value = "";
    try {
        backtestResult.value = isTradingStrategyTab.value
            ? await runTradingStrategyBacktestTest(
                  selectedModelName.value,
                  backendBacktestSettings(),
              )
            : await runBacktestTest(
                  selectedModelName.value,
                  backendBacktestSettings(),
              );
        await loadSavedBacktestTests(selectedModelName.value);
    } catch (err) {
        backtestError.value = formatError(err);
    } finally {
        isBacktestRunning.value = false;
    }
}

function backendBacktestSettings(): BacktestSettings {
    return {
        ...backtestSettings.value,
        fees: backtestSettings.value.fees / 100,
        tax_rate: backtestSettings.value.tax_rate / 100,
        slippage: 0,
    };
}

function defaultCpcvSettings(): CpcvSettings {
    const end = new Date();
    const start = new Date(end);
    start.setMonth(start.getMonth() - 9);
    return {
        test_name: "baseline",
        start_date: toDateInput(start),
        end_date: toDateInput(end),
        interval: "CANDLE_INTERVAL_DAY",
        class_code: "TQBR",
        n_folds: 10,
        n_test_folds: 6,
        test_size: 0.33,
    };
}

function defaultWalkForwardSettings(): WalkForwardSettings {
    const end = new Date();
    const start = new Date(end);
    start.setMonth(start.getMonth() - 9);
    return {
        test_name: "baseline",
        start_date: toDateInput(start),
        end_date: toDateInput(end),
        interval: "CANDLE_INTERVAL_DAY",
        class_code: "TQBR",
        test_size: 0.33,
        train_size_months: 3,
        freq_months: 3,
        wf_test_size: 1,
    };
}

function defaultBacktestSettings(): BacktestSettings {
    const end = new Date();
    const start = new Date(end);
    start.setFullYear(start.getFullYear() - 3);
    const tradingStart = new Date(start);
    tradingStart.setFullYear(tradingStart.getFullYear() + 1);
    return {
        test_name: "baseline",
        start_date: toDateInput(start),
        end_date: toDateInput(end),
        interval: "CANDLE_INTERVAL_DAY",
        class_code: "TQBR",
        trading_start_date: toDateInput(tradingStart),
        rebalance_freq: "3ME",
        rebalance_on: "last",
        init_cash: 1_000_000,
        fees: 0.08,
        slippage: 0,
        freq: "1D",
        rolling_window: 252,
        tax_rate: 13,
    };
}

function toDateInput(value: Date) {
    return value.toISOString().slice(0, 10);
}

function formatMoneyInput(value: number) {
    if (!Number.isFinite(value)) return "";
    return Math.round(value)
        .toLocaleString("ru-RU")
        .replace(/\u00a0/g, " ");
}

function updateInitCash(event: Event) {
    const raw = (event.target as HTMLInputElement).value.replace(/\s/g, "");
    const value = Number(raw);
    if (Number.isFinite(value)) {
        backtestSettings.value.init_cash = value;
    }
}

async function toggleFullscreen() {
    if (!chartContainer.value) return;
    if (document.fullscreenElement) {
        await document.exitFullscreen();
    } else {
        await chartContainer.value.requestFullscreen();
    }
}

async function toggleWalkForwardFullscreen() {
    if (!walkForwardChartContainer.value) return;
    if (document.fullscreenElement) {
        await document.exitFullscreen();
    } else {
        await walkForwardChartContainer.value.requestFullscreen();
    }
}

function formatDateTime(value?: string) {
    if (!value) return "—";
    return value.replace("T", " ").replace(/\.\d+.*$/, "");
}

function translateMetric(metric: string): string {
    return cpcvMetricTranslations[locale.value][metric] ?? metric;
}

function formatPercent(value: number) {
    return `${(value * 100).toFixed(1)}%`;
}

function formatWeight(value: number) {
    return `${(value * 100).toFixed(2)}%`;
}

function formatPrice(value: number | null | undefined) {
    if (value === null || value === undefined || !Number.isFinite(value))
        return "—";
    return value.toLocaleString(locale.value === "ru" ? "ru-RU" : "en-US", {
        maximumFractionDigits: 4,
    });
}

function formatEventReason(reason: string) {
    return (
        {
            stop_loss: t.value.stopLoss,
            take_profit: t.value.takeProfit,
        }[reason] ?? reason
    );
}

function formatScore(value: number | null | undefined) {
    if (value === null || value === undefined || !Number.isFinite(value))
        return "—";
    return value.toFixed(2);
}

function formatMetricValue(
    value: number | null | undefined,
    mode: "percent" | "number" = "number",
) {
    if (value === null || value === undefined || !Number.isFinite(value))
        return "—";
    if (mode === "percent") return `${(value * 100).toFixed(2)}%`;
    return value.toLocaleString(locale.value === "ru" ? "ru-RU" : "en-US", {
        maximumFractionDigits: 4,
    });
}

function testTypeLabel(value: string) {
    return (
        {
            cpcv: "CPCV",
            walk_forward: "WalkForward",
            backtesting: "Backtesting",
        }[value] ?? value
    );
}

function openAssetsModal(source: "cpcv" | "walkForward") {
    activeAssetsSource.value = source;
    showAssetsModal.value = true;
}

function openWeightsModal(record: BacktestResult["rebalance_weights"][number]) {
    selectedWeightRecord.value = record;
    showWeightsModal.value = true;
}

function curveToChartResult(curve?: {
    name: string;
    final_value: number | null;
    points: Array<{ time: string; value: number }>;
}) {
    if (!curve?.points?.length) return null;
    return {
        paths: [
            {
                name: curve.name,
                final_return: curve.final_value ?? 0,
                points: curve.points,
            },
        ],
    };
}

function buildChartLines(
    result: {
        paths: Array<{ points: Array<{ time: string; value: number }> }>;
    } | null,
    xLabelsRef = xAxisLabels,
    yLabelsRef = yAxisLabels,
    yFormat: "percent" | "money" | "number" = "percent",
    palette = [
        "#66d9ef",
        "#ffcc66",
        "#aee9d1",
        "#ff6b8a",
        "#b48cf2",
        "#7dd3fc",
    ],
) {
    const paths = result?.paths ?? [];
    const values = paths.flatMap((path) =>
        path.points.map((point) => point.value),
    );
    const timestamps = paths.flatMap((path) =>
        path.points
            .map((point) => new Date(point.time).getTime())
            .filter((value) => Number.isFinite(value)),
    );
    if (!values.length) {
        xLabelsRef.value = [];
        yLabelsRef.value = [];
        return [];
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const width = 720;
    const height = 260;
    const pad = 48;
    const colors = palette;
    const minTime = timestamps.length ? Math.min(...timestamps) : 0;
    const maxTime = timestamps.length ? Math.max(...timestamps) : 1;
    const timeRange = maxTime - minTime || 1;

    const timePoints = [...(paths.flatMap((path) => path.points) ?? [])].sort(
        (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
    );

    const xLabels: Array<{ x: number; text: string }> = [];
    if (timePoints.length > 0) {
        const step = Math.max(1, Math.ceil(timePoints.length / 5));
        const indices = [0];
        for (let i = step; i < timePoints.length - 1; i += step)
            indices.push(i);
        if (timePoints.length > 1) indices.push(timePoints.length - 1);

        indices.forEach((pointIndex) => {
            const d = new Date(timePoints[pointIndex].time);
            const x =
                pad + ((d.getTime() - minTime) / timeRange) * (width - pad * 2);
            const text = `${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
            xLabels.push({ x, text });
        });
    }
    xLabelsRef.value = xLabels;

    const yLabels: Array<{ y: number; text: string }> = [];
    const tickCount = 5;
    for (let i = 0; i <= tickCount; i++) {
        const tick = min + (range * i) / tickCount;
        const y = height - pad - ((tick - min) / range) * (height - pad * 2);
        yLabels.push({ y, text: formatAxisValue(tick, yFormat) });
    }
    yLabelsRef.value = yLabels;

    return paths.map((path, index) => {
        const points = path.points
            .map((point) => {
                const pointTime = new Date(point.time).getTime();
                const x =
                    pad +
                    ((pointTime - minTime) / timeRange) * (width - pad * 2);
                const y =
                    height -
                    pad -
                    ((point.value - min) / range) * (height - pad * 2);
                return `${x.toFixed(2)},${y.toFixed(2)}`;
            })
            .join(" ");
        return {
            points,
            color: colors[index % colors.length],
            opacity: Math.max(0.18, 0.86 - index * 0.004),
        };
    });
}

function formatAxisValue(value: number, mode: "percent" | "money" | "number") {
    if (mode === "money") {
        return Math.round(value).toLocaleString("ru-RU", {
            notation: "compact",
            maximumFractionDigits: 1,
        });
    }
    if (mode === "number") {
        return value.toFixed(2);
    }
    return `${(value * 100).toFixed(1)}%`;
}

function buildPieSegments(
    record: BacktestResult["rebalance_weights"][number] | null,
) {
    if (!record) return [];
    const colors = [
        "#66d9ef",
        "#ffcc66",
        "#aee9d1",
        "#ff6b8a",
        "#b48cf2",
        "#7dd3fc",
        "#fca5a5",
        "#86efac",
        "#f9a8d4",
        "#93c5fd",
    ];
    const total =
        record.weights.reduce(
            (sum, item) => sum + Math.max(item.weight, 0),
            0,
        ) || 1;
    let cursor = 0;
    return record.weights.map((item, index) => {
        const start = cursor / total;
        cursor += Math.max(item.weight, 0);
        const end = cursor / total;
        const middle = (start + end) / 2;
        const labelPosition = polarPoint(112, 112, 92, middle);
        return {
            ...item,
            color: colors[index % colors.length],
            d: piePath(112, 112, 86, start, end),
            labelX: labelPosition.x,
            labelY: labelPosition.y,
            showLabel: item.weight / total >= 0.025,
        };
    });
}

function buildSectorRows(
    record: BacktestResult["rebalance_weights"][number] | null,
    result: BacktestResult | null,
) {
    if (!record) return [];
    const tickerSector = new Map(
        (result?.metadata.assets ?? []).map((asset) => [
            asset.ticker,
            normalizeSector(asset.sector),
        ]),
    );
    const sectors = new Map<
        string,
        { sector: string; weight: number; asset_count: number }
    >();

    record.weights.forEach((item) => {
        const sector = normalizeSector(
            item.sector ?? tickerSector.get(item.ticker),
        );
        const current = sectors.get(sector) ?? {
            sector,
            weight: 0,
            asset_count: 0,
        };
        current.weight += item.weight;
        current.asset_count += 1;
        sectors.set(sector, current);
    });

    return [...sectors.values()].sort((a, b) => b.weight - a.weight);
}

function buildSectorPieSegments(
    rows: Array<{ sector: string; weight: number; asset_count: number }>,
) {
    const colors = [
        "#7dd3fc",
        "#f9a8d4",
        "#aee9d1",
        "#ffcc66",
        "#b48cf2",
        "#fca5a5",
        "#86efac",
        "#93c5fd",
        "#ff6b8a",
        "#66d9ef",
    ];
    const total =
        rows.reduce((sum, item) => sum + Math.max(item.weight, 0), 0) || 1;
    let cursor = 0;
    return rows.map((item, index) => {
        const start = cursor / total;
        cursor += Math.max(item.weight, 0);
        const end = cursor / total;
        const middle = (start + end) / 2;
        const labelPosition = polarPoint(112, 112, 92, middle);
        return {
            ...item,
            color: colors[index % colors.length],
            d: piePath(112, 112, 86, start, end),
            labelX: labelPosition.x,
            labelY: labelPosition.y,
            showLabel: item.weight / total >= 0.04,
        };
    });
}

function normalizeSector(sector?: string | null) {
    const value = String(sector ?? "").trim();
    return value || t.value.unknownSector;
}

function colorForWeightItem(ticker: string) {
    return (
        pieSegments.value.find((segment) => segment.ticker === ticker)?.color ??
        "#8992a3"
    );
}

function colorForSector(sector: string) {
    return (
        sectorPieSegments.value.find((segment) => segment.sector === sector)
            ?.color ?? "#8992a3"
    );
}

function sectorForTicker(ticker: string) {
    const weight = selectedWeightRecord.value?.weights.find(
        (item) => item.ticker === ticker,
    );
    if (weight?.sector) {
        return normalizeSector(weight.sector);
    }
    const asset = backtestResult.value?.metadata.assets.find(
        (item) => item.ticker === ticker,
    );
    return normalizeSector(asset?.sector);
}

function piePath(
    cx: number,
    cy: number,
    radius: number,
    startRatio: number,
    endRatio: number,
) {
    const start = polarPoint(cx, cy, radius, startRatio);
    const end = polarPoint(cx, cy, radius, endRatio);
    const largeArc = endRatio - startRatio > 0.5 ? 1 : 0;
    return [
        `M ${cx} ${cy}`,
        `L ${start.x} ${start.y}`,
        `A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`,
        "Z",
    ].join(" ");
}

function polarPoint(cx: number, cy: number, radius: number, ratio: number) {
    const angle = ratio * Math.PI * 2 - Math.PI / 2;
    return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
    };
}
</script>

<template>
    <div class="app-shell">
        <header class="topbar">
            <div class="brand">
                <div class="brand-mark">
                    <DatabaseZap :size="22" />
                </div>
                <div>
                    <strong>{{ t.appTitle }}</strong>
                    <span>{{ t.appSubtitle }}</span>
                </div>
            </div>

            <div class="top-actions" :aria-label="t.language">
                <Globe2 :size="18" />
                <div class="segmented">
                    <button
                        type="button"
                        :class="{ active: locale === 'ru' }"
                        @click="locale = 'ru'"
                    >
                        RU
                    </button>
                    <button
                        type="button"
                        :class="{ active: locale === 'en' }"
                        @click="locale = 'en'"
                    >
                        EN
                    </button>
                </div>
                <button class="icon-button" type="button" @click="loadRegistry">
                    <RefreshCw
                        :class="{ spin: isLoading || isModelLoading }"
                        :size="17"
                    />
                </button>
            </div>
        </header>

        <main class="workspace">
            <aside class="source-rail">
                <button
                    v-for="group in groups"
                    :key="group.id"
                    class="source-item"
                    :class="{ active: selectedGroupId === group.id }"
                    type="button"
                    @click="setGroup(group.id)"
                >
                    <component :is="iconFor(group.id)" :size="18" />
                    <span>{{ labelFor(group.id) }}</span>
                    <small>{{ group.count }}</small>
                </button>
            </aside>

            <section class="content">
                <p v-if="error" class="error-banner">{{ error }}</p>

                <section class="hero-panel">
                    <div>
                        <span>{{ t.middleLayerName }}</span>
                        <strong>{{
                            selectedGroup
                                ? labelFor(selectedGroup.id)
                                : t.loading
                        }}</strong>
                    </div>
                    <p>{{ selectedGroup?.role }}</p>
                </section>

                <section
                    class="main-grid"
                    :class="{ 'single-column': !isTestableStrategyTab }"
                >
                    <div class="registry-panel">
                        <div class="panel-head">
                            <div>
                                <span>{{ t.components }}</span>
                                <strong>{{
                                    selectedGroup
                                        ? labelFor(selectedGroup.id)
                                        : "—"
                                }}</strong>
                            </div>
                            <Layers3 :size="18" />
                        </div>

                        <div v-if="isLoading" class="empty-state">
                            <RefreshCw class="spin" :size="24" />
                            <span>{{ t.loading }}</span>
                        </div>

                        <div
                            v-else-if="selectedItems.length === 0"
                            class="empty-state"
                        >
                            <span>{{ t.empty }}</span>
                        </div>

                        <div v-else class="component-list">
                            <article
                                v-for="item in selectedItems"
                                :key="`${item.module}.${item.name}`"
                                class="component-card"
                                :class="{
                                    selected: item.name === selectedModelName,
                                }"
                                @click="selectRegistryItem(item.name)"
                            >
                                <div class="card-title">
                                    <strong>{{ item.name }}</strong>
                                    <span>{{ item.kind }}</span>
                                </div>
                                <p>{{ item.description || t.empty }}</p>
                                <code>{{ item.signature || item.module }}</code>
                            </article>
                        </div>
                    </div>

                    <div v-if="isTestableStrategyTab" class="detail-panel">
                        <div class="panel-head">
                            <div>
                                <span>{{ t.models }}</span>
                                <strong>{{
                                    modelDetail?.name ?? t.selectModel
                                }}</strong>
                            </div>
                            <GitBranch :size="18" />
                        </div>

                        <div v-if="isModelLoading" class="empty-state">
                            <RefreshCw class="spin" :size="24" />
                            <span>{{ t.loading }}</span>
                        </div>

                        <template v-else-if="modelDetail">
                            <section class="detail-section">
                                <span>{{ t.description }}</span>
                                <p>{{ modelDetail.description || t.empty }}</p>
                                <code>{{ modelDetail.module }}</code>
                            </section>

                            <section class="detail-section">
                                <span>{{ t.composition }}</span>
                                <div class="steps">
                                    <article
                                        v-for="step in modelDetail.composition
                                            .steps"
                                        :key="step.step"
                                        class="step"
                                    >
                                        <small>{{
                                            labelFor(step.category)
                                        }}</small>
                                        <strong>{{ step.step }}</strong>
                                        <code>{{ step.component }}</code>
                                    </article>
                                </div>
                            </section>

                            <section class="detail-section">
                                <span>{{ t.testing }}</span>
                                <div class="report-grid">
                                    <button
                                        v-if="isCoreStrategyTab"
                                        class="report-btn"
                                        type="button"
                                        @click="showCpcvModal = true"
                                    >
                                        <strong>CPCV</strong>
                                    </button>
                                    <button
                                        v-if="isCoreStrategyTab"
                                        class="report-btn"
                                        type="button"
                                        @click="showWalkForwardModal = true"
                                    >
                                        <strong>WalkForward</strong>
                                    </button>
                                    <button
                                        class="report-btn"
                                        type="button"
                                        @click="showBacktestModal = true"
                                    >
                                        <strong>Backtesting</strong>
                                    </button>
                                    <article
                                        v-for="report in modelDetail.future_reports.filter(
                                            (item) =>
                                                ![
                                                    'cpcv',
                                                    'walk_forward',
                                                    'backtesting',
                                                ].includes(item.id),
                                        )"
                                        :key="report.id"
                                        class="report"
                                    >
                                        <strong>{{ report.title }}</strong>
                                        <small>{{ t.planned }}</small>
                                    </article>
                                </div>
                                <button
                                    v-if="isCoreStrategyTab"
                                    class="report-btn featured comparison-wide-btn"
                                    type="button"
                                    @click="openComparison"
                                >
                                    <BarChart3 :size="18" />
                                    <div>
                                        <strong>{{
                                            t.strategyComparison
                                        }}</strong>
                                        <small>{{
                                            t.strategyComparisonSubtitle
                                        }}</small>
                                    </div>
                                </button>
                            </section>
                        </template>
                    </div>
                </section>
            </section>

            <div
                v-if="showComparisonModal"
                class="modal-overlay"
                @click.self="showComparisonModal = false"
            >
                <div class="modal-fullscreen">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.strategyComparisonSubtitle }}</span>
                            <strong>{{ t.strategyComparison }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showComparisonModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>

                    <p v-if="comparisonError" class="error-banner">
                        {{ comparisonError }}
                    </p>

                    <div class="cpcv-actions">
                        <button
                            class="primary-button"
                            type="button"
                            :disabled="isComparisonLoading"
                            @click="loadComparison"
                        >
                            <RefreshCw
                                v-if="isComparisonLoading"
                                class="spin"
                                :size="17"
                            />
                            <BarChart3 v-else :size="17" />
                            <span>{{
                                isComparisonLoading
                                    ? t.processing
                                    : t.runComparison
                            }}</span>
                        </button>
                        <small v-if="comparisonResult">{{
                            formatDateTime(comparisonResult.generated_at)
                        }}</small>
                    </div>

                    <div v-if="isComparisonLoading" class="empty-state">
                        <RefreshCw class="spin" :size="24" />
                        <span>{{ t.loading }}</span>
                    </div>

                    <div v-else-if="comparisonResult" class="comparison-layout">
                        <section class="result-strip">
                            <article>
                                <span>{{ t.eligibleModels }}</span>
                                <strong>{{
                                    comparisonResult.eligible_count
                                }}</strong>
                            </article>
                            <article>
                                <span>{{ t.skippedModels }}</span>
                                <strong>{{
                                    comparisonResult.skipped.length
                                }}</strong>
                            </article>
                            <article>
                                <span>{{ t.recommendation }}</span>
                                <strong>{{
                                    comparisonResult.winner?.model_name ?? "—"
                                }}</strong>
                                <small
                                    >{{ t.totalScore }}:
                                    {{
                                        formatScore(
                                            comparisonResult.winner
                                                ?.TOTAL_SCORE,
                                        )
                                    }}</small
                                >
                            </article>
                        </section>

                        <section
                            v-if="comparisonResult.rows.length"
                            class="chart-panel"
                        >
                            <div class="section-title">
                                <span>{{ t.strategyComparison }}</span>
                                <strong>{{
                                    comparisonResult.rows.length
                                }}</strong>
                            </div>
                            <div class="table-scroll">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>#</th>
                                            <th>{{ t.models }}</th>
                                            <th>{{ t.totalScore }}</th>
                                            <th>WF Return</th>
                                            <th>WF Calmar</th>
                                            <th>Robustness Delta</th>
                                            <th>Sharpe Stability</th>
                                            <th>{{ t.metricWins }}</th>
                                            <th>Backtest Return</th>
                                            <th>Backtest Sharpe</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr
                                            v-for="row in comparisonResult.rows"
                                            :key="row.model_name"
                                        >
                                            <td>
                                                <strong class="rank-badge">
                                                    <Trophy
                                                        v-if="row.rank === 1"
                                                        :size="14"
                                                    />
                                                    {{ row.rank }}
                                                </strong>
                                            </td>
                                            <td>
                                                <strong>{{
                                                    row.model_name
                                                }}</strong>
                                            </td>
                                            <td>
                                                {{
                                                    formatScore(row.TOTAL_SCORE)
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        row.WF_Return,
                                                        "percent",
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        row.WF_Calmar,
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        row.Robustness_Delta,
                                                        "percent",
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        row.Sharpe_Stability,
                                                        "percent",
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatScore(
                                                        row.Backtest_Metric_Wins,
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        row.Backtest_Total_Return,
                                                        "percent",
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        row.Backtest_Sharpe,
                                                    )
                                                }}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </section>

                        <section v-else class="empty-state">
                            <span>{{ t.noComparison }}</span>
                        </section>

                        <section
                            v-if="comparisonResult.rows.length"
                            class="dual-chart-grid"
                        >
                            <div class="chart-panel">
                                <div class="section-title">
                                    <span>{{ t.latestTests }}</span>
                                    <strong>{{
                                        comparisonResult.rows[0].model_name
                                    }}</strong>
                                </div>
                                <div class="saved-list">
                                    <article
                                        v-for="(
                                            test, testType
                                        ) in comparisonResult.rows[0]
                                            .latest_tests"
                                        :key="testType"
                                        class="saved-card"
                                    >
                                        <div>
                                            <strong
                                                >{{
                                                    testTypeLabel(
                                                        String(testType),
                                                    )
                                                }}
                                                / {{ test.test_name }}</strong
                                            >
                                            <small>{{
                                                formatDateTime(
                                                    test.generated_at,
                                                )
                                            }}</small>
                                        </div>
                                        <code>{{ test.file_name }}</code>
                                    </article>
                                </div>
                            </div>

                            <div class="chart-panel">
                                <div class="section-title">
                                    <span>{{ t.backtestWinners }}</span>
                                    <strong>{{
                                        comparisonResult.backtest_winners.length
                                    }}</strong>
                                </div>
                                <div class="metrics-grid compact-metrics">
                                    <div
                                        v-for="item in comparisonResult.backtest_winners"
                                        :key="`${item.metric}-${item.winner}`"
                                        class="metric-item"
                                    >
                                        <span class="metric-label">{{
                                            translateMetric(item.metric)
                                        }}</span>
                                        <span class="metric-value"
                                            >{{ item.winner }} ·
                                            {{
                                                formatMetricValue(item.value)
                                            }}</span
                                        >
                                    </div>
                                </div>
                                <div
                                    v-if="
                                        comparisonResult.backtest_winners
                                            .length === 0
                                    "
                                    class="small-state"
                                >
                                    {{ t.noBacktestWinners }}
                                </div>
                            </div>
                        </section>

                        <section class="dual-chart-grid">
                            <div class="chart-panel">
                                <div class="section-title">
                                    <span>{{ t.skippedModels }}</span>
                                    <strong>{{
                                        comparisonResult.skipped.length
                                    }}</strong>
                                </div>
                                <div
                                    v-if="comparisonResult.skipped.length"
                                    class="saved-list"
                                >
                                    <article
                                        v-for="item in comparisonResult.skipped"
                                        :key="item.model_name"
                                        class="saved-card"
                                    >
                                        <div>
                                            <strong>{{
                                                item.model_name
                                            }}</strong>
                                            <small>{{
                                                [
                                                    ...item.missing_tests,
                                                    ...(item.missing_metrics ??
                                                        []),
                                                ].join(", ")
                                            }}</small>
                                        </div>
                                    </article>
                                </div>
                                <div v-else class="small-state">
                                    {{ t.empty }}
                                </div>
                            </div>

                            <div class="chart-panel">
                                <div class="section-title">
                                    <span>{{ t.explanation }}</span>
                                    <strong>{{ t.totalScore }}</strong>
                                </div>
                                <div class="comparison-notes">
                                    <p
                                        v-for="item in comparisonExplanations"
                                        :key="item"
                                    >
                                        {{ item }}
                                    </p>
                                </div>
                            </div>
                        </section>
                    </div>
                </div>
            </div>

            <div
                v-if="showCpcvModal"
                class="modal-overlay"
                @click.self="showCpcvModal = false"
            >
                <div class="modal-fullscreen">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.cpcvSettings }}</span>
                            <strong>{{ t.cpcv }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showCpcvModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>

                    <p v-if="cpcvError" class="error-banner">{{ cpcvError }}</p>

                    <div class="cpcv-layout">
                        <div class="form-grid">
                            <label>
                                <span>{{ t.testName }}</span>
                                <input
                                    v-model="cpcvSettings.test_name"
                                    type="text"
                                />
                            </label>
                            <label>
                                <span>{{ t.startDate }}</span>
                                <input
                                    v-model="cpcvSettings.start_date"
                                    type="date"
                                />
                            </label>
                            <label>
                                <span>{{ t.endDate }}</span>
                                <input
                                    v-model="cpcvSettings.end_date"
                                    type="date"
                                />
                            </label>
                            <label>
                                <span>{{ t.interval }}</span>
                                <select v-model="cpcvSettings.interval">
                                    <option value="CANDLE_INTERVAL_DAY">
                                        Day
                                    </option>
                                    <option value="CANDLE_INTERVAL_HOUR">
                                        Hour
                                    </option>
                                    <option value="CANDLE_INTERVAL_WEEK">
                                        Week
                                    </option>
                                    <option value="CANDLE_INTERVAL_MONTH">
                                        Month
                                    </option>
                                </select>
                            </label>
                            <label>
                                <span>{{ t.classCode }}</span>
                                <input
                                    v-model="cpcvSettings.class_code"
                                    type="text"
                                />
                            </label>
                            <label>
                                <span>{{ t.nFolds }}</span>
                                <input
                                    v-model.number="cpcvSettings.n_folds"
                                    min="2"
                                    max="30"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span>{{ t.nTestFolds }}</span>
                                <input
                                    v-model.number="cpcvSettings.n_test_folds"
                                    min="1"
                                    max="29"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span>{{ t.testSize }}</span>
                                <input
                                    v-model.number="cpcvSettings.test_size"
                                    min="0.05"
                                    max="0.50"
                                    step="0.01"
                                    type="number"
                                />
                            </label>
                        </div>

                        <div class="cpcv-actions">
                            <button
                                class="primary-button"
                                type="button"
                                :disabled="isCpcvRunning"
                                @click="runCpcv"
                            >
                                <RefreshCw
                                    v-if="isCpcvRunning"
                                    class="spin"
                                    :size="17"
                                />
                                <PlayCircle v-else :size="17" />
                                <span>{{
                                    isCpcvRunning ? t.processing : t.runAndSave
                                }}</span>
                            </button>
                        </div>
                    </div>

                    <div class="saved-tests">
                        <div class="section-title">
                            <span>{{ t.savedTests }}</span>
                            <strong>{{ savedCpcvTests.length }}</strong>
                        </div>
                        <div v-if="isCpcvLoading" class="small-state">
                            <RefreshCw class="spin" :size="17" />
                            <span>{{ t.loading }}</span>
                        </div>
                        <div
                            v-else-if="savedCpcvTests.length === 0"
                            class="small-state"
                        >
                            <span>{{ t.noSavedTests }}</span>
                        </div>
                        <div v-else class="saved-list">
                            <article
                                v-for="test in savedCpcvTests"
                                :key="test.file_name"
                                class="saved-card"
                            >
                                <div>
                                    <strong>{{ test.test_name }}</strong>
                                    <small>{{
                                        formatDateTime(test.generated_at)
                                    }}</small>
                                </div>
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openCpcvTest(test.test_name)"
                                >
                                    <FolderOpen :size="16" />
                                    <span>{{ t.loadSaved }}</span>
                                </button>
                            </article>
                        </div>
                    </div>

                    <div v-if="cpcvResult" class="cpcv-results">
                        <div class="result-strip">
                            <article>
                                <span>{{ t.train }}</span>
                                <strong>{{
                                    cpcvResult.metadata.train_period.rows
                                }}</strong>
                                <small
                                    >{{
                                        formatDateTime(
                                            cpcvResult.metadata.train_period
                                                .start,
                                        )
                                    }}
                                    -
                                    {{
                                        formatDateTime(
                                            cpcvResult.metadata.train_period
                                                .end,
                                        )
                                    }}</small
                                >
                            </article>
                            <article>
                                <span>{{ t.test }}</span>
                                <strong>{{
                                    cpcvResult.metadata.test_period.rows
                                }}</strong>
                                <small
                                    >{{
                                        formatDateTime(
                                            cpcvResult.metadata.test_period
                                                .start,
                                        )
                                    }}
                                    -
                                    {{
                                        formatDateTime(
                                            cpcvResult.metadata.test_period.end,
                                        )
                                    }}</small
                                >
                            </article>
                            <article>
                                <span>{{ t.assets }}</span>
                                <strong>{{
                                    cpcvResult.metadata.asset_count
                                }}</strong>
                                <small>{{
                                    cpcvResult.metadata.settings.interval
                                }}</small>
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openAssetsModal('cpcv')"
                                >
                                    <span>{{ t.viewAssets }}</span>
                                </button>
                            </article>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.testPaths }}</span>
                                <strong>{{ cpcvResult.paths.length }}</strong>
                            </div>
                            <div ref="chartContainer" class="chart-wrapper">
                                <button
                                    class="fullscreen-btn"
                                    type="button"
                                    @click="toggleFullscreen"
                                >
                                    {{
                                        isFullscreen ? "Exit ⛶" : "Fullscreen ⛶"
                                    }}
                                </button>
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line x1="48" y1="212" x2="702" y2="212" />
                                    <line x1="48" y1="18" x2="48" y2="212" />
                                    <polyline
                                        v-for="(line, index) in chartLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        v-for="(label, i) in xAxisLabels"
                                        :key="'x' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(label, i) in yAxisLabels"
                                        :key="'y' + i"
                                        :x="44"
                                        :y="label.y"
                                        text-anchor="end"
                                        font-size="10"
                                        fill="#8992a3"
                                        dominant-baseline="middle"
                                    >
                                        {{ label.text }}
                                    </text>
                                </svg>
                            </div>
                        </div>

                        <div class="metrics-container">
                            <div class="metrics-section">
                                <div class="section-title">
                                    <span>{{ t.metrics }}</span>
                                    <strong>{{
                                        cpcvResult.metadata.test_name
                                    }}</strong>
                                </div>
                                <div class="metrics-grid">
                                    <div
                                        v-for="row in cpcvResult.report"
                                        :key="row.metric"
                                        class="metric-item"
                                    >
                                        <span class="metric-label">{{
                                            translateMetric(row.metric)
                                        }}</span>
                                        <span class="metric-value">{{
                                            row.value
                                        }}</span>
                                    </div>
                                </div>
                            </div>

                            <div class="metrics-section">
                                <div class="section-title">
                                    <span>{{ t.cvSummary }}</span>
                                    <strong>CPCV</strong>
                                </div>
                                <div class="metrics-grid">
                                    <div
                                        v-for="row in cpcvResult.cv_summary"
                                        :key="row.metric"
                                        class="metric-item"
                                    >
                                        <span class="metric-label">{{
                                            translateMetric(row.metric)
                                        }}</span>
                                        <span class="metric-value">{{
                                            row.value
                                        }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div
                v-if="showWalkForwardModal"
                class="modal-overlay"
                @click.self="showWalkForwardModal = false"
            >
                <div class="modal-fullscreen">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.walkForwardSettings }}</span>
                            <strong>{{ t.walkForward }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showWalkForwardModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>

                    <p v-if="walkForwardError" class="error-banner">
                        {{ walkForwardError }}
                    </p>

                    <div class="cpcv-layout">
                        <div class="form-grid">
                            <label>
                                <span>{{ t.testName }}</span>
                                <input
                                    v-model="walkForwardSettings.test_name"
                                    type="text"
                                />
                            </label>
                            <label>
                                <span>{{ t.startDate }}</span>
                                <input
                                    v-model="walkForwardSettings.start_date"
                                    type="date"
                                />
                            </label>
                            <label>
                                <span>{{ t.endDate }}</span>
                                <input
                                    v-model="walkForwardSettings.end_date"
                                    type="date"
                                />
                            </label>
                            <label>
                                <span>{{ t.interval }}</span>
                                <select v-model="walkForwardSettings.interval">
                                    <option value="CANDLE_INTERVAL_DAY">
                                        Day
                                    </option>
                                    <option value="CANDLE_INTERVAL_HOUR">
                                        Hour
                                    </option>
                                    <option value="CANDLE_INTERVAL_WEEK">
                                        Week
                                    </option>
                                    <option value="CANDLE_INTERVAL_MONTH">
                                        Month
                                    </option>
                                </select>
                            </label>
                            <label>
                                <span>{{ t.classCode }}</span>
                                <input
                                    v-model="walkForwardSettings.class_code"
                                    type="text"
                                />
                            </label>
                            <label>
                                <span>{{ t.testSize }}</span>
                                <input
                                    v-model.number="
                                        walkForwardSettings.test_size
                                    "
                                    min="0.05"
                                    max="0.80"
                                    step="0.01"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span>{{ t.trainSizeMonths }}</span>
                                <input
                                    v-model.number="
                                        walkForwardSettings.train_size_months
                                    "
                                    min="1"
                                    max="120"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span>{{ t.freqMonths }}</span>
                                <input
                                    v-model.number="
                                        walkForwardSettings.freq_months
                                    "
                                    min="1"
                                    max="120"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span>{{ t.wfTestSize }}</span>
                                <input
                                    v-model.number="
                                        walkForwardSettings.wf_test_size
                                    "
                                    min="1"
                                    max="500"
                                    type="number"
                                />
                            </label>
                        </div>

                        <div class="cpcv-actions">
                            <button
                                class="primary-button"
                                type="button"
                                :disabled="isWalkForwardRunning"
                                @click="runWalkForward"
                            >
                                <RefreshCw
                                    v-if="isWalkForwardRunning"
                                    class="spin"
                                    :size="17"
                                />
                                <PlayCircle v-else :size="17" />
                                <span>{{
                                    isWalkForwardRunning
                                        ? t.processing
                                        : t.runAndSave
                                }}</span>
                            </button>
                        </div>
                    </div>

                    <div class="saved-tests">
                        <div class="section-title">
                            <span>{{ t.savedTests }}</span>
                            <strong>{{ savedWalkForwardTests.length }}</strong>
                        </div>
                        <div v-if="isWalkForwardLoading" class="small-state">
                            <RefreshCw class="spin" :size="17" />
                            <span>{{ t.loading }}</span>
                        </div>
                        <div
                            v-else-if="savedWalkForwardTests.length === 0"
                            class="small-state"
                        >
                            <span>{{ t.noSavedTests }}</span>
                        </div>
                        <div v-else class="saved-list">
                            <article
                                v-for="test in savedWalkForwardTests"
                                :key="test.file_name"
                                class="saved-card"
                            >
                                <div>
                                    <strong>{{ test.test_name }}</strong>
                                    <small>{{
                                        formatDateTime(test.generated_at)
                                    }}</small>
                                </div>
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openWalkForwardTest(test.test_name)"
                                >
                                    <FolderOpen :size="16" />
                                    <span>{{ t.loadSaved }}</span>
                                </button>
                            </article>
                        </div>
                    </div>

                    <div v-if="walkForwardResult" class="cpcv-results">
                        <div class="result-strip">
                            <article>
                                <span>{{ t.train }}</span>
                                <strong>{{
                                    walkForwardResult.metadata.train_period.rows
                                }}</strong>
                                <small
                                    >{{
                                        formatDateTime(
                                            walkForwardResult.metadata
                                                .train_period.start,
                                        )
                                    }}
                                    -
                                    {{
                                        formatDateTime(
                                            walkForwardResult.metadata
                                                .train_period.end,
                                        )
                                    }}</small
                                >
                            </article>
                            <article>
                                <span>{{ t.test }}</span>
                                <strong>{{
                                    walkForwardResult.metadata.test_period.rows
                                }}</strong>
                                <small
                                    >{{
                                        formatDateTime(
                                            walkForwardResult.metadata
                                                .test_period.start,
                                        )
                                    }}
                                    -
                                    {{
                                        formatDateTime(
                                            walkForwardResult.metadata
                                                .test_period.end,
                                        )
                                    }}</small
                                >
                            </article>
                            <article>
                                <span>{{ t.assets }}</span>
                                <strong>{{
                                    walkForwardResult.metadata.asset_count
                                }}</strong>
                                <small>{{
                                    walkForwardResult.metadata.settings.interval
                                }}</small>
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openAssetsModal('walkForward')"
                                >
                                    <span>{{ t.viewAssets }}</span>
                                </button>
                            </article>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.stitchedOosCurve }}</span>
                                <strong>{{ t.walkForwardOosBacktest }}</strong>
                            </div>
                            <div
                                ref="walkForwardChartContainer"
                                class="chart-wrapper"
                            >
                                <button
                                    class="fullscreen-btn"
                                    type="button"
                                    @click="toggleWalkForwardFullscreen"
                                >
                                    {{
                                        isFullscreen ? "Exit ⛶" : "Fullscreen ⛶"
                                    }}
                                </button>
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line x1="48" y1="212" x2="702" y2="212" />
                                    <line x1="48" y1="18" x2="48" y2="212" />
                                    <polyline
                                        v-for="(
                                            line, index
                                        ) in walkForwardOosChartLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        v-for="(label, i) in wfOosXAxisLabels"
                                        :key="'wfoosx' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(label, i) in wfOosYAxisLabels"
                                        :key="'wfoosy' + i"
                                        :x="44"
                                        :y="label.y"
                                        text-anchor="end"
                                        font-size="10"
                                        fill="#8992a3"
                                        dominant-baseline="middle"
                                    >
                                        {{ label.text }}
                                    </text>
                                </svg>
                            </div>
                            <div class="chart-meta">
                                <span>{{
                                    walkForwardResult.oos_curve?.stitch_rule
                                }}</span>
                                <strong
                                    >{{ t.duplicatesRemoved }}:
                                    {{
                                        walkForwardResult.oos_curve
                                            ?.duplicates_removed ?? 0
                                    }}</strong
                                >
                            </div>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.walkForwardPaths }}</span>
                                <strong>{{
                                    walkForwardResult.paths.length
                                }}</strong>
                            </div>
                            <div class="chart-wrapper">
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line x1="48" y1="212" x2="702" y2="212" />
                                    <line x1="48" y1="18" x2="48" y2="212" />
                                    <polyline
                                        v-for="(
                                            line, index
                                        ) in walkForwardChartLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        v-for="(label, i) in wfXAxisLabels"
                                        :key="'wfx' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(label, i) in wfYAxisLabels"
                                        :key="'wfy' + i"
                                        :x="44"
                                        :y="label.y"
                                        text-anchor="end"
                                        font-size="10"
                                        fill="#8992a3"
                                        dominant-baseline="middle"
                                    >
                                        {{ label.text }}
                                    </text>
                                </svg>
                            </div>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.wfSplits }}</span>
                                <strong>{{
                                    walkForwardResult.windows?.length ?? 0
                                }}</strong>
                            </div>
                            <div class="table-scroll">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>{{ t.splitId }}</th>
                                            <th>{{ t.train }}</th>
                                            <th>{{ t.test }}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr
                                            v-for="window in walkForwardResult.windows ??
                                            []"
                                            :key="window.split_id"
                                        >
                                            <td>
                                                <strong>{{
                                                    window.split_id
                                                }}</strong>
                                            </td>
                                            <td>
                                                {{
                                                    formatDateTime(
                                                        window.train_start,
                                                    )
                                                }}
                                                -
                                                {{
                                                    formatDateTime(
                                                        window.train_end,
                                                    )
                                                }}
                                                <br />
                                                <small>{{
                                                    window.train_rows
                                                }}</small>
                                            </td>
                                            <td>
                                                {{
                                                    formatDateTime(
                                                        window.test_start,
                                                    )
                                                }}
                                                -
                                                {{
                                                    formatDateTime(
                                                        window.test_end,
                                                    )
                                                }}
                                                <br />
                                                <small>{{
                                                    window.test_rows
                                                }}</small>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div class="metrics-container">
                            <div class="metrics-section">
                                <div class="section-title">
                                    <span>{{ t.metrics }}</span>
                                    <strong>{{
                                        walkForwardResult.metadata.test_name
                                    }}</strong>
                                </div>
                                <div class="metrics-grid">
                                    <div
                                        v-for="row in walkForwardResult.report"
                                        :key="row.metric"
                                        class="metric-item"
                                    >
                                        <span class="metric-label">{{
                                            translateMetric(row.metric)
                                        }}</span>
                                        <span class="metric-value">{{
                                            row.value
                                        }}</span>
                                    </div>
                                </div>
                            </div>

                            <div class="metrics-section">
                                <div class="section-title">
                                    <span>{{ t.cvSummary }}</span>
                                    <strong>WalkForward</strong>
                                </div>
                                <div class="metrics-grid">
                                    <div
                                        v-for="row in walkForwardResult.cv_summary"
                                        :key="row.metric"
                                        class="metric-item"
                                    >
                                        <span class="metric-label">{{
                                            translateMetric(row.metric)
                                        }}</span>
                                        <span class="metric-value">{{
                                            row.value
                                        }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div
                v-if="showBacktestModal"
                class="modal-overlay"
                @click.self="showBacktestModal = false"
            >
                <div class="modal-fullscreen">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.backtestSettings }}</span>
                            <strong>{{ t.backtesting }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showBacktestModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>

                    <p v-if="backtestError" class="error-banner">
                        {{ backtestError }}
                    </p>

                    <div class="cpcv-layout">
                        <div class="form-grid">
                            <label
                                ><span>{{ t.testName }}</span
                                ><input
                                    v-model="backtestSettings.test_name"
                                    type="text"
                            /></label>
                            <label
                                ><span>{{ t.startDate }}</span
                                ><input
                                    v-model="backtestSettings.start_date"
                                    type="date"
                            /></label>
                            <label
                                ><span>{{ t.endDate }}</span
                                ><input
                                    v-model="backtestSettings.end_date"
                                    type="date"
                            /></label>
                            <label
                                ><span>{{ t.tradingStartDate }}</span
                                ><input
                                    v-model="
                                        backtestSettings.trading_start_date
                                    "
                                    type="date"
                            /></label>
                            <label>
                                <span>{{ t.interval }}</span>
                                <select v-model="backtestSettings.interval">
                                    <option value="CANDLE_INTERVAL_DAY">
                                        Day
                                    </option>
                                    <option value="CANDLE_INTERVAL_HOUR">
                                        Hour
                                    </option>
                                    <option value="CANDLE_INTERVAL_WEEK">
                                        Week
                                    </option>
                                    <option value="CANDLE_INTERVAL_MONTH">
                                        Month
                                    </option>
                                </select>
                            </label>
                            <label
                                ><span>{{ t.classCode }}</span
                                ><input
                                    v-model="backtestSettings.class_code"
                                    type="text"
                            /></label>
                            <label
                                ><span>{{ t.rebalanceFreq }}</span
                                ><input
                                    v-model="backtestSettings.rebalance_freq"
                                    type="text"
                            /></label>
                            <label>
                                <span>{{ t.rebalanceOn }}</span>
                                <select v-model="backtestSettings.rebalance_on">
                                    <option value="last">last</option>
                                    <option value="first">first</option>
                                </select>
                            </label>
                            <label
                                ><span>{{ t.initCash }}</span
                                ><input
                                    :value="
                                        formatMoneyInput(
                                            backtestSettings.init_cash,
                                        )
                                    "
                                    inputmode="numeric"
                                    type="text"
                                    @input="updateInitCash"
                            /></label>
                            <label
                                ><span>{{ t.fees }}</span
                                ><input
                                    v-model.number="backtestSettings.fees"
                                    min="0"
                                    step="0.0001"
                                    type="number"
                            /></label>
                            <label
                                ><span>{{ t.taxRate }}</span
                                ><input
                                    v-model.number="backtestSettings.tax_rate"
                                    min="0"
                                    max="100"
                                    step="0.1"
                                    type="number"
                            /></label>
                            <label
                                ><span>{{ t.rollingWindow }}</span
                                ><input
                                    v-model.number="
                                        backtestSettings.rolling_window
                                    "
                                    min="2"
                                    max="2000"
                                    type="number"
                            /></label>
                        </div>

                        <div class="cpcv-actions">
                            <button
                                class="primary-button"
                                type="button"
                                :disabled="isBacktestRunning"
                                @click="runBacktest"
                            >
                                <RefreshCw
                                    v-if="isBacktestRunning"
                                    class="spin"
                                    :size="17"
                                />
                                <PlayCircle v-else :size="17" />
                                <span>{{
                                    isBacktestRunning
                                        ? t.processing
                                        : t.runAndSave
                                }}</span>
                            </button>
                        </div>
                    </div>

                    <div class="saved-tests">
                        <div class="section-title">
                            <span>{{ t.savedTests }}</span>
                            <strong>{{ savedBacktestTests.length }}</strong>
                        </div>
                        <div v-if="isBacktestLoading" class="small-state">
                            <RefreshCw class="spin" :size="17" />
                            <span>{{ t.loading }}</span>
                        </div>
                        <div
                            v-else-if="savedBacktestTests.length === 0"
                            class="small-state"
                        >
                            <span>{{ t.noSavedTests }}</span>
                        </div>
                        <div v-else class="saved-list">
                            <article
                                v-for="test in savedBacktestTests"
                                :key="test.file_name"
                                class="saved-card"
                            >
                                <div>
                                    <strong>{{ test.test_name }}</strong>
                                    <small>{{
                                        formatDateTime(test.generated_at)
                                    }}</small>
                                </div>
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openBacktestTest(test.test_name)"
                                >
                                    <FolderOpen :size="16" />
                                    <span>{{ t.loadSaved }}</span>
                                </button>
                            </article>
                        </div>
                    </div>

                    <div v-if="backtestResult" class="cpcv-results">
                        <div class="result-strip">
                            <article>
                                <span>{{ t.source }}</span>
                                <strong>{{
                                    backtestResult.metadata.price_period.rows
                                }}</strong>
                                <small
                                    >{{
                                        formatDateTime(
                                            backtestResult.metadata.price_period
                                                .start,
                                        )
                                    }}
                                    -
                                    {{
                                        formatDateTime(
                                            backtestResult.metadata.price_period
                                                .end,
                                        )
                                    }}</small
                                >
                            </article>
                            <article>
                                <span>{{ t.backtesting }}</span>
                                <strong>{{
                                    backtestResult.metadata.trading_period.rows
                                }}</strong>
                                <small
                                    >{{
                                        formatDateTime(
                                            backtestResult.metadata
                                                .trading_period.start,
                                        )
                                    }}
                                    -
                                    {{
                                        formatDateTime(
                                            backtestResult.metadata
                                                .trading_period.end,
                                        )
                                    }}</small
                                >
                            </article>
                            <article>
                                <span>{{ t.assets }}</span>
                                <strong>{{
                                    backtestResult.metadata.asset_count
                                }}</strong>
                                <small>{{
                                    backtestResult.metadata.settings
                                        .rebalance_freq
                                }}</small>
                            </article>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.equityCurve }}</span>
                                <strong>{{
                                    backtestResult.metadata.test_name
                                }}</strong>
                            </div>
                            <svg
                                class="cpcv-chart"
                                viewBox="0 0 720 260"
                                role="img"
                            >
                                <line x1="48" y1="212" x2="702" y2="212" />
                                <line x1="48" y1="18" x2="48" y2="212" />
                                <polyline
                                    v-for="(line, index) in backtestEquityLines"
                                    :key="index"
                                    :points="line.points"
                                    :stroke="line.color"
                                    :opacity="line.opacity"
                                />
                                <text
                                    x="375"
                                    y="252"
                                    text-anchor="middle"
                                    font-size="10"
                                    fill="#8992a3"
                                >
                                    Date
                                </text>
                                <text
                                    x="12"
                                    y="118"
                                    text-anchor="middle"
                                    font-size="10"
                                    fill="#8992a3"
                                    transform="rotate(-90 12 118)"
                                >
                                    Value
                                </text>
                                <text
                                    v-for="(
                                        label, i
                                    ) in backtestEquityXAxisLabels"
                                    :key="'btx' + i"
                                    :x="label.x"
                                    y="228"
                                    text-anchor="middle"
                                    font-size="10"
                                    fill="#8992a3"
                                >
                                    {{ label.text }}
                                </text>
                                <text
                                    v-for="(
                                        label, i
                                    ) in backtestEquityYAxisLabels"
                                    :key="'bty' + i"
                                    :x="44"
                                    :y="label.y"
                                    text-anchor="end"
                                    font-size="10"
                                    fill="#8992a3"
                                    dominant-baseline="middle"
                                >
                                    {{ label.text }}
                                </text>
                            </svg>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.drawdown }}</span>
                                <strong>{{ t.rollingSharpe }}</strong>
                            </div>
                            <div class="dual-chart-grid">
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line x1="48" y1="212" x2="702" y2="212" />
                                    <line x1="48" y1="18" x2="48" y2="212" />
                                    <polyline
                                        v-for="(
                                            line, index
                                        ) in backtestDrawdownLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        x="375"
                                        y="252"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        Date
                                    </text>
                                    <text
                                        x="12"
                                        y="118"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                        transform="rotate(-90 12 118)"
                                    >
                                        Drawdown
                                    </text>
                                    <text
                                        v-for="(
                                            label, i
                                        ) in backtestDrawdownXAxisLabels"
                                        :key="'btdx' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(
                                            label, i
                                        ) in backtestDrawdownYAxisLabels"
                                        :key="'btdy' + i"
                                        :x="44"
                                        :y="label.y"
                                        text-anchor="end"
                                        font-size="10"
                                        fill="#8992a3"
                                        dominant-baseline="middle"
                                    >
                                        {{ label.text }}
                                    </text>
                                </svg>
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line x1="48" y1="212" x2="702" y2="212" />
                                    <line x1="48" y1="18" x2="48" y2="212" />
                                    <polyline
                                        v-for="(
                                            line, index
                                        ) in backtestSharpeLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        x="375"
                                        y="252"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        Date
                                    </text>
                                    <text
                                        x="12"
                                        y="118"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                        transform="rotate(-90 12 118)"
                                    >
                                        Sharpe
                                    </text>
                                    <text
                                        v-for="(
                                            label, i
                                        ) in backtestSharpeXAxisLabels"
                                        :key="'btsx' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(
                                            label, i
                                        ) in backtestSharpeYAxisLabels"
                                        :key="'btsy' + i"
                                        :x="44"
                                        :y="label.y"
                                        text-anchor="end"
                                        font-size="10"
                                        fill="#8992a3"
                                        dominant-baseline="middle"
                                    >
                                        {{ label.text }}
                                    </text>
                                </svg>
                            </div>
                        </div>

                        <div class="metrics-section">
                            <div class="section-title">
                                <span>{{ t.metrics }}</span>
                                <strong>{{ t.backtestResults }}</strong>
                            </div>
                            <div class="metrics-grid">
                                <div
                                    v-for="row in [
                                        ...backtestResult.summary,
                                        ...backtestResult.report,
                                    ]"
                                    :key="row.metric"
                                    class="metric-item"
                                >
                                    <span class="metric-label">{{
                                        translateMetric(row.metric)
                                    }}</span>
                                    <span class="metric-value">{{
                                        row.value
                                    }}</span>
                                </div>
                            </div>
                        </div>

                        <div
                            v-if="backtestResult.execution_events?.length"
                            class="chart-panel"
                        >
                            <div class="section-title">
                                <span>{{ t.executionEvents }}</span>
                                <strong>{{
                                    backtestResult.execution_events?.length ?? 0
                                }}</strong>
                            </div>
                            <div class="table-scroll">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>{{ t.time }}</th>
                                            <th>Ticker</th>
                                            <th>{{ t.reason }}</th>
                                            <th>{{ t.entryPrice }}</th>
                                            <th>{{ t.executionPrice }}</th>
                                            <th>{{ t.returnPct }}</th>
                                            <th>{{ t.weight }}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr
                                            v-for="event in (
                                                backtestResult.execution_events ??
                                                []
                                            ).slice(0, 80)"
                                            :key="`${event.time}-${event.ticker}-${event.reason}`"
                                        >
                                            <td>
                                                {{ formatDateTime(event.time) }}
                                            </td>
                                            <td>
                                                <strong>{{
                                                    event.ticker
                                                }}</strong>
                                            </td>
                                            <td>
                                                {{
                                                    formatEventReason(
                                                        event.reason,
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatPrice(
                                                        event.entry_price,
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatPrice(
                                                        event.execution_price,
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        event.return_pct,
                                                        "percent",
                                                    )
                                                }}
                                            </td>
                                            <td>
                                                {{
                                                    formatMetricValue(
                                                        event.weight,
                                                        "percent",
                                                    )
                                                }}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.rebalanceWeights }}</span>
                                <strong>{{
                                    backtestResult.rebalance_weights.length
                                }}</strong>
                            </div>
                            <div class="table-scroll">
                                <table>
                                    <tbody>
                                        <tr
                                            v-for="record in backtestResult.rebalance_weights.slice(
                                                0,
                                                40,
                                            )"
                                            :key="record.time"
                                        >
                                            <th>
                                                {{
                                                    formatDateTime(record.time)
                                                }}
                                            </th>
                                            <td>
                                                <strong
                                                    >{{ t.totalWeight }}:
                                                    {{
                                                        formatWeight(
                                                            record.total_weight,
                                                        )
                                                    }}
                                                    /
                                                    {{
                                                        record.asset_count
                                                    }}</strong
                                                >
                                                <br />
                                                <span
                                                    v-for="item in record.weights.slice(
                                                        0,
                                                        12,
                                                    )"
                                                    :key="`${record.time}-${item.ticker}`"
                                                    class="weight-pill"
                                                >
                                                    {{ item.ticker }}
                                                    {{
                                                        formatWeight(
                                                            item.weight,
                                                        )
                                                    }}
                                                </span>
                                                <button
                                                    class="icon-text-button compact-action"
                                                    type="button"
                                                    @click="
                                                        openWeightsModal(record)
                                                    "
                                                >
                                                    {{ t.showAll }} (+{{
                                                        record.weights.length -
                                                        12
                                                    }}
                                                    {{ t.hiddenAssets }})
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div
                v-if="showWeightsModal"
                class="modal-overlay"
                @click.self="showWeightsModal = false"
            >
                <div class="modal-fullscreen weights-modal">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.portfolioComposition }}</span>
                            <strong>{{
                                formatDateTime(selectedWeightRecord?.time)
                            }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showWeightsModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>

                    <div v-if="selectedWeightRecord" class="weights-layout">
                        <section class="pie-panel">
                            <div class="section-title">
                                <span>{{ t.totalWeight }}</span>
                                <strong
                                    >{{
                                        formatWeight(
                                            selectedWeightRecord.total_weight,
                                        )
                                    }}
                                    /
                                    {{
                                        selectedWeightRecord.asset_count
                                    }}</strong
                                >
                            </div>
                            <svg
                                class="pie-chart"
                                viewBox="0 0 224 224"
                                role="img"
                            >
                                <path
                                    v-for="segment in pieSegments"
                                    :key="segment.ticker"
                                    :d="segment.d"
                                    :fill="segment.color"
                                    stroke="#11141b"
                                    stroke-width="0.8"
                                />
                                <text
                                    v-for="segment in pieSegments.filter(
                                        (item) => item.showLabel,
                                    )"
                                    :key="`${segment.ticker}-label`"
                                    :x="segment.labelX"
                                    :y="segment.labelY"
                                    fill="#f4f6fb"
                                    font-size="5"
                                    text-anchor="middle"
                                    dominant-baseline="middle"
                                >
                                    {{ segment.ticker }}
                                    {{ formatWeight(segment.weight) }}
                                </text>
                            </svg>

                            <div class="section-title sector-title">
                                <span>{{ t.sectorAllocation }}</span>
                                <strong>{{ sectorRows.length }}</strong>
                            </div>
                            <svg
                                class="pie-chart"
                                viewBox="0 0 224 224"
                                role="img"
                            >
                                <path
                                    v-for="segment in sectorPieSegments"
                                    :key="segment.sector"
                                    :d="segment.d"
                                    :fill="segment.color"
                                    stroke="#11141b"
                                    stroke-width="0.8"
                                />
                                <text
                                    v-for="segment in sectorPieSegments.filter(
                                        (item) => item.showLabel,
                                    )"
                                    :key="`${segment.sector}-label`"
                                    :x="segment.labelX"
                                    :y="segment.labelY"
                                    fill="#f4f6fb"
                                    font-size="5"
                                    text-anchor="middle"
                                    dominant-baseline="middle"
                                >
                                    {{ segment.sector }}
                                    {{ formatWeight(segment.weight) }}
                                </text>
                            </svg>
                        </section>

                        <section class="weights-table-panel">
                            <div class="table-scroll full-height-table">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Ticker</th>
                                            <th>{{ t.sector }}</th>
                                            <th>Weight</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr
                                            v-for="item in selectedWeightRecord.weights"
                                            :key="item.ticker"
                                        >
                                            <td>
                                                <span class="legend-ticker">
                                                    <span
                                                        class="legend-dot"
                                                        :style="{
                                                            backgroundColor:
                                                                colorForWeightItem(
                                                                    item.ticker,
                                                                ),
                                                        }"
                                                    ></span>
                                                    <strong>{{
                                                        item.ticker
                                                    }}</strong>
                                                </span>
                                            </td>
                                            <td>
                                                {{
                                                    sectorForTicker(item.ticker)
                                                }}
                                            </td>
                                            <td>
                                                {{ formatWeight(item.weight) }}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>

                            <div class="section-title sector-table-title">
                                <span>{{ t.sectorAllocation }}</span>
                                <strong>{{ sectorRows.length }}</strong>
                            </div>
                            <div class="table-scroll">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>{{ t.sector }}</th>
                                            <th>{{ t.assets }}</th>
                                            <th>{{ t.weight }}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr
                                            v-for="item in sectorRows"
                                            :key="item.sector"
                                        >
                                            <td>
                                                <span class="legend-ticker">
                                                    <span
                                                        class="legend-dot"
                                                        :style="{
                                                            backgroundColor:
                                                                colorForSector(
                                                                    item.sector,
                                                                ),
                                                        }"
                                                    ></span>
                                                    <strong>{{
                                                        item.sector
                                                    }}</strong>
                                                </span>
                                            </td>
                                            <td>{{ item.asset_count }}</td>
                                            <td>
                                                {{ formatWeight(item.weight) }}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    </div>
                </div>
            </div>

            <div
                v-if="showAssetsModal"
                class="modal-overlay"
                @click.self="showAssetsModal = false"
            >
                <div class="modal-fullscreen" style="max-width: 800px">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.assets }}</span>
                            <strong>{{ activeAssetCount }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showAssetsModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>
                    <div class="table-scroll" style="max-height: 70vh">
                        <table>
                            <thead>
                                <tr>
                                    <th>FIGI</th>
                                    <th>Ticker</th>
                                    <th>Name</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr
                                    v-for="asset in activeAssets"
                                    :key="asset.figi"
                                >
                                    <td>
                                        <code>{{ asset.figi }}</code>
                                    </td>
                                    <td>
                                        <strong>{{ asset.ticker }}</strong>
                                    </td>
                                    <td>{{ asset.name }}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </main>
    </div>
</template>
