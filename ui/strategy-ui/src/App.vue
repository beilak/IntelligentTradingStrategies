<script setup lang="ts">
import {
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
  X,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import {
  getCpcvTest,
  getModelDetail,
  getRegistry,
  getWalkForwardTest,
  listCpcvTests,
  listWalkForwardTests,
  runCpcvTest,
  runWalkForwardTest,
} from "./api";
import { messages, cpcvMetricTranslations } from "./i18n";
import type {
  CpcvResult,
  CpcvSavedTest,
  CpcvSettings,
  Locale,
  ModelDetail,
  RegistryGroup,
  RegistryItem,
  RegistryResponse,
  WalkForwardResult,
  WalkForwardSavedTest,
  WalkForwardSettings,
} from "./types";

const savedLocale = localStorage.getItem("its-strategy-locale") as Locale | null;
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
const error = ref("");
const cpcvError = ref("");
const walkForwardError = ref("");
const savedCpcvTests = ref<CpcvSavedTest[]>([]);
const savedWalkForwardTests = ref<WalkForwardSavedTest[]>([]);
const cpcvResult = ref<CpcvResult | null>(null);
const walkForwardResult = ref<WalkForwardResult | null>(null);
const cpcvSettings = ref<CpcvSettings>(defaultCpcvSettings());
const walkForwardSettings = ref<WalkForwardSettings>(defaultWalkForwardSettings());
const showCpcvModal = ref(false);
const showWalkForwardModal = ref(false);
const showAssetsModal = ref(false);
const activeAssetsSource = ref<"cpcv" | "walkForward">("cpcv");
const xAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const yAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const wfXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const wfYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const wfOosXAxisLabels = ref<Array<{ x: number; text: string }>>([]);
const wfOosYAxisLabels = ref<Array<{ y: number; text: string }>>([]);
const isFullscreen = ref(false);
const chartContainer = ref<HTMLElement | null>(null);
const walkForwardChartContainer = ref<HTMLElement | null>(null);

const groups = computed(() => registry.value?.groups ?? []);
const selectedGroup = computed<RegistryGroup | undefined>(() =>
  groups.value.find((group) => group.id === selectedGroupId.value),
);
const selectedItems = computed<RegistryItem[]>(() => selectedGroup.value?.items ?? []);
const isCoreStrategyTab = computed(() => selectedGroupId.value === "strategy_model");
const chartLines = computed(() => buildChartLines(cpcvResult.value));
const walkForwardChartLines = computed(() =>
  buildChartLines(walkForwardResult.value, wfXAxisLabels, wfYAxisLabels),
);
const walkForwardOosChartLines = computed(() =>
  buildChartLines(walkForwardOosChartResult.value, wfOosXAxisLabels, wfOosYAxisLabels),
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
    cpcvError.value = "";
    walkForwardError.value = "";
    await loadSavedCpcvTests(modelName);
    await loadSavedWalkForwardTests(modelName);
  } catch (err) {
    error.value = formatError(err);
  } finally {
    isModelLoading.value = false;
  }
}

function setGroup(groupId: string) {
  selectedGroupId.value = groupId;
}

function iconFor(groupId: string) {
  return {
    pre_selection: SearchCheck,
    signal_model: BrainCircuit,
    allocation: Scale,
    strategy_model: Boxes,
  }[groupId] ?? Layers3;
}

