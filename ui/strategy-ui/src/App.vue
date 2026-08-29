<script setup lang="ts">
import {
    BarChart3,
    Boxes,
    BrainCircuit,
    ChevronDown,
    CircleHelp,
    DatabaseZap,
    FileChartColumn,
    FolderOpen,
    GitBranch,
    Globe2,
    Home,
    Layers3,
    PlayCircle,
    RefreshCw,
    Scale,
    SearchCheck,
    ShieldAlert,
    Trophy,
    X,
} from "lucide-vue-next";
import { computed, defineAsyncComponent, onMounted, ref, watch } from "vue";
import {
    getBacktestTest,
    getBacktestRun,
    getCpcvTest,
    getLatestStrategyComparison,
    getModelDetail,
    getRegistry,
    getRiskModelTest,
    getTradingStrategyBacktestTest,
    getTradingStrategyBacktestRun,
    getTradingStrategyDetail,
    getWalkForwardTest,
    listAvailableRiskModels,
    listBacktestTests,
    listCpcvTests,
    listRiskModelTests,
    listTradingStrategies,
    listTradingStrategyBacktestTests,
    listWalkForwardTests,
    startBacktestRun,
    runCpcvTest,
    runRiskModelTest,
    setTradingStrategyProdReady,
    startTradingStrategyBacktestRun,
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
    RiskModelDefinition,
    RiskModelResult,
    RiskModelSavedTest,
    RiskModelSettings,
    StrategyComparisonResult,
    TradingStrategyProductionState,
    WalkForwardResult,
    WalkForwardSavedTest,
    WalkForwardSettings,
} from "./types";

const BacktestPnlReportModal = defineAsyncComponent(
    () => import("./components/BacktestPnlReportModal.vue"),
);

const savedLocale = localStorage.getItem(
    "its-strategy-locale",
) as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");
const t = computed(() => messages[locale.value]);
const docsHref = computed(() => `/docs/?lang=${locale.value}`);

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
const isRiskModelRunning = ref(false);
const isRiskModelLoading = ref(false);
const isComparisonLoading = ref(false);
const error = ref("");
const cpcvError = ref("");
const walkForwardError = ref("");
const backtestError = ref("");
const riskModelError = ref("");
const comparisonError = ref("");
const prodStateError = ref("");
const isProdStateUpdating = ref(false);
const prodCommentDraft = ref("");
const savedCpcvTests = ref<CpcvSavedTest[]>([]);
const savedWalkForwardTests = ref<WalkForwardSavedTest[]>([]);
const savedBacktestTests = ref<BacktestSavedTest[]>([]);
const savedRiskModelTests = ref<RiskModelSavedTest[]>([]);
const availableRiskModels = ref<RiskModelDefinition[]>([]);
const cpcvResult = ref<CpcvResult | null>(null);
const walkForwardResult = ref<WalkForwardResult | null>(null);
const backtestResult = ref<BacktestResult | null>(null);
const rebalancePage = ref(1);
const rebalancePageSize = 40;
const indexedRebalanceWeights = computed(() => {
    const records = backtestResult.value?.rebalance_weights ?? [];
    return records
        .map((record, index) => ({ record, number: index + 1 }))
        .reverse();
});
const rebalancePageCount = computed(() =>
    Math.max(1, Math.ceil(indexedRebalanceWeights.value.length / rebalancePageSize)),
);
const paginatedRebalanceWeights = computed(() => {
    const start = (rebalancePage.value - 1) * rebalancePageSize;
    return indexedRebalanceWeights.value.slice(start, start + rebalancePageSize);
});
watch(backtestResult, () => {
    rebalancePage.value = 1;
    showBacktestPnlModal.value = false;
});
const riskModelResult = ref<RiskModelResult | null>(null);
const comparisonResult = ref<StrategyComparisonResult | null>(null);
const cpcvSettings = ref<CpcvSettings>(defaultCpcvSettings());
const walkForwardSettings = ref<WalkForwardSettings>(
    defaultWalkForwardSettings(),
);
const backtestSettings = ref<BacktestSettings>(defaultBacktestSettings());
const rebalanceFrequencyUnits = [
    "D",
    "B",
    "W",
    "MS",
    "ME",
    "QS",
    "QE",
    "YS",
    "YE",
] as const;
const rebalanceFrequencyParts = computed(() => {
    const match = backtestSettings.value.rebalance_freq.match(/^(\d+)([A-Z]+)$/i);
    return {
        amount: match ? Number(match[1]) : 1,
        unit: match?.[2]?.toUpperCase() ?? "ME",
    };
});
const rebalanceFrequencyAmount = computed({
    get: () => rebalanceFrequencyParts.value.amount,
    set: (value: number) => {
        const amount = Number.isFinite(value) ? Math.max(1, Math.trunc(value)) : 1;
        backtestSettings.value.rebalance_freq = `${amount}${rebalanceFrequencyParts.value.unit}`;
    },
});
const rebalanceFrequencyUnit = computed({
    get: () => rebalanceFrequencyParts.value.unit,
    set: (value: string) => {
        backtestSettings.value.rebalance_freq = `${rebalanceFrequencyParts.value.amount}${value}`;
    },
});
const riskModelSettings = ref<RiskModelSettings>(defaultRiskModelSettings());
const activeRiskModelId = ref("monte_carlo");
const activeFieldTooltip = ref("");
const showCpcvModal = ref(false);
const showWalkForwardModal = ref(false);
const showBacktestModal = ref(false);
const showBacktestPnlModal = ref(false);
const showRiskModelModal = ref(false);
const showRiskModelMenu = ref(false);
const showComparisonModal = ref(false);
const showAssetsModal = ref(false);
const showWeightsModal = ref(false);
const activeAssetsSource = ref<"cpcv" | "walkForward" | "riskModel">("cpcv");
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
const riskHistoricalXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const riskHistoricalYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const riskDistributionXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const riskDistributionYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const riskCdfXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const riskCdfYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const riskPathsXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const riskPathsYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
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
const fallbackRiskModels: RiskModelDefinition[] = [
    {
        id: "monte_carlo",
        title: "Monte Carlo",
        metric: "VaR/CVaR",
        engine: "monte_carlo",
    },
    {
        id: "qae",
        title: "QAE (Quantum Amplitude Estimation)",
        metric: "VaR/CVaR",
        engine: "qae_style_discrete",
    },
];
const riskModelOptions = computed(() =>
    availableRiskModels.value.length
        ? availableRiskModels.value
        : fallbackRiskModels,
);
const activeRiskModel = computed(
    () =>
        riskModelOptions.value.find(
            (item) => item.id === activeRiskModelId.value,
        ) ?? fallbackRiskModels[0],
);
const isQaeRiskModel = computed(() => activeRiskModel.value.engine.includes("qae"));
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
const riskHistoricalLines = computed(() =>
    buildChartLines(
        curveToChartResult(riskModelResult.value?.historical_portfolio_curve),
        riskHistoricalXAxisLabels,
        riskHistoricalYAxisLabels,
        "money",
        ["#aee9d1"],
    ),
);
const riskDistributionBars = computed(() =>
    buildHistogramBars(
        riskModelResult.value?.loss_distribution,
        riskDistributionXAxisLabels,
        riskDistributionYAxisLabels,
    ),
);
const riskCdfLines = computed(() =>
    buildNumericChartLines(
        riskModelResult.value?.cumulative_distribution.points ?? [],
        riskCdfXAxisLabels,
        riskCdfYAxisLabels,
        "money",
        "percent",
        ["#66d9ef"],
    ),
);
const riskScenarioPathLines = computed(() =>
    buildNumericMultiPathLines(
        riskModelResult.value?.simulated_paths?.paths ?? [],
        riskPathsXAxisLabels,
        riskPathsYAxisLabels,
        "number",
        "money",
    ),
);

