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
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import { getCpcvTest, getModelDetail, getRegistry, listCpcvTests, runCpcvTest } from "./api";
import { messages } from "./i18n";
import type {
  CpcvResult,
  CpcvSavedTest,
  CpcvSettings,
  Locale,
  ModelDetail,
  RegistryGroup,
  RegistryItem,
  RegistryResponse,
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
const error = ref("");
const cpcvError = ref("");
const savedCpcvTests = ref<CpcvSavedTest[]>([]);
const cpcvResult = ref<CpcvResult | null>(null);
const cpcvSettings = ref<CpcvSettings>(defaultCpcvSettings());

const groups = computed(() => registry.value?.groups ?? []);
const selectedGroup = computed<RegistryGroup | undefined>(() =>
  groups.value.find((group) => group.id === selectedGroupId.value),
);
const selectedItems = computed<RegistryItem[]>(() => selectedGroup.value?.items ?? []);
const isCoreStrategyTab = computed(() => selectedGroupId.value === "strategy_model");
const chartLines = computed(() => buildChartLines(cpcvResult.value));

watch(locale, (value) => localStorage.setItem("its-strategy-locale", value));

onMounted(async () => {
  await loadRegistry();
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
    cpcvError.value = "";
    await loadSavedCpcvTests(modelName);
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
      force: false,
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
    asset_limit: 40,
    force: false,
  };
}

function toDateInput(value: Date) {
  return value.toISOString().slice(0, 10);
}

function formatDateTime(value?: string) {
  if (!value) return "—";
  return value.replace("T", " ").replace(/\.\d+.*$/, "");
}

function buildChartLines(result: CpcvResult | null) {
  const paths = result?.paths ?? [];
  const values = paths.flatMap((path) => path.points.map((point) => point.value));
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 720;
  const height = 260;
  const pad = 18;
  const colors = ["#66d9ef", "#ffcc66", "#aee9d1", "#ff6b8a", "#b48cf2", "#7dd3fc"];

  return paths.map((path, index) => {
    const lastIndex = Math.max(path.points.length - 1, 1);
    const points = path.points
      .map((point, pointIndex) => {
        const x = pad + (pointIndex / lastIndex) * (width - pad * 2);
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
                <span>{{ t.reports }}</span>
                <div class="report-grid">
                  <article v-for="report in modelDetail.future_reports.filter((item) => item.id !== 'cpcv')" :key="report.id" class="report">
                    <strong>{{ report.title }}</strong>
                    <small>{{ t.planned }}</small>
                  </article>
                </div>
              </section>

              <section class="detail-section cpcv-section">
                <div class="section-title">
                  <span>{{ t.cpcvSettings }}</span>
                  <strong>{{ t.cpcv }}</strong>
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
                      <span>{{ t.assetLimit }}</span>
                      <input v-model.number="cpcvSettings.asset_limit" min="2" max="500" type="number" />
                    </label>
                  </div>

                  <div class="cpcv-actions">
                    <label class="checkbox-row">
                      <input v-model="cpcvSettings.force" type="checkbox" />
                      <span>{{ t.forceRun }}</span>
                    </label>
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
                    </article>
                  </div>

                  <div class="chart-panel">
                    <div class="section-title">
                      <span>{{ t.testPaths }}</span>
                      <strong>{{ cpcvResult.paths.length }}</strong>
                    </div>
                    <svg class="cpcv-chart" viewBox="0 0 720 260" role="img">
                      <line x1="18" y1="242" x2="702" y2="242" />
                      <line x1="18" y1="18" x2="18" y2="242" />
                      <polyline
                        v-for="(line, index) in chartLines"
                        :key="index"
                        :points="line.points"
                        :stroke="line.color"
                        :opacity="line.opacity"
                      />
                    </svg>
                  </div>

                  <div class="tables-grid">
                    <div>
                      <div class="section-title">
                        <span>{{ t.metrics }}</span>
                        <strong>{{ cpcvResult.metadata.test_name }}</strong>
                      </div>
                      <div class="table-scroll compact-table">
                        <table>
                          <tbody>
                            <tr v-for="row in cpcvResult.report" :key="row.metric">
                              <th>{{ row.metric }}</th>
                              <td>{{ row.value }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div>
                      <div class="section-title">
                        <span>{{ t.cvSummary }}</span>
                        <strong>CPCV</strong>
                      </div>
                      <div class="table-scroll compact-table">
                        <table>
                          <tbody>
                            <tr v-for="row in cpcvResult.cv_summary" :key="row.metric">
                              <th>{{ row.metric }}</th>
                              <td>{{ row.value }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </template>
          </div>
        </section>
      </section>
    </main>
  </div>
</template>