function labelFor(groupId: string) {
  const labels = t.value as Record<string, string>;
  return labels[groupId] ?? groupId;
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
    cpcvResult.value = await runCpcvTest(selectedModelName.value, cpcvSettings.value);
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
    savedWalkForwardTests.value = (await listWalkForwardTests(modelName)).items;
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
    walkForwardResult.value = await getWalkForwardTest(selectedModelName.value, testName);
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
    walkForwardResult.value = await runWalkForwardTest(selectedModelName.value, walkForwardSettings.value);
    await loadSavedWalkForwardTests(selectedModelName.value);
  } catch (err) {
    walkForwardError.value = formatError(err);
  } finally {
    isWalkForwardRunning.value = false;
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

function toDateInput(value: Date) {
  return value.toISOString().slice(0, 10);
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

function openAssetsModal(source: "cpcv" | "walkForward") {
  activeAssetsSource.value = source;
  showAssetsModal.value = true;
}

function buildChartLines(
  result: { paths: Array<{ points: Array<{ time: string; value: number }> }> } | null,
  xLabelsRef = xAxisLabels,
  yLabelsRef = yAxisLabels,
) {
  const paths = result?.paths ?? [];
  const values = paths.flatMap((path) => path.points.map((point) => point.value));
  const timestamps = paths.flatMap((path) =>
    path.points.map((point) => new Date(point.time).getTime()).filter((value) => Number.isFinite(value)),
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
  const colors = ["#66d9ef", "#ffcc66", "#aee9d1", "#ff6b8a", "#b48cf2", "#7dd3fc"];
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
    for (let i = step; i < timePoints.length - 1; i += step) indices.push(i);
    if (timePoints.length > 1) indices.push(timePoints.length - 1);

    indices.forEach((pointIndex) => {
      const d = new Date(timePoints[pointIndex].time);
      const x = pad + ((d.getTime() - minTime) / timeRange) * (width - pad * 2);
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
    yLabels.push({ y, text: (tick * 100).toFixed(1) + "%" });
  }
  yLabelsRef.value = yLabels;

  return paths.map((path, index) => {
    const points = path.points
      .map((point) => {
        const pointTime = new Date(point.time).getTime();
        const x = pad + ((pointTime - minTime) / timeRange) * (width - pad * 2);
        const y = height - pad - ((point.value - min) / range) * (height - pad * 2);
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
          <button type="button" :class="{ active: locale === 'ru' }" @click="locale = 'ru'">RU</button>
          <button type="button" :class="{ active: locale === 'en' }" @click="locale = 'en'">EN</button>
        </div>
        <button class="icon-button" type="button" @click="loadRegistry">
          <RefreshCw :class="{ spin: isLoading || isModelLoading }" :size="17" />
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
            <strong>{{ selectedGroup ? labelFor(selectedGroup.id) : t.loading }}</strong>
          </div>
          <p>{{ selectedGroup?.role }}</p>
        </section>

        <section class="main-grid" :class="{ 'single-column': !isCoreStrategyTab }">
          <div class="registry-panel">
            <div class="panel-head">
              <div>
                <span>{{ t.components }}</span>
                <strong>{{ selectedGroup ? labelFor(selectedGroup.id) : "—" }}</strong>
              </div>
              <Layers3 :size="18" />
            </div>

            <div v-if="isLoading" class="empty-state">
              <RefreshCw class="spin" :size="24" />
              <span>{{ t.loading }}</span>
            </div>

            <div v-else-if="selectedItems.length === 0" class="empty-state">
              <span>{{ t.empty }}</span>
            </div>

            <div v-else class="component-list">
              <article
                v-for="item in selectedItems"
                :key="`${item.module}.${item.name}`"
                class="component-card"
                :class="{ selected: item.name === selectedModelName }"
                @click="selectedGroupId === 'strategy_model' && loadModel(item.name)"
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

          <div v-if="isCoreStrategyTab" class="detail-panel">
            <div class="panel-head">
              <div>
                <span>{{ t.models }}</span>
                <strong>{{ modelDetail?.name ?? t.selectModel }}</strong>
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
                  <article v-for="step in modelDetail.composition.steps" :key="step.step" class="step">
                    <small>{{ labelFor(step.category) }}</small>
                    <strong>{{ step.step }}</strong>
                    <code>{{ step.component }}</code>
                  </article>
                </div>
              </section>

              <section class="detail-section">
                <span>{{ t.testing }}</span>
                <div class="report-grid">
                  <button class="report-btn" type="button" @click="showCpcvModal = true">
                    <strong>CPCV</strong>
                  </button>
                  <button class="report-btn" type="button" @click="showWalkForwardModal = true">
                    <strong>WalkForward</strong>
                  </button>
                  <article v-for="report in modelDetail.future_reports.filter((item) => !['cpcv', 'walk_forward'].includes(item.id))" :key="report.id" class="report">
                    <strong>{{ report.title }}</strong>
                    <small>{{ t.planned }}</small>
                  </article>
                </div>
              </section>
            </template>
          </div>
        </section>
      </section>

      <div v-if="showCpcvModal" class="modal-overlay" @click.self="showCpcvModal = false">
        <div class="modal-fullscreen">
          <div class="modal-header">
            <div class="section-title">
              <span>{{ t.cpcvSettings }}</span>
              <strong>{{ t.cpcv }}</strong>
            </div>
            <button class="icon-button" type="button" @click="showCpcvModal = false">
              <X :size="18" />
            </button>
          </div>

          <p v-if="cpcvError" class="error-banner">{{ cpcvError }}</p>

          <div class="cpcv-layout">
            <div class="form-grid">
              <label>
                <span>{{ t.testName }}</span>
                <input v-model="cpcvSettings.test_name" type="text" />
              </label>
              <label>
                <span>{{ t.startDate }}</span>
                <input v-model="cpcvSettings.start_date" type="date" />
              </label>
              <label>
                <span>{{ t.endDate }}</span>
                <input v-model="cpcvSettings.end_date" type="date" />
              </label>
              <label>
                <span>{{ t.interval }}</span>
                <select v-model="cpcvSettings.interval">
                  <option value="CANDLE_INTERVAL_DAY">Day</option>
                  <option value="CANDLE_INTERVAL_HOUR">Hour</option>
                  <option value="CANDLE_INTERVAL_WEEK">Week</option>
                  <option value="CANDLE_INTERVAL_MONTH">Month</option>
                </select>
              </label>
              <label>
                <span>{{ t.classCode }}</span>
                <input v-model="cpcvSettings.class_code" type="text" />
              </label>
              <label>
                <span>{{ t.nFolds }}</span>
                <input v-model.number="cpcvSettings.n_folds" min="2" max="30" type="number" />
              </label>
              <label>
                <span>{{ t.nTestFolds }}</span>
                <input v-model.number="cpcvSettings.n_test_folds" min="1" max="29" type="number" />
              </label>
              <label>
                <span>{{ t.testSize }}</span>
                <input v-model.number="cpcvSettings.test_size" min="0.05" max="0.50" step="0.01" type="number" />
              </label>
            </div>

            <div class="cpcv-actions">
              <button class="primary-button" type="button" :disabled="isCpcvRunning" @click="runCpcv">
                <RefreshCw v-if="isCpcvRunning" class="spin" :size="17" />
                <PlayCircle v-else :size="17" />
                <span>{{ isCpcvRunning ? t.processing : t.runAndSave }}</span>
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
            <div v-else-if="savedCpcvTests.length === 0" class="small-state">
              <span>{{ t.noSavedTests }}</span>
            </div>
            <div v-else class="saved-list">
              <article v-for="test in savedCpcvTests" :key="test.file_name" class="saved-card">
                <div>
                  <strong>{{ test.test_name }}</strong>
                  <small>{{ formatDateTime(test.generated_at) }}</small>
                </div>
                <button class="icon-text-button" type="button" @click="openCpcvTest(test.test_name)">
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
                <strong>{{ cpcvResult.metadata.train_period.rows }}</strong>
                <small>{{ formatDateTime(cpcvResult.metadata.train_period.start) }} - {{ formatDateTime(cpcvResult.metadata.train_period.end) }}</small>
              </article>
              <article>
                <span>{{ t.test }}</span>
                <strong>{{ cpcvResult.metadata.test_period.rows }}</strong>
                <small>{{ formatDateTime(cpcvResult.metadata.test_period.start) }} - {{ formatDateTime(cpcvResult.metadata.test_period.end) }}</small>
              </article>
              <article>
                <span>{{ t.assets }}</span>
                <strong>{{ cpcvResult.metadata.asset_count }}</strong>
                <small>{{ cpcvResult.metadata.settings.interval }}</small>
                <button class="icon-text-button" type="button" @click="openAssetsModal('cpcv')">
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
                <button class="fullscreen-btn" type="button" @click="toggleFullscreen">
                  {{ isFullscreen ? 'Exit ⛶' : 'Fullscreen ⛶' }}
                </button>
                <svg class="cpcv-chart" viewBox="0 0 720 260" role="img">
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
                  >{{ label.text }}</text>
                  <text
                    v-for="(label, i) in yAxisLabels"
                    :key="'y' + i"
                    :x="44"
                    :y="label.y"
                    text-anchor="end"
                    font-size="10"
                    fill="#8992a3"
                    dominant-baseline="middle"
                  >{{ label.text }}</text>
                </svg>
              </div>
            </div>

            <div class="metrics-container">
              <div class="metrics-section">
                <div class="section-title">
                  <span>{{ t.metrics }}</span>
                  <strong>{{ cpcvResult.metadata.test_name }}</strong>
                </div>
                <div class="metrics-grid">
                  <div v-for="row in cpcvResult.report" :key="row.metric" class="metric-item">
                    <span class="metric-label">{{ translateMetric(row.metric) }}</span>
                    <span class="metric-value">{{ row.value }}</span>
                  </div>
                </div>
              </div>

              <div class="metrics-section">
                <div class="section-title">
                  <span>{{ t.cvSummary }}</span>
                  <strong>CPCV</strong>
                </div>
                <div class="metrics-grid">
                  <div v-for="row in cpcvResult.cv_summary" :key="row.metric" class="metric-item">
                    <span class="metric-label">{{ translateMetric(row.metric) }}</span>
                    <span class="metric-value">{{ row.value }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="showWalkForwardModal" class="modal-overlay" @click.self="showWalkForwardModal = false">
        <div class="modal-fullscreen">
          <div class="modal-header">
            <div class="section-title">
              <span>{{ t.walkForwardSettings }}</span>
              <strong>{{ t.walkForward }}</strong>
            </div>
            <button class="icon-button" type="button" @click="showWalkForwardModal = false">
              <X :size="18" />
            </button>
          </div>

          <p v-if="walkForwardError" class="error-banner">{{ walkForwardError }}</p>

          <div class="cpcv-layout">
            <div class="form-grid">
              <label>
                <span>{{ t.testName }}</span>
                <input v-model="walkForwardSettings.test_name" type="text" />
              </label>
              <label>
                <span>{{ t.startDate }}</span>
                <input v-model="walkForwardSettings.start_date" type="date" />
              </label>
              <label>
                <span>{{ t.endDate }}</span>
                <input v-model="walkForwardSettings.end_date" type="date" />
              </label>
              <label>
                <span>{{ t.interval }}</span>
                <select v-model="walkForwardSettings.interval">
                  <option value="CANDLE_INTERVAL_DAY">Day</option>
                  <option value="CANDLE_INTERVAL_HOUR">Hour</option>
                  <option value="CANDLE_INTERVAL_WEEK">Week</option>
                  <option value="CANDLE_INTERVAL_MONTH">Month</option>
                </select>
              </label>
              <label>
                <span>{{ t.classCode }}</span>
                <input v-model="walkForwardSettings.class_code" type="text" />
              </label>
              <label>
                <span>{{ t.testSize }}</span>
                <input v-model.number="walkForwardSettings.test_size" min="0.05" max="0.80" step="0.01" type="number" />
              </label>
              <label>
                <span>{{ t.trainSizeMonths }}</span>
                <input v-model.number="walkForwardSettings.train_size_months" min="1" max="120" type="number" />
              </label>
              <label>
                <span>{{ t.freqMonths }}</span>
                <input v-model.number="walkForwardSettings.freq_months" min="1" max="120" type="number" />
              </label>
              <label>
                <span>{{ t.wfTestSize }}</span>
                <input v-model.number="walkForwardSettings.wf_test_size" min="1" max="500" type="number" />
              </label>
            </div>

            <div class="cpcv-actions">
              <button class="primary-button" type="button" :disabled="isWalkForwardRunning" @click="runWalkForward">
                <RefreshCw v-if="isWalkForwardRunning" class="spin" :size="17" />
                <PlayCircle v-else :size="17" />
                <span>{{ isWalkForwardRunning ? t.processing : t.runAndSave }}</span>
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
            <div v-else-if="savedWalkForwardTests.length === 0" class="small-state">
              <span>{{ t.noSavedTests }}</span>
            </div>
            <div v-else class="saved-list">
              <article v-for="test in savedWalkForwardTests" :key="test.file_name" class="saved-card">
                <div>
                  <strong>{{ test.test_name }}</strong>
                  <small>{{ formatDateTime(test.generated_at) }}</small>
                </div>
                <button class="icon-text-button" type="button" @click="openWalkForwardTest(test.test_name)">
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
                <strong>{{ walkForwardResult.metadata.train_period.rows }}</strong>
                <small>{{ formatDateTime(walkForwardResult.metadata.train_period.start) }} - {{ formatDateTime(walkForwardResult.metadata.train_period.end) }}</small>
              </article>
              <article>
                <span>{{ t.test }}</span>
                <strong>{{ walkForwardResult.metadata.test_period.rows }}</strong>
                <small>{{ formatDateTime(walkForwardResult.metadata.test_period.start) }} - {{ formatDateTime(walkForwardResult.metadata.test_period.end) }}</small>
              </article>
              <article>
                <span>{{ t.assets }}</span>
                <strong>{{ walkForwardResult.metadata.asset_count }}</strong>
                <small>{{ walkForwardResult.metadata.settings.interval }}</small>
                <button class="icon-text-button" type="button" @click="openAssetsModal('walkForward')">
                  <span>{{ t.viewAssets }}</span>
                </button>
              </article>
            </div>

            <div class="chart-panel">
              <div class="section-title">
                <span>{{ t.stitchedOosCurve }}</span>
                <strong>{{ t.walkForwardOosBacktest }}</strong>
              </div>
              <div ref="walkForwardChartContainer" class="chart-wrapper">
                <button class="fullscreen-btn" type="button" @click="toggleWalkForwardFullscreen">
                  {{ isFullscreen ? 'Exit ⛶' : 'Fullscreen ⛶' }}
                </button>
                <svg class="cpcv-chart" viewBox="0 0 720 260" role="img">
                  <line x1="48" y1="212" x2="702" y2="212" />
                  <line x1="48" y1="18" x2="48" y2="212" />
                  <polyline
                    v-for="(line, index) in walkForwardOosChartLines"
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
                  >{{ label.text }}</text>
                  <text
                    v-for="(label, i) in wfOosYAxisLabels"
                    :key="'wfoosy' + i"
                    :x="44"
                    :y="label.y"
                    text-anchor="end"
                    font-size="10"
                    fill="#8992a3"
                    dominant-baseline="middle"
                  >{{ label.text }}</text>
                </svg>
              </div>
              <div class="chart-meta">
                <span>{{ walkForwardResult.oos_curve?.stitch_rule }}</span>
                <strong>{{ t.duplicatesRemoved }}: {{ walkForwardResult.oos_curve?.duplicates_removed ?? 0 }}</strong>
              </div>
            </div>

            <div class="chart-panel">
              <div class="section-title">
                <span>{{ t.walkForwardPaths }}</span>
                <strong>{{ walkForwardResult.paths.length }}</strong>
              </div>
              <div class="chart-wrapper">
                <svg class="cpcv-chart" viewBox="0 0 720 260" role="img">
                  <line x1="48" y1="212" x2="702" y2="212" />
                  <line x1="48" y1="18" x2="48" y2="212" />
                  <polyline
                    v-for="(line, index) in walkForwardChartLines"
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
                  >{{ label.text }}</text>
                  <text
                    v-for="(label, i) in wfYAxisLabels"
                    :key="'wfy' + i"
                    :x="44"
                    :y="label.y"
                    text-anchor="end"
                    font-size="10"
                    fill="#8992a3"
                    dominant-baseline="middle"
                  >{{ label.text }}</text>
                </svg>
              </div>
            </div>

            <div class="chart-panel">
              <div class="section-title">
                <span>{{ t.wfSplits }}</span>
                <strong>{{ walkForwardResult.windows?.length ?? 0 }}</strong>
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
                    <tr v-for="window in walkForwardResult.windows ?? []" :key="window.split_id">
                      <td><strong>{{ window.split_id }}</strong></td>
                      <td>
                        {{ formatDateTime(window.train_start) }} - {{ formatDateTime(window.train_end) }}
                        <br />
                        <small>{{ window.train_rows }}</small>
                      </td>
                      <td>
                        {{ formatDateTime(window.test_start) }} - {{ formatDateTime(window.test_end) }}
                        <br />
                        <small>{{ window.test_rows }}</small>
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
                  <strong>{{ walkForwardResult.metadata.test_name }}</strong>
                </div>
                <div class="metrics-grid">
                  <div v-for="row in walkForwardResult.report" :key="row.metric" class="metric-item">
                    <span class="metric-label">{{ translateMetric(row.metric) }}</span>
                    <span class="metric-value">{{ row.value }}</span>
                  </div>
                </div>
              </div>

              <div class="metrics-section">
                <div class="section-title">
                  <span>{{ t.cvSummary }}</span>
                  <strong>WalkForward</strong>
                </div>
                <div class="metrics-grid">
                  <div v-for="row in walkForwardResult.cv_summary" :key="row.metric" class="metric-item">
                    <span class="metric-label">{{ translateMetric(row.metric) }}</span>
                    <span class="metric-value">{{ row.value }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

      <div v-if="showAssetsModal" class="modal-overlay" @click.self="showAssetsModal = false">
        <div class="modal-fullscreen" style="max-width: 800px">
          <div class="modal-header">
            <div class="section-title">
              <span>{{ t.assets }}</span>
              <strong>{{ activeAssetCount }}</strong>
            </div>
            <button class="icon-button" type="button" @click="showAssetsModal = false">
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
                <tr v-for="asset in activeAssets" :key="asset.figi">
                  <td><code>{{ asset.figi }}</code></td>
                  <td><strong>{{ asset.ticker }}</strong></td>
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