function toggleFieldTooltip(key: string) {
    activeFieldTooltip.value = activeFieldTooltip.value === key ? "" : key;
}

function tooltipText(value: string | string[]) {
    return Array.isArray(value) ? value.join(" ") : value;
}
const riskCvarSummaryValue = computed(() => {
    const rows = riskModelResult.value?.summary ?? [];
    return (
        rows.find((row) => row.metric === "CVaR")?.value ??
        rows.find((row) => row.metric === "CVaR Reference")?.value ??
        "—"
    );
});
const activeAssets = computed(() =>
    activeAssetsSource.value === "walkForward"
        ? (walkForwardResult.value?.metadata.assets ?? [])
        : activeAssetsSource.value === "riskModel"
          ? (riskModelResult.value?.metadata.assets ?? [])
          : (cpcvResult.value?.metadata.assets ?? []),
);
const activeAssetCount = computed(() =>
    activeAssetsSource.value === "walkForward"
        ? (walkForwardResult.value?.metadata.asset_count ?? 0)
        : activeAssetsSource.value === "riskModel"
          ? (riskModelResult.value?.metadata.asset_count ?? 0)
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
const currentProdState = computed<TradingStrategyProductionState | null>(() => {
    if (!isTradingStrategyTab.value || !modelDetail.value) return null;
    return (
        modelDetail.value.production_state ?? {
            strategy_name: modelDetail.value.name,
            is_prod_ready: false,
            comment: null,
            updated_by_user_id: null,
            updated_at: null,
        }
    );
});

watch(locale, (value) => localStorage.setItem("its-strategy-locale", value));
watch(activeRiskModelId, async (value) => {
    if (!showRiskModelModal.value || !selectedModelName.value) return;
    riskModelResult.value = null;
    riskModelError.value = "";
    await loadSavedRiskModelTests(selectedModelName.value, value);
});

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
        await loadTradingStrategyItems();
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

async function loadTradingStrategyItems() {
    const response = await listTradingStrategies();
    const tradingGroup = registry.value?.groups.find(
        (group) => group.id === "trading_strategy_model",
    );
    if (!tradingGroup) return;
    tradingGroup.items = response.items;
    tradingGroup.count = response.items.length;
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
        riskModelResult.value = null;
        cpcvError.value = "";
        walkForwardError.value = "";
        backtestError.value = "";
        riskModelError.value = "";
        comparisonError.value = "";
        await loadAvailableRiskModels(modelName);
        await loadSavedCpcvTests(modelName);
        await loadSavedWalkForwardTests(modelName);
        await loadSavedBacktestTests(modelName);
        await loadSavedRiskModelTests(modelName, activeRiskModelId.value);
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
        prodCommentDraft.value = modelDetail.value.production_state?.comment ?? "";
        prodStateError.value = "";
        cpcvResult.value = null;
        walkForwardResult.value = null;
        backtestResult.value = null;
        riskModelResult.value = null;
        cpcvError.value = "";
        walkForwardError.value = "";
        backtestError.value = "";
        riskModelError.value = "";
        comparisonError.value = "";
        savedCpcvTests.value = [];
        savedWalkForwardTests.value = [];
        savedRiskModelTests.value = [];
        availableRiskModels.value = [];
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

async function updateProdReady(isProdReady: boolean) {
    if (!isTradingStrategyTab.value || !selectedModelName.value) return;
    isProdStateUpdating.value = true;
    prodStateError.value = "";
    try {
        const response = await setTradingStrategyProdReady(selectedModelName.value, {
            is_prod_ready: isProdReady,
            comment: prodCommentDraft.value.trim() || null,
        });
        if (modelDetail.value) {
            modelDetail.value.production_state = response.item;
        }
        await loadTradingStrategyItems();
    } catch (err) {
        prodStateError.value = formatError(err);
    } finally {
        isProdStateUpdating.value = false;
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

function formatError(err: unknown): string {
    if (err instanceof Error) return err.message;
    if (typeof err === "string") return err;
    if (err && typeof err === "object") {
        try {
            return JSON.stringify(err);
        } catch {
            return "Не удалось прочитать детали ошибки";
        }
    }
    return String(err);
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
        let run = isTradingStrategyTab.value
            ? await startTradingStrategyBacktestRun(
                  selectedModelName.value,
                  backendBacktestSettings(),
              )
            : await startBacktestRun(
                  selectedModelName.value,
                  backendBacktestSettings(),
              );
        while (run.status === "queued" || run.status === "running") {
            await new Promise((resolve) => window.setTimeout(resolve, 1_000));
            run = isTradingStrategyTab.value
                ? await getTradingStrategyBacktestRun(
                      selectedModelName.value,
                      run.run_id,
                  )
                : await getBacktestRun(selectedModelName.value, run.run_id);
        }
        if (run.status === "failed") {
            throw new Error(run.error ?? "Backtest failed");
        }
        if (!run.result) {
            throw new Error("Backtest completed without a result");
        }
        backtestResult.value = run.result;
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

async function loadAvailableRiskModels(modelName = selectedModelName.value) {
    if (!modelName || !isCoreStrategyTab.value) return;
    try {
        availableRiskModels.value = (await listAvailableRiskModels(modelName)).items;
        if (
            availableRiskModels.value.length &&
            !availableRiskModels.value.some(
                (item) => item.id === activeRiskModelId.value,
            )
        ) {
            activeRiskModelId.value = availableRiskModels.value[0].id;
        }
    } catch (err) {
        riskModelError.value = formatError(err);
    }
}

async function openRiskModel(riskModel: string) {
    if (!selectedModelName.value) return;
    activeRiskModelId.value = riskModel;
    showRiskModelMenu.value = false;
    showRiskModelModal.value = true;
    riskModelResult.value = null;
    riskModelError.value = "";
    await loadSavedRiskModelTests(selectedModelName.value, riskModel);
}

async function loadSavedRiskModelTests(
    modelName = selectedModelName.value,
    riskModel = activeRiskModelId.value,
) {
    if (!modelName || !riskModel || !isCoreStrategyTab.value) return;
    isRiskModelLoading.value = true;
    try {
        savedRiskModelTests.value = (
            await listRiskModelTests(modelName, riskModel)
        ).items;
    } catch (err) {
        riskModelError.value = formatError(err);
    } finally {
        isRiskModelLoading.value = false;
    }
}

async function openRiskModelTest(testName: string) {
    if (!selectedModelName.value) return;
    isRiskModelLoading.value = true;
    riskModelError.value = "";
    try {
        riskModelResult.value = await getRiskModelTest(
            selectedModelName.value,
            activeRiskModelId.value,
            testName,
        );
        riskModelSettings.value = {
            ...riskModelSettings.value,
            ...riskModelResult.value.metadata.settings,
        };
    } catch (err) {
        riskModelError.value = formatError(err);
    } finally {
        isRiskModelLoading.value = false;
    }
}

async function runRiskModel() {
    if (!selectedModelName.value) return;
    isRiskModelRunning.value = true;
    riskModelError.value = "";
    try {
        riskModelResult.value = await runRiskModelTest(
            selectedModelName.value,
            activeRiskModelId.value,
            riskModelSettings.value,
        );
        await loadSavedRiskModelTests(
            selectedModelName.value,
            activeRiskModelId.value,
        );
    } catch (err) {
        riskModelError.value = formatError(err);
    } finally {
        isRiskModelRunning.value = false;
    }
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

function defaultRiskModelSettings(): RiskModelSettings {
    const end = new Date();
    const start = new Date(end);
    start.setFullYear(start.getFullYear() - 3);
    return {
        test_name: "baseline",
        start_date: toDateInput(start),
        end_date: toDateInput(end),
        interval: "CANDLE_INTERVAL_DAY",
        class_code: "TQBR",
        test_size: 0.33,
        portfolio_value: 1_000_000,
        confidence_level: 0.95,
        horizon_days: 1,
        n_simulations: 50_000,
        simulation_method: "historical_bootstrap",
        random_state: 42,
        n_buckets: 64,
        qae_iterations: 12,
        qae_shots: 2_000,
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

function updateRiskPortfolioValue(event: Event) {
    const raw = (event.target as HTMLInputElement).value.replace(/\s/g, "");
    const value = Number(raw);
    if (Number.isFinite(value)) {
        riskModelSettings.value.portfolio_value = value;
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

function openAssetsModal(source: "cpcv" | "walkForward" | "riskModel") {
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

function buildHistogramBars(
    distribution: RiskModelResult["loss_distribution"] | undefined | null,
    xLabelsRef: typeof riskDistributionXAxisLabels,
    yLabelsRef: typeof riskDistributionYAxisLabels,
) {
    const bins = distribution?.bins ?? [];
    if (!bins.length) {
        xLabelsRef.value = [];
        yLabelsRef.value = [];
        return [];
    }
    const width = 720;
    const height = 260;
    const pad = 48;
    const losses = bins.map((bin) => bin.loss);
    const probabilities = bins.map((bin) => bin.probability);
    const minLoss = Math.min(...losses);
    const maxLoss = Math.max(...losses);
    const lossRange = maxLoss - minLoss || 1;
    const maxProbability = Math.max(...probabilities) || 1;
    const plotWidth = width - pad * 2;
    const plotHeight = height - pad * 2;
    const barWidth = Math.max(2, plotWidth / bins.length - 1);

    xLabelsRef.value = buildNumericAxisLabels(
        minLoss,
        maxLoss,
        "money",
        "x",
        width,
        height,
        pad,
    ) as Array<{ x: number; text: string }>;
    yLabelsRef.value = buildNumericAxisLabels(
        0,
        maxProbability,
        "percent",
        "y",
        width,
        height,
        pad,
    ) as Array<{ y: number; text: string }>;

    return bins.map((bin) => {
        const x = pad + ((bin.loss - minLoss) / lossRange) * plotWidth;
        const barHeight = (bin.probability / maxProbability) * plotHeight;
        return {
            x: x - barWidth / 2,
            y: height - pad - barHeight,
            width: barWidth,
            height: barHeight,
            color: bin.is_tail ? "#ff6b8a" : "#66d9ef",
            opacity: bin.is_tail ? 0.86 : 0.58,
        };
    });
}

function buildNumericChartLines(
    points: Array<{ x: number; y: number }>,
    xLabelsRef: typeof riskCdfXAxisLabels,
    yLabelsRef: typeof riskCdfYAxisLabels,
    xFormat: "percent" | "money" | "number" = "number",
    yFormat: "percent" | "money" | "number" = "number",
    palette = ["#66d9ef"],
) {
    if (!points.length) {
        xLabelsRef.value = [];
        yLabelsRef.value = [];
        return [];
    }
    const width = 720;
    const height = 260;
    const pad = 48;
    const xValues = points.map((point) => point.x);
    const yValues = points.map((point) => point.y);
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    const xRange = maxX - minX || 1;
    const yRange = maxY - minY || 1;

    xLabelsRef.value = buildNumericAxisLabels(
        minX,
        maxX,
        xFormat,
        "x",
        width,
        height,
        pad,
    ) as Array<{ x: number; text: string }>;
    yLabelsRef.value = buildNumericAxisLabels(
        minY,
        maxY,
        yFormat,
        "y",
        width,
        height,
        pad,
    ) as Array<{ y: number; text: string }>;

    return [
        {
            points: points
                .map((point) => {
                    const x = pad + ((point.x - minX) / xRange) * (width - pad * 2);
                    const y =
                        height -
                        pad -
                        ((point.y - minY) / yRange) * (height - pad * 2);
                    return `${x.toFixed(2)},${y.toFixed(2)}`;
                })
                .join(" "),
            color: palette[0],
            opacity: 0.9,
        },
    ];
}

function buildNumericMultiPathLines(
    paths: Array<{
        points: Array<{ x: number; y: number }>;
    }>,
    xLabelsRef: typeof riskPathsXAxisLabels,
    yLabelsRef: typeof riskPathsYAxisLabels,
    xFormat: "percent" | "money" | "number" = "number",
    yFormat: "percent" | "money" | "number" = "number",
) {
    const drawablePaths = paths.filter((path) => path.points.length > 1);
    if (!drawablePaths.length) {
        xLabelsRef.value = [];
        yLabelsRef.value = [];
        return [];
    }
    const width = 720;
    const height = 260;
    const pad = 48;
    const allPoints = drawablePaths.flatMap((path) => path.points);
    const xValues = allPoints.map((point) => point.x);
    const yValues = allPoints.map((point) => point.y);
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    const xRange = maxX - minX || 1;
    const yRange = maxY - minY || 1;

    xLabelsRef.value = buildNumericAxisLabels(
        minX,
        maxX,
        xFormat,
        "x",
        width,
        height,
        pad,
    ) as Array<{ x: number; text: string }>;
    yLabelsRef.value = buildNumericAxisLabels(
        minY,
        maxY,
        yFormat,
        "y",
        width,
        height,
        pad,
    ) as Array<{ y: number; text: string }>;

    return drawablePaths.map((path, index) => ({
        points: path.points
            .map((point) => {
                const x = pad + ((point.x - minX) / xRange) * (width - pad * 2);
                const y =
                    height -
                    pad -
                    ((point.y - minY) / yRange) * (height - pad * 2);
                return `${x.toFixed(2)},${y.toFixed(2)}`;
            })
            .join(" "),
        color: index % 5 === 0 ? "#ffcc66" : "#66d9ef",
        opacity: index % 5 === 0 ? 0.45 : 0.18,
    }));
}

function buildNumericAxisLabels(
    min: number,
    max: number,
    mode: "percent" | "money" | "number",
    axis: "x" | "y",
    width: number,
    height: number,
    pad: number,
) {
    const range = max - min || 1;
    const labels = [];
    const tickCount = 5;
    for (let i = 0; i <= tickCount; i++) {
        const value = min + (range * i) / tickCount;
        if (axis === "x") {
            labels.push({
                x: pad + ((value - min) / range) * (width - pad * 2),
                text: formatAxisValue(value, mode),
            });
        } else {
            labels.push({
                y:
                    height -
                    pad -
                    ((value - min) / range) * (height - pad * 2),
                text: formatAxisValue(value, mode),
            });
        }
    }
    return labels;
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
                <a
                    class="icon-button"
                    href="/launchpad/"
                    title="Launchpad"
                    aria-label="Launchpad"
                >
                    <Home :size="18" />
                </a>
                <a
                    class="icon-button"
                    :href="docsHref"
                    target="_blank"
                    rel="noreferrer"
                    :title="t.documentation"
                    :aria-label="t.documentation"
                >
                    <CircleHelp :size="18" />
                </a>
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
                                    <span>{{
                                        item.production_state?.is_prod_ready
                                            ? "prod-ready"
                                            : item.kind
                                    }}</span>
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

                            <section
                                v-if="isTradingStrategyTab && currentProdState"
                                class="detail-section"
                            >
                                <span>{{ t.productionState }}</span>
                                <div class="prod-ready-block">
                                    <strong>
                                        {{
                                            currentProdState.is_prod_ready
                                                ? t.prodReadyYes
                                                : t.prodReadyNo
                                        }}
                                    </strong>
                                    <textarea
                                        v-model="prodCommentDraft"
                                        rows="3"
                                        :placeholder="t.prodCommentPlaceholder"
                                    />
                                    <div class="prod-ready-actions">
                                        <button
                                            class="report-btn"
                                            type="button"
                                            :disabled="isProdStateUpdating"
                                            @click="updateProdReady(true)"
                                        >
                                            {{ t.markProdReady }}
                                        </button>
                                        <button
                                            class="report-btn"
                                            type="button"
                                            :disabled="isProdStateUpdating"
                                            @click="updateProdReady(false)"
                                        >
                                            {{ t.unmarkProdReady }}
                                        </button>
                                    </div>
                                    <small v-if="currentProdState.updated_at">
                                        {{
                                            `${t.updatedAt}: ${formatDateTime(currentProdState.updated_at)}`
                                        }}
                                    </small>
                                    <p v-if="prodStateError" class="error-banner">
                                        {{ prodStateError }}
                                    </p>
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
                                    <div
                                        v-if="isCoreStrategyTab"
                                        class="report-dropdown"
                                    >
                                        <button
                                            class="report-btn dropdown-trigger"
                                            type="button"
                                            @click="
                                                showRiskModelMenu =
                                                    !showRiskModelMenu
                                            "
                                        >
                                            <ShieldAlert :size="17" />
                                            <div>
                                                <strong>{{
                                                    t.riskModels
                                                }}</strong>
                                                <small>{{
                                                    t.riskModelSubtitle
                                                }}</small>
                                            </div>
                                            <ChevronDown :size="16" />
                                        </button>
                                        <div
                                            v-if="showRiskModelMenu"
                                            class="report-menu"
                                        >
                                            <button
                                                v-for="option in riskModelOptions"
                                                :key="option.id"
                                                type="button"
                                                @click="openRiskModel(option.id)"
                                            >
                                                <strong>{{
                                                    option.title
                                                }}</strong>
                                                <small>{{
                                                    option.engine
                                                }}</small>
                                            </button>
                                        </div>
                                    </div>
                                    <article
                                        v-for="report in modelDetail.future_reports.filter(
                                            (item) =>
                                                ![
                                                    'cpcv',
                                                    'walk_forward',
                                                    'backtesting',
                                                    'risk_models',
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
                v-if="showRiskModelModal"
                class="modal-overlay"
                @click.self="showRiskModelModal = false"
            >
                <div class="modal-fullscreen">
                    <div class="modal-header">
                        <div class="section-title">
                            <span>{{ t.riskModelSettings }}</span>
                            <strong>{{ activeRiskModel.title }}</strong>
                        </div>
                        <button
                            class="icon-button"
                            type="button"
                            @click="showRiskModelModal = false"
                        >
                            <X :size="18" />
                        </button>
                    </div>

                    <p v-if="riskModelError" class="error-banner">
                        {{ riskModelError }}
                    </p>

                    <div class="cpcv-layout">
                        <div class="form-grid">
                            <label>
                                <span>{{ t.testName }}</span>
                                <input
                                    v-model="riskModelSettings.test_name"
                                    type="text"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.riskModel }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('riskModel')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'riskModel'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.riskModelTooltip) }}
                                </span>
                                <select v-model="activeRiskModelId">
                                    <option
                                        v-for="option in riskModelOptions"
                                        :key="option.id"
                                        :value="option.id"
                                    >
                                        {{ option.title }}
                                    </option>
                                </select>
                            </label>
                            <label>
                                <span>{{ t.startDate }}</span>
                                <input
                                    v-model="riskModelSettings.start_date"
                                    type="date"
                                />
                            </label>
                            <label>
                                <span>{{ t.endDate }}</span>
                                <input
                                    v-model="riskModelSettings.end_date"
                                    type="date"
                                />
                            </label>
                            <label>
                                <span>{{ t.interval }}</span>
                                <select v-model="riskModelSettings.interval">
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
                                    v-model="riskModelSettings.class_code"
                                    type="text"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.testSize }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('testSize')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'testSize'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.testSizeTooltip) }}
                                </span>
                                <input
                                    v-model.number="riskModelSettings.test_size"
                                    min="0.05"
                                    max="0.80"
                                    step="0.01"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.portfolioValue }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="
                                            toggleFieldTooltip('portfolioValue')
                                        "
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'portfolioValue'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.portfolioValueTooltip) }}
                                </span>
                                <input
                                    :value="
                                        formatMoneyInput(
                                            riskModelSettings.portfolio_value,
                                        )
                                    "
                                    inputmode="numeric"
                                    type="text"
                                    @input="updateRiskPortfolioValue"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.confidenceLevel }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="
                                            toggleFieldTooltip('confidenceLevel')
                                        "
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="
                                        activeFieldTooltip === 'confidenceLevel'
                                    "
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.confidenceLevelTooltip) }}
                                </span>
                                <input
                                    v-model.number="
                                        riskModelSettings.confidence_level
                                    "
                                    min="0.5"
                                    max="0.999"
                                    step="0.001"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.horizonDays }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('horizonDays')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'horizonDays'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.horizonDaysTooltip) }}
                                </span>
                                <input
                                    v-model.number="
                                        riskModelSettings.horizon_days
                                    "
                                    min="1"
                                    max="252"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.nSimulations }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('nSimulations')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'nSimulations'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.nSimulationsTooltip) }}
                                </span>
                                <input
                                    v-model.number="
                                        riskModelSettings.n_simulations
                                    "
                                    min="100"
                                    max="1000000"
                                    step="1000"
                                    type="number"
                                />
                            </label>
                            <label>
                                <span class="field-label">
                                    {{ t.simulationMethod }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="
                                            toggleFieldTooltip('simulationMethod')
                                        "
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="
                                        activeFieldTooltip === 'simulationMethod'
                                    "
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.simulationMethodTooltip) }}
                                </span>
                                <select
                                    v-model="
                                        riskModelSettings.simulation_method
                                    "
                                >
                                    <option value="historical_bootstrap">
                                        {{ t.historicalBootstrap }}
                                    </option>
                                    <option value="multivariate_normal">
                                        {{ t.multivariateNormal }}
                                    </option>
                                </select>
                            </label>
                            <label>
                                <span class="field-label">
                                    Random state
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('randomState')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'randomState'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.randomStateTooltip) }}
                                </span>
                                <input
                                    v-model.number="
                                        riskModelSettings.random_state
                                    "
                                    type="number"
                                />
                            </label>
                            <label v-if="isQaeRiskModel">
                                <span class="field-label">
                                    {{ t.nBuckets }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('nBuckets')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'nBuckets'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.nBucketsTooltip) }}
                                </span>
                                <select v-model.number="riskModelSettings.n_buckets">
                                    <option :value="32">32</option>
                                    <option :value="64">64</option>
                                    <option :value="128">128</option>
                                    <option :value="256">256</option>
                                    <option :value="512">512</option>
                                    <option :value="1024">1024</option>
                                </select>
                            </label>
                            <label v-if="isQaeRiskModel">
                                <span class="field-label">
                                    {{ t.qaeIterations }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="
                                            toggleFieldTooltip('qaeIterations')
                                        "
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'qaeIterations'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.qaeIterationsTooltip) }}
                                </span>
                                <input
                                    v-model.number="
                                        riskModelSettings.qae_iterations
                                    "
                                    min="1"
                                    max="64"
                                    type="number"
                                />
                            </label>
                            <label v-if="isQaeRiskModel">
                                <span class="field-label">
                                    {{ t.qaeShots }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('qaeShots')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <span
                                    v-if="activeFieldTooltip === 'qaeShots'"
                                    class="field-tooltip"
                                >
                                    {{ tooltipText(t.qaeShotsTooltip) }}
                                </span>
                                <input
                                    v-model.number="riskModelSettings.qae_shots"
                                    min="100"
                                    max="1000000"
                                    step="100"
                                    type="number"
                                />
                            </label>
                        </div>

                        <div class="cpcv-actions">
                            <button
                                class="primary-button"
                                type="button"
                                :disabled="isRiskModelRunning"
                                @click="runRiskModel"
                            >
                                <RefreshCw
                                    v-if="isRiskModelRunning"
                                    class="spin"
                                    :size="17"
                                />
                                <PlayCircle v-else :size="17" />
                                <span>{{
                                    isRiskModelRunning
                                        ? t.processing
                                        : t.runAndSave
                                }}</span>
                            </button>
                        </div>
                    </div>

                    <div class="saved-tests">
                        <div class="section-title">
                            <span>{{ t.savedTests }}</span>
                            <strong>{{ savedRiskModelTests.length }}</strong>
                        </div>
                        <div v-if="isRiskModelLoading" class="small-state">
                            <RefreshCw class="spin" :size="17" />
                            <span>{{ t.loading }}</span>
                        </div>
                        <div
                            v-else-if="savedRiskModelTests.length === 0"
                            class="small-state"
                        >
                            <span>{{ t.noSavedTests }}</span>
                        </div>
                        <div v-else class="saved-list">
                            <article
                                v-for="test in savedRiskModelTests"
                                :key="test.file_name"
                                class="saved-card"
                            >
                                <div>
                                    <strong>{{ test.test_name }}</strong>
                                    <small
                                        >{{ test.risk_model_title }} ·
                                        {{
                                            formatDateTime(test.generated_at)
                                        }}</small
                                    >
                                </div>
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openRiskModelTest(test.test_name)"
                                >
                                    <FolderOpen :size="16" />
                                    <span>{{ t.loadSaved }}</span>
                                </button>
                            </article>
                        </div>
                    </div>

                    <div v-if="riskModelResult" class="cpcv-results">
                        <div class="result-strip">
                            <article>
                                <span class="section-title-with-help">
                                    VaR
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('varResult')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <strong>{{
                                    riskModelResult.summary[0]?.value ?? "—"
                                }}</strong>
                                <small>{{
                                    riskModelResult.metadata.confidence_level
                                }}</small>
                                <small
                                    v-if="activeFieldTooltip === 'varResult'"
                                    class="result-tooltip"
                                >
                                    {{ tooltipText(t.varResultTooltip) }}
                                </small>
                            </article>
                            <article>
                                <span class="section-title-with-help">
                                    CVaR
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="toggleFieldTooltip('cvarResult')"
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <strong>{{ riskCvarSummaryValue }}</strong>
                                <small>{{ riskModelResult.metadata.engine }}</small>
                                <small
                                    v-if="activeFieldTooltip === 'cvarResult'"
                                    class="result-tooltip"
                                >
                                    {{ tooltipText(t.cvarResultTooltip) }}
                                </small>
                            </article>
                            <article>
                                <span>{{ t.assets }}</span>
                                <strong>{{
                                    riskModelResult.metadata.asset_count
                                }}</strong>
                                <small
                                    >{{ t.scenarios }}:
                                    {{
                                        riskModelResult.metadata.scenario_count
                                    }}</small
                                >
                                <button
                                    class="icon-text-button"
                                    type="button"
                                    @click="openAssetsModal('riskModel')"
                                >
                                    <span>{{ t.viewAssets }}</span>
                                </button>
                            </article>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span>{{ t.interpretation }}</span>
                                <strong>{{
                                    riskModelResult.metadata.risk_model_title
                                }}</strong>
                            </div>
                            <p class="risk-interpretation">
                                {{ riskModelResult.interpretation }}
                            </p>
                        </div>

                        <div class="chart-panel">
                            <div class="section-title">
                                <span class="section-title-with-help">
                                    {{ t.lossDistribution }}
                                    <button
                                        class="field-help"
                                        type="button"
                                        @click.stop="
                                            toggleFieldTooltip('lossDistribution')
                                        "
                                    >
                                        <CircleHelp :size="13" />
                                    </button>
                                </span>
                                <strong>VaR</strong>
                            </div>
                            <p
                                v-if="activeFieldTooltip === 'lossDistribution'"
                                class="chart-tooltip"
                            >
                                {{ tooltipText(t.lossDistributionTooltip) }}
                            </p>
                            <svg
                                class="cpcv-chart"
                                viewBox="0 0 720 260"
                                role="img"
                            >
                                <line x1="48" y1="212" x2="702" y2="212" />
                                <line x1="48" y1="18" x2="48" y2="212" />
                                <rect
                                    v-for="(bar, index) in riskDistributionBars"
                                    :key="index"
                                    :x="bar.x"
                                    :y="bar.y"
                                    :width="bar.width"
                                    :height="bar.height"
                                    :fill="bar.color"
                                    :opacity="bar.opacity"
                                    rx="1"
                                />
                                <text
                                    v-for="(
                                        label, i
                                    ) in riskDistributionXAxisLabels"
                                    :key="'riskdistx' + i"
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
                                    ) in riskDistributionYAxisLabels"
                                    :key="'riskdisty' + i"
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

                        <div class="dual-chart-grid">
                            <div class="chart-panel">
                                <div class="section-title">
                                    <span class="section-title-with-help">
                                        {{ t.simulatedPortfolioPaths }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip(
                                                    'simulatedPortfolioPaths',
                                                )
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong>{{
                                        riskModelResult.simulated_paths?.paths
                                            ?.length ?? 0
                                    }}</strong>
                                </div>
                                <p
                                    v-if="
                                        activeFieldTooltip ===
                                        'simulatedPortfolioPaths'
                                    "
                                    class="chart-tooltip"
                                >
                                    {{
                                        tooltipText(
                                            t.simulatedPortfolioPathsTooltip,
                                        )
                                    }}
                                </p>
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line
                                        x1="48"
                                        y1="212"
                                        x2="702"
                                        y2="212"
                                    />
                                    <line
                                        x1="48"
                                        y1="18"
                                        x2="48"
                                        y2="212"
                                    />
                                    <polyline
                                        v-for="(
                                            line, index
                                        ) in riskScenarioPathLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        v-for="(label, i) in riskPathsXAxisLabels"
                                        :key="'riskpathsx' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(label, i) in riskPathsYAxisLabels"
                                        :key="'riskpathsy' + i"
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
                                    <span class="section-title-with-help">
                                        {{ t.cumulativeLossDistribution }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip(
                                                    'cumulativeLossDistribution',
                                                )
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong>CDF</strong>
                                </div>
                                <p
                                    v-if="
                                        activeFieldTooltip ===
                                        'cumulativeLossDistribution'
                                    "
                                    class="chart-tooltip"
                                >
                                    {{
                                        tooltipText(
                                            t.cumulativeLossDistributionTooltip,
                                        )
                                    }}
                                </p>
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line
                                        x1="48"
                                        y1="212"
                                        x2="702"
                                        y2="212"
                                    />
                                    <line
                                        x1="48"
                                        y1="18"
                                        x2="48"
                                        y2="212"
                                    />
                                    <polyline
                                        v-for="(line, index) in riskCdfLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        v-for="(label, i) in riskCdfXAxisLabels"
                                        :key="'riskcdfx' + i"
                                        :x="label.x"
                                        y="228"
                                        text-anchor="middle"
                                        font-size="10"
                                        fill="#8992a3"
                                    >
                                        {{ label.text }}
                                    </text>
                                    <text
                                        v-for="(label, i) in riskCdfYAxisLabels"
                                        :key="'riskcdfy' + i"
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
                                    <span class="section-title-with-help">
                                        {{ t.historicalPortfolioValue }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip(
                                                    'historicalPortfolioValue',
                                                )
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong>{{
                                        riskModelResult.metadata.test_period.rows
                                    }}</strong>
                                </div>
                                <p
                                    v-if="
                                        activeFieldTooltip ===
                                        'historicalPortfolioValue'
                                    "
                                    class="chart-tooltip"
                                >
                                    {{
                                        tooltipText(
                                            t.historicalPortfolioValueTooltip,
                                        )
                                    }}
                                </p>
                                <svg
                                    class="cpcv-chart"
                                    viewBox="0 0 720 260"
                                    role="img"
                                >
                                    <line
                                        x1="48"
                                        y1="212"
                                        x2="702"
                                        y2="212"
                                    />
                                    <line
                                        x1="48"
                                        y1="18"
                                        x2="48"
                                        y2="212"
                                    />
                                    <polyline
                                        v-for="(
                                            line, index
                                        ) in riskHistoricalLines"
                                        :key="index"
                                        :points="line.points"
                                        :stroke="line.color"
                                        :opacity="line.opacity"
                                    />
                                    <text
                                        v-for="(
                                            label, i
                                        ) in riskHistoricalXAxisLabels"
                                        :key="'riskhistx' + i"
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
                                        ) in riskHistoricalYAxisLabels"
                                        :key="'riskhisty' + i"
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
                                    <span class="section-title-with-help">
                                        {{ t.riskSummary }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip('riskSummary')
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong>{{
                                        riskModelResult.metadata.test_name
                                    }}</strong>
                                </div>
                                <p
                                    v-if="activeFieldTooltip === 'riskSummary'"
                                    class="chart-tooltip"
                                >
                                    {{ tooltipText(t.riskSummaryTooltip) }}
                                </p>
                                <div class="metrics-grid">
                                    <div
                                        v-for="row in riskModelResult.summary"
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
                                    <span class="section-title-with-help">
                                        {{ t.metrics }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip('riskMetrics')
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong>{{ activeRiskModel.title }}</strong>
                                </div>
                                <p
                                    v-if="activeFieldTooltip === 'riskMetrics'"
                                    class="chart-tooltip"
                                >
                                    {{ tooltipText(t.riskMetricsTooltip) }}
                                </p>
                                <div class="metrics-grid">
                                    <div
                                        v-for="row in riskModelResult.report"
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

                        <div class="dual-chart-grid">
                            <div class="chart-panel">
                                <div class="section-title">
                                    <span class="section-title-with-help">
                                        {{ t.riskModelPortfolio }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip(
                                                    'riskModelPortfolio',
                                                )
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong>{{
                                        riskModelResult.portfolio_weights.length
                                    }}</strong>
                                </div>
                                <p
                                    v-if="
                                        activeFieldTooltip ===
                                        'riskModelPortfolio'
                                    "
                                    class="chart-tooltip"
                                >
                                    {{
                                        tooltipText(
                                            t.riskModelPortfolioTooltip,
                                        )
                                    }}
                                </p>
                                <div class="table-scroll">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Ticker</th>
                                                <th>{{ t.weight }}</th>
                                                <th>{{ t.sector }}</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr
                                                v-for="item in riskModelResult.portfolio_weights"
                                                :key="item.ticker"
                                            >
                                                <td>
                                                    <strong>{{
                                                        item.ticker
                                                    }}</strong>
                                                    <br />
                                                    <small>{{
                                                        item.name
                                                    }}</small>
                                                </td>
                                                <td>
                                                    {{
                                                        formatWeight(
                                                            item.weight,
                                                        )
                                                    }}
                                                </td>
                                                <td>
                                                    {{
                                                        normalizeSector(
                                                            item.sector,
                                                        )
                                                    }}
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <div
                                v-if="riskModelResult.qae_distribution"
                                class="chart-panel"
                            >
                                <div class="section-title">
                                    <span class="section-title-with-help">
                                        {{ t.qaeDistribution }}
                                        <button
                                            class="field-help"
                                            type="button"
                                            @click.stop="
                                                toggleFieldTooltip(
                                                    'qaeDistribution',
                                                )
                                            "
                                        >
                                            <CircleHelp :size="13" />
                                        </button>
                                    </span>
                                    <strong
                                        >{{
                                            riskModelResult.qae_distribution
                                                .bucket_count
                                        }}
                                        /
                                        {{
                                            riskModelResult.qae_distribution
                                                .qubits
                                        }}
                                        qubits</strong
                                    >
                                </div>
                                <p
                                    v-if="activeFieldTooltip === 'qaeDistribution'"
                                    class="chart-tooltip"
                                >
                                    {{ tooltipText(t.qaeDistributionTooltip) }}
                                </p>
                                <div class="table-scroll">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Bucket</th>
                                                <th>Loss</th>
                                                <th>Probability</th>
                                                <th>Count</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr
                                                v-for="bucket in riskModelResult
                                                    .qae_distribution.buckets"
                                                :key="bucket.bucket"
                                            >
                                                <td>
                                                    <strong>{{
                                                        bucket.bucket
                                                    }}</strong>
                                                </td>
                                                <td>
                                                    {{
                                                        formatPrice(bucket.loss)
                                                    }}
                                                </td>
                                                <td>
                                                    {{
                                                        formatMetricValue(
                                                            bucket.probability,
                                                            "percent",
                                                        )
                                                    }}
                                                </td>
                                                <td>{{ bucket.count }}</td>
                                            </tr>
                                        </tbody>
                                    </table>
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
                            <label>
                                <span>{{ t.rebalanceFreq }}</span>
                                <div class="frequency-input">
                                    <input
                                        v-model.number="rebalanceFrequencyAmount"
                                        aria-label="Rebalance frequency value"
                                        min="1"
                                        step="1"
                                        type="number"
                                    />
                                    <select
                                        v-model="rebalanceFrequencyUnit"
                                        aria-label="Rebalance frequency unit"
                                    >
                                        <option
                                            v-for="unit in rebalanceFrequencyUnits"
                                            :key="unit"
                                            :value="unit"
                                        >
                                            {{ unit }}
                                        </option>
                                    </select>
                                </div>
                            </label>
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
                        <div class="backtest-report-actions">
                            <button
                                class="icon-text-button backtest-pnl-trigger"
                                type="button"
                                @click="showBacktestPnlModal = true"
                            >
                                <FileChartColumn :size="17" />
                                <span>{{
                                    locale === "ru"
                                        ? "Отчет PnL"
                                        : "PnL Report"
                                }}</span>
                            </button>
                        </div>
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
                                            v-for="item in paginatedRebalanceWeights"
                                            :key="item.record.time"
                                        >
                                            <th>
                                                <strong>#{{ item.number }}</strong>
                                                <br />
                                                {{
                                                    formatDateTime(item.record.time)
                                                }}
                                            </th>
                                            <td>
                                                <strong
                                                    >{{ t.totalWeight }}:
                                                    {{
                                                            formatWeight(
                                                            item.record.total_weight,
                                                        )
                                                    }}
                                                    /
                                                    {{
                                                        item.record.asset_count
                                                    }}</strong
                                                >
                                                <br />
                                                <span
                                                    v-for="weight in item.record.weights.slice(
                                                        0,
                                                        12,
                                                    )"
                                                    :key="`${item.record.time}-${weight.ticker}`"
                                                    class="weight-pill"
                                                >
                                                    {{ weight.ticker }}
                                                    {{
                                                        formatWeight(
                                                            weight.weight,
                                                        )
                                                    }}
                                                </span>
                                                <button
                                                    v-if="item.record.weights.length > 0"
                                                    class="icon-text-button compact-action"
                                                    type="button"
                                                    @click="
                                                        openWeightsModal(item.record)
                                                    "
                                                >
                                                    <template
                                                        v-if="item.record.weights.length > 12"
                                                    >
                                                        {{ t.showAll }} (+{{
                                                            item.record.weights.length -
                                                            12
                                                        }}
                                                        {{ t.hiddenAssets }})
                                                    </template>
                                                    <template v-else>
                                                        {{ t.details }}
                                                    </template>
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            <div
                                v-if="rebalancePageCount > 1"
                                class="table-pagination"
                            >
                                <button
                                    :disabled="rebalancePage === 1"
                                    type="button"
                                    @click="rebalancePage--"
                                >
                                    {{ t.previousPage }}
                                </button>
                                <span>
                                    {{ t.page }} {{ rebalancePage }} / {{ rebalancePageCount }}
                                </span>
                                <button
                                    :disabled="rebalancePage === rebalancePageCount"
                                    type="button"
                                    @click="rebalancePage++"
                                >
                                    {{ t.nextPage }}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <BacktestPnlReportModal
                v-if="showBacktestPnlModal && backtestResult"
                :result="backtestResult"
                :locale="locale"
                @close="showBacktestPnlModal = false"
            />

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
