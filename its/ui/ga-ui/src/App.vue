<script setup lang="ts">
import {
  Activity,
  Atom,
  Boxes,
  BrainCircuit,
  CandlestickChart,
  Dna,
  Globe2,
  Layers3,
  Play,
  CircleHelp,
  RefreshCw,
  Save,
  Sparkles,
  Trophy,
} from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { getAlphabets, getRun, listRuns, startRun } from "./api";
import type {
  AlphabetGroup,
  AlphabetResponse,
  CandidateRow,
  GenerationSummary,
  GARun,
  GARunSettings,
  GARunSummary,
  Locale,
} from "./types";

const messages = {
  ru: {
    appTitle: "ITS GA Lab",
    appSubtitle: "Среда генерации торговых стратегий генетическими алгоритмами",
    language: "Язык",
    alphabets: "Алфавиты",
    searchSpace: "Пространство поиска",
    settings: "Настройки GA",
    run: "Запустить эволюцию",
    running: "Эволюция идет",
    refresh: "Обновить",
    generations: "Поколения",
    population: "Популяция",
    best: "Лучший",
    mean: "Средний",
    topStrategies: "TOP стратегии",
    materialized: "Материализовано",
    recentRuns: "Запуски",
    noRuns: "Запусков пока нет",
    testName: "Название теста",
    startDate: "Дата начала",
    endDate: "Дата конца",
    interval: "Интервал",
    classCode: "Класс активов",
    testSize: "Размер OOS теста",
    numGenerations: "Поколения",
    solPerPop: "Размер популяции",
    parents: "Родителей",
    mutation: "Мутация",
    selection: "Отбор",
    tournament: "Турнир K",
    keepParents: "Сохранять родителей",
    elitism: "Элита",
    crossover: "Скрещивание",
    mutationType: "Тип мутации",
    stopCriteria: "Stop criteria",
    randomSeed: "Random seed",
    cpcvFolds: "CPCV folds",
    cpcvTestFolds: "CPCV test folds",
    wfTrain: "WF train rows",
    wfTest: "WF test rows",
    wfPurge: "WF purge rows",
    topN: "TOP-N",
    materializeTop: "Создать файлы TOP стратегий",
    evolutionMovie: "Монитор эволюции",
    scoreDynamics: "Динамика score",
    train: "Train",
    test: "Test",
    assets: "Активы",
    evaluated: "Оценено",
    status: "Статус",
    file: "Файл",
    empty: "Пусто",
    wrapper: "Обертка",
    totalScore: "TOTAL",
    wfReturn: "WF Return",
    calmar: "Calmar",
    drawdown: "Drawdown",
    help: "Справка",
  },
  en: {
    appTitle: "ITS GA Lab",
    appSubtitle: "Genetic algorithm workspace for generating trading strategies",
    language: "Language",
    alphabets: "Alphabets",
    searchSpace: "Search space",
    settings: "GA Settings",
    run: "Run evolution",
    running: "Evolution running",
    refresh: "Refresh",
    generations: "Generations",
    population: "Population",
    best: "Best",
    mean: "Mean",
    topStrategies: "TOP strategies",
    materialized: "Materialized",
    recentRuns: "Runs",
    noRuns: "No runs yet",
    testName: "Test name",
    startDate: "Start date",
    endDate: "End date",
    interval: "Interval",
    classCode: "Asset class",
    testSize: "OOS test size",
    numGenerations: "Generations",
    solPerPop: "Population size",
    parents: "Parents",
    mutation: "Mutation",
    selection: "Selection",
    tournament: "Tournament K",
    keepParents: "Keep parents",
    elitism: "Elitism",
    crossover: "Crossover",
    mutationType: "Mutation type",
    stopCriteria: "Stop criteria",
    randomSeed: "Random seed",
    cpcvFolds: "CPCV folds",
    cpcvTestFolds: "CPCV test folds",
    wfTrain: "WF train rows",
    wfTest: "WF test rows",
    wfPurge: "WF purge rows",
    topN: "TOP-N",
    materializeTop: "Create TOP strategy files",
    evolutionMovie: "Evolution monitor",
    scoreDynamics: "Score dynamics",
    train: "Train",
    test: "Test",
    assets: "Assets",
    evaluated: "Evaluated",
    status: "Status",
    file: "File",
    empty: "Empty",
    wrapper: "Wrapper",
    totalScore: "TOTAL",
    wfReturn: "WF Return",
    calmar: "Calmar",
    drawdown: "Drawdown",
    help: "Help",
  },
} satisfies Record<Locale, Record<string, string>>;

const helpMessages = {
  ru: {
    numGenerations: "Сколько поколений пройдет GA. Больше поколений дает больше попыток улучшить стратегии, но увеличивает время расчета.",
    solPerPop: "Сколько стратегий одновременно находится в каждом поколении. Большая популяция шире исследует пространство поиска, но дороже по вычислениям.",
    parents: "Сколько лучших кандидатов используется для создания следующего поколения. Значение не должно превышать размер популяции.",
    mutation: "Вероятность случайного изменения гена стратегии. Низкая мутация сохраняет найденные решения, высокая помогает выходить из локальных максимумов.",
    selection: "tournament: выбирает лучших из случайных групп; sss: steady-state selection, сохраняет сильных кандидатов между поколениями; rank: отбор по рангу, снижает влияние экстремальных score; rws: roulette wheel selection, вероятность выбора пропорциональна fitness.",
    tournament: "Размер случайной группы при tournament-отборе. Чем выше K, тем сильнее давление отбора в пользу лучших стратегий.",
    keepParents: "-1 сохраняет всех родителей, 0 не переносит родителей напрямую, положительное число переносит указанное количество родителей в новое поколение.",
    elitism: "Сколько лучших стратегий гарантированно переносится в следующее поколение без изменений.",
    crossover: "uniform: каждый ген берется у одного из родителей независимо; single_point: обмен генами после одной точки разреза; two_points: обмен сегментом между двумя точками.",
    stopCriteria: "Условие ранней остановки PyGAD. Например saturate_3 завершит поиск, если fitness не улучшается 3 поколения.",
    topN: "Сколько лучших стратегий попадет в итоговый TOP и, если включено, будет материализовано в файлы.",
  },
  en: {
    numGenerations: "How many GA generations to run. More generations give the search more chances to improve strategies, but increase runtime.",
    solPerPop: "How many strategies are evaluated in each generation. A larger population explores the search space wider, but costs more compute.",
    parents: "How many top candidates are used to create the next generation. Must not exceed the population size.",
    mutation: "Probability of randomly changing a strategy gene. Lower mutation preserves found solutions, higher mutation helps escape local maxima.",
    selection: "tournament: picks winners from random groups; sss: steady-state selection, keeps strong candidates across generations; rank: rank-based selection, reduces the impact of extreme scores; rws: roulette wheel selection, pick probability is proportional to fitness.",
    tournament: "Random group size for tournament selection. Higher K increases selection pressure toward the best strategies.",
    keepParents: "-1 keeps all parents, 0 does not copy parents directly, a positive value copies that many parents into the new generation.",
    elitism: "How many best strategies are guaranteed to pass unchanged into the next generation.",
    crossover: "uniform: each gene is independently taken from one parent; single_point: genes are swapped after one split point; two_points: a segment between two points is swapped.",
    stopCriteria: "PyGAD early-stop condition. For example, saturate_3 stops when fitness does not improve for 3 generations.",
    topN: "How many best strategies are included in the final TOP list and, when enabled, materialized into files.",
  },
} satisfies Record<Locale, Record<string, string>>;

const savedLocale = localStorage.getItem("its-ga-locale") as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");
const t = computed(() => messages[locale.value]);
const help = computed(() => helpMessages[locale.value]);
const alphabets = ref<AlphabetResponse | null>(null);
const activeGroupId = ref("pre_selection");
const currentRun = ref<GARun | null>(null);
const runs = ref<GARunSummary[]>([]);
const isLoading = ref(false);
const isRunning = ref(false);
const error = ref("");
let pollTimer: number | null = null;

const settings = ref<GARunSettings>(defaultSettings());
const groups = computed(() => alphabets.value?.groups ?? []);
const activeGroup = computed<AlphabetGroup | undefined>(() =>
  groups.value.find((group) => group.id === activeGroupId.value),
);
const currentGeneration = computed(() => {
  const populations = currentRun.value?.result?.population_scores;
  if (populations?.length) {
    return populations[populations.length - 1];
  }
  const events = currentRun.value?.events.filter((event) => event.population?.length) ?? [];
  if (!events.length) return null;
  const event = events[events.length - 1];
  return {
    generation: event.summary?.generation ?? 0,
    items: event.population ?? [],
  };
});
const generationSummaries = computed(() =>
  currentRun.value?.result?.generation_summaries ??
  currentRun.value?.events
    .map((event) => event.summary)
    .filter((summary): summary is GenerationSummary => Boolean(summary)) ??
  [],
);
const topStrategies = computed(() => currentRun.value?.result?.top_strategies ?? []);
const materialized = computed(() => currentRun.value?.result?.materialized ?? []);
const materializationError = computed(() => currentRun.value?.result?.materialization_error ?? "");
const chartLines = computed(() => buildScoreChart(generationSummaries.value));
const isRunActive = computed(() =>
  currentRun.value?.status === "queued" || currentRun.value?.status === "running" || isRunning.value,
);

watch(locale, (value) => localStorage.setItem("its-ga-locale", value));

onMounted(async () => {
  await refreshAll();
});

onBeforeUnmount(() => {
  stopPolling();
});

async function refreshAll() {
  isLoading.value = true;
  error.value = "";
  try {
    const [alphabetPayload, runPayload] = await Promise.all([getAlphabets(), listRuns()]);
    alphabets.value = alphabetPayload;
    runs.value = runPayload.items;
  } catch (err) {
    error.value = formatError(err);
  } finally {
    isLoading.value = false;
  }
}

async function runGA() {
  isRunning.value = true;
  error.value = "";
  try {
    currentRun.value = await startRun(settings.value);
    startPolling(currentRun.value.run_id);
  } catch (err) {
    error.value = formatError(err);
    isRunning.value = false;
  }
}

async function openRun(runId: string) {
  error.value = "";
  try {
    currentRun.value = await getRun(runId);
    if (currentRun.value.status === "queued" || currentRun.value.status === "running") {
      startPolling(runId);
    }
  } catch (err) {
    error.value = formatError(err);
  }
}

function startPolling(runId: string) {
  stopPolling();
  void pollRun(runId);
  pollTimer = window.setInterval(async () => {
    await pollRun(runId);
  }, 1000);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollRun(runId: string) {
  try {
    currentRun.value = await getRun(runId);
    if (currentRun.value.status === "completed" || currentRun.value.status === "failed") {
      isRunning.value = false;
      stopPolling();
      await refreshAll();
    }
  } catch (err) {
    error.value = formatError(err);
    isRunning.value = false;
    stopPolling();
  }
}

function defaultSettings(): GARunSettings {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 2);
  return {
    test_name: "ga_baseline",
    start_date: toDateInput(start),
    end_date: toDateInput(end),
    interval: "CANDLE_INTERVAL_DAY",
    class_code: "TQBR",
    test_size: 0.33,
    num_generations: 10,
    sol_per_pop: 8,
    num_parents_mating: 4,
    mutation_probability: 0.25,
    parent_selection_type: "tournament",
    k_tournament: 3,
    keep_parents: 0,
    keep_elitism: 1,
    crossover_type: "uniform",
    mutation_type: "random",
    stop_criteria: "saturate_3",
    random_seed: 42,
    cpcv_n_folds: 4,
    cpcv_n_test_folds: 2,
    wf_train_size: 63,
    wf_test_size: 21,
    wf_purged_size: 5,
    top_n: 3,
    materialize_top: true,
  };
}

function toDateInput(value: Date) {
  return value.toISOString().slice(0, 10);
}

function labelForGroup(groupId: string) {
  return {
    pre_selection: "Pre-selection",
    signal: "Signal",
    allocation: "Allocation",
  }[groupId] ?? groupId;
}

function iconForGroup(groupId: string) {
  return {
    pre_selection: Layers3,
    signal: BrainCircuit,
    allocation: Boxes,
  }[groupId] ?? Dna;
}

function formatError(err: unknown) {
  return err instanceof Error ? err.message : String(err);
}

function formatDateTime(value?: string) {
  if (!value) return "—";
  return value.replace("T", " ").replace(/\.\d+.*$/, "");
}

function formatScore(value?: number | null) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function organismStyle(item: CandidateRow, index: number) {
  const score = item.TOTAL_SCORE ?? 0;
  return {
    "--score": `${Math.max(8, Math.min(100, score))}%`,
    "--delay": `${index * 80}ms`,
  };
}

function buildScoreChart(items: Array<{ generation: number; best_total_score: number | null; mean_total_score: number | null }>) {
  if (!items.length) {
    return {
      best: "",
      mean: "",
      labels: [] as Array<{ x: number; text: string }>,
      yTicks: [] as Array<{ y: number; text: string }>,
    };
  }
  const width = 720;
  const height = 220;
  const padLeft = 58;
  const padRight = 34;
  const padY = 34;
  const maxScoreRaw = Math.max(
    100,
    ...items.flatMap((item) => [item.best_total_score ?? 0, item.mean_total_score ?? 0]),
  );
  const maxScore = Math.ceil(maxScoreRaw / 10) * 10;
  const xFor = (index: number) => padLeft + (index / Math.max(1, items.length - 1)) * (width - padLeft - padRight);
  const yFor = (value: number | null) => height - padY - (((value ?? 0) / maxScore) * (height - padY * 2));
  const best = items.map((item, index) => `${xFor(index).toFixed(2)},${yFor(item.best_total_score).toFixed(2)}`).join(" ");
  const mean = items.map((item, index) => `${xFor(index).toFixed(2)},${yFor(item.mean_total_score).toFixed(2)}`).join(" ");
  const labels = items
    .filter((_, index) => index === 0 || index === items.length - 1 || index % Math.ceil(items.length / 4) === 0)
    .map((item, index) => ({ x: xFor(index), text: String(item.generation) }));
  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const value = (maxScore / 4) * index;
    return {
      y: yFor(value),
      text: value.toFixed(0),
    };
  }).reverse();
  return { best, mean, labels, yTicks };
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">
          <Dna :size="23" />
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
        <button class="icon-button" type="button" @click="refreshAll">
          <RefreshCw :class="{ spin: isLoading }" :size="17" />
        </button>
      </div>
    </header>

    <main class="workspace">
      <p v-if="error" class="error-banner">{{ error }}</p>

      <section class="hero-panel">
        <div>
          <span>{{ t.searchSpace }}</span>
          <strong>{{ alphabets?.search_space ?? "—" }}</strong>
          <p>{{ t.appSubtitle }}</p>
        </div>
        <div class="hero-animation" aria-hidden="true">
          <span v-for="i in 18" :key="i" :style="{ '--i': i }"></span>
        </div>
      </section>

      <section class="main-grid">
        <aside class="alphabets-panel">
          <div class="panel-head">
            <div>
              <span>{{ t.alphabets }}</span>
              <strong>{{ t.searchSpace }}: {{ alphabets?.search_space ?? "—" }}</strong>
            </div>
            <Atom :size="18" />
          </div>
          <div class="source-tabs">
            <button
              v-for="group in groups"
              :key="group.id"
              type="button"
              :class="{ active: activeGroupId === group.id }"
              @click="activeGroupId = group.id"
            >
              <component :is="iconForGroup(group.id)" :size="17" />
              <span>{{ labelForGroup(group.id) }}</span>
              <small>{{ group.count }}</small>
            </button>
          </div>
          <div class="gene-list">
            <article v-for="gene in activeGroup?.items ?? []" :key="gene.id" class="gene-card">
              <div>
                <strong>{{ gene.title }}</strong>
                <span>{{ gene.id }}</span>
              </div>
              <p>{{ gene.description }}</p>
              <code>{{ gene.component_path || gene.factory_path || "—" }}</code>
              <small v-if="gene.wrapper_path" class="gene-meta">{{ t.wrapper }}: {{ gene.wrapper_path }}</small>
            </article>
          </div>
        </aside>

        <section class="control-panel">
          <div class="panel-head">
            <div>
              <span>{{ t.settings }}</span>
              <strong>{{ settings.test_name }}</strong>
            </div>
            <CandlestickChart :size="18" />
          </div>
          <div class="form-grid">
            <label><span>{{ t.testName }}</span><input v-model="settings.test_name" type="text" /></label>
            <label><span>{{ t.startDate }}</span><input v-model="settings.start_date" type="date" /></label>
            <label><span>{{ t.endDate }}</span><input v-model="settings.end_date" type="date" /></label>
            <label>
              <span>{{ t.interval }}</span>
              <select v-model="settings.interval">
                <option value="CANDLE_INTERVAL_DAY">Day</option>
                <option value="CANDLE_INTERVAL_HOUR">Hour</option>
                <option value="CANDLE_INTERVAL_WEEK">Week</option>
                <option value="CANDLE_INTERVAL_MONTH">Month</option>
              </select>
            </label>
            <label><span>{{ t.classCode }}</span><input v-model="settings.class_code" type="text" /></label>
            <label><span>{{ t.testSize }}</span><input v-model.number="settings.test_size" min="0.05" max="0.8" step="0.01" type="number" /></label>
            <label>
              <span class="field-label">
                {{ t.numGenerations }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.numGenerations}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.numGenerations }}</span>
                </span>
              </span>
              <input v-model.number="settings.num_generations" min="1" max="100" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.solPerPop }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.solPerPop}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.solPerPop }}</span>
                </span>
              </span>
              <input v-model.number="settings.sol_per_pop" min="2" max="80" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.parents }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.parents}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.parents }}</span>
                </span>
              </span>
              <input v-model.number="settings.num_parents_mating" min="1" max="80" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.mutation }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.mutation}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.mutation }}</span>
                </span>
              </span>
              <input v-model.number="settings.mutation_probability" min="0" max="1" step="0.01" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.selection }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.selection}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.selection }}</span>
                </span>
              </span>
              <select v-model="settings.parent_selection_type">
                <option value="tournament">tournament</option>
                <option value="sss">sss</option>
                <option value="rank">rank</option>
                <option value="rws">rws</option>
              </select>
            </label>
            <label>
              <span class="field-label">
                {{ t.tournament }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.tournament}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.tournament }}</span>
                </span>
              </span>
              <input v-model.number="settings.k_tournament" min="2" max="20" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.keepParents }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.keepParents}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.keepParents }}</span>
                </span>
              </span>
              <input v-model.number="settings.keep_parents" min="-1" max="20" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.elitism }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.elitism}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.elitism }}</span>
                </span>
              </span>
              <input v-model.number="settings.keep_elitism" min="0" max="20" type="number" />
            </label>
            <label>
              <span class="field-label">
                {{ t.crossover }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.crossover}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.crossover }}</span>
                </span>
              </span>
              <select v-model="settings.crossover_type">
                <option value="uniform">uniform</option>
                <option value="single_point">single_point</option>
                <option value="two_points">two_points</option>
              </select>
            </label>
            <label>
              <span class="field-label">
                {{ t.stopCriteria }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.stopCriteria}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.stopCriteria }}</span>
                </span>
              </span>
              <input v-model="settings.stop_criteria" type="text" />
            </label>
            <label><span>{{ t.randomSeed }}</span><input v-model.number="settings.random_seed" type="number" /></label>
            <label><span>{{ t.cpcvFolds }}</span><input v-model.number="settings.cpcv_n_folds" min="3" max="30" type="number" /></label>
            <label><span>{{ t.cpcvTestFolds }}</span><input v-model.number="settings.cpcv_n_test_folds" min="2" max="29" type="number" /></label>
            <label><span>{{ t.wfTrain }}</span><input v-model.number="settings.wf_train_size" min="2" max="1000" type="number" /></label>
            <label><span>{{ t.wfTest }}</span><input v-model.number="settings.wf_test_size" min="1" max="500" type="number" /></label>
            <label><span>{{ t.wfPurge }}</span><input v-model.number="settings.wf_purged_size" min="0" max="250" type="number" /></label>
            <label>
              <span class="field-label">
                {{ t.topN }}
                <span class="help-hint" tabindex="0" :aria-label="`${t.help}: ${t.topN}`">
                  <CircleHelp :size="14" />
                  <span class="help-tooltip">{{ help.topN }}</span>
                </span>
              </span>
              <input v-model.number="settings.top_n" min="1" max="10" type="number" />
            </label>
          </div>
          <label class="checkbox-row">
            <input v-model="settings.materialize_top" type="checkbox" />
            <span>{{ t.materializeTop }}</span>
          </label>
          <button class="primary-button" type="button" :disabled="isRunActive" @click="runGA">
            <RefreshCw v-if="isRunActive" class="spin" :size="17" />
            <Play v-else :size="17" />
            {{ isRunActive ? t.running : t.run }}
          </button>
        </section>
      </section>

      <section class="evolution-grid">
        <div class="movie-panel">
          <div class="panel-head">
            <div>
              <span>{{ t.evolutionMovie }}</span>
              <strong>{{ t.generations }} {{ currentGeneration?.generation ?? "—" }}</strong>
            </div>
            <Sparkles :size="18" />
          </div>
          <div class="organism-stage">
            <article
              v-for="(item, index) in currentGeneration?.items ?? []"
              :key="`${currentGeneration?.generation}-${item.strategy_name}-${index}`"
              class="organism"
              :style="organismStyle(item, index)"
            >
              <div class="organism-core"></div>
              <strong>{{ item.strategy_name }}</strong>
              <span>{{ item.selector_name }}</span>
              <small>{{ item.signal_name }} / {{ item.allocation_name }}</small>
              <dl class="organism-metrics">
                <div>
                  <dt>{{ t.totalScore }}</dt>
                  <dd>{{ formatScore(item.TOTAL_SCORE) }}</dd>
                </div>
                <div>
                  <dt>{{ t.wfReturn }}</dt>
                  <dd>{{ formatPercent(item.WF_Return) }}</dd>
                </div>
                <div>
                  <dt>{{ t.calmar }}</dt>
                  <dd>{{ formatScore(item.WF_Calmar) }}</dd>
                </div>
                <div>
                  <dt>{{ t.drawdown }}</dt>
                  <dd>{{ formatPercent(item.WF_Max_Drawdown_Abs) }}</dd>
                </div>
              </dl>
            </article>
            <div v-if="!currentGeneration" class="empty-state">{{ t.empty }}</div>
          </div>
        </div>

        <div class="chart-panel">
          <div class="panel-head">
            <div>
              <span>{{ t.scoreDynamics }}</span>
              <strong>{{ currentRun?.status ?? "—" }}</strong>
            </div>
            <Activity :size="18" />
          </div>
          <svg class="score-chart" viewBox="0 0 720 220" role="img">
            <text class="axis-title" x="18" y="105" text-anchor="middle" transform="rotate(-90 18 105)">Score</text>
            <g v-for="tick in chartLines.yTicks" :key="tick.text">
              <line class="grid-line" x1="58" :y1="tick.y" x2="686" :y2="tick.y" />
              <text class="y-label" x="48" :y="tick.y + 4" text-anchor="end">{{ tick.text }}</text>
            </g>
            <line x1="58" y1="186" x2="686" y2="186" />
            <line x1="58" y1="34" x2="58" y2="186" />
            <polyline :points="chartLines.mean" class="mean-line" />
            <polyline :points="chartLines.best" class="best-line" />
            <text v-for="label in chartLines.labels" :key="label.text" :x="label.x" y="208" text-anchor="middle">{{ label.text }}</text>
          </svg>
          <div class="chart-legend">
            <span><i class="best-dot"></i>{{ t.best }}</span>
            <span><i class="mean-dot"></i>{{ t.mean }}</span>
          </div>
        </div>
      </section>

      <section class="result-grid">
        <div class="table-panel">
          <div class="panel-head">
            <div>
              <span>{{ t.topStrategies }}</span>
              <strong>{{ topStrategies.length }}</strong>
            </div>
            <Trophy :size="18" />
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Strategy</th>
                  <th>TOTAL_SCORE</th>
                  <th>WF Return</th>
                  <th>WF Calmar</th>
                  <th>Drawdown</th>
                  <th>Breadth</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in topStrategies" :key="row.strategy_name">
                  <td><strong>{{ index + 1 }}</strong></td>
                  <td>
                    <strong>{{ row.strategy_name }}</strong>
                    <small>{{ row.selector_name }} / {{ row.signal_name }} / {{ row.allocation_name }}</small>
                  </td>
                  <td>{{ formatScore(row.TOTAL_SCORE) }}</td>
                  <td>{{ formatPercent(row.WF_Return) }}</td>
                  <td>{{ formatScore(row.WF_Calmar) }}</td>
                  <td>{{ formatPercent(row.WF_Max_Drawdown_Abs) }}</td>
                  <td>{{ formatScore(row.WF_Mean_Active_Assets) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="side-stack">
          <section class="table-panel">
            <div class="panel-head">
              <div>
                <span>{{ t.materialized }}</span>
                <strong>{{ materialized.length }}</strong>
              </div>
              <Save :size="18" />
            </div>
            <div class="saved-list">
              <article v-for="item in materialized" :key="item.class_name" class="saved-card">
                <strong>{{ item.class_name }}</strong>
                <small>{{ item.file_path }}</small>
              </article>
              <div v-if="materializationError" class="small-state">{{ materializationError }}</div>
              <div v-if="!materialized.length" class="small-state">{{ t.empty }}</div>
            </div>
          </section>

          <section class="table-panel">
            <div class="panel-head">
              <div>
                <span>{{ t.recentRuns }}</span>
                <strong>{{ runs.length }}</strong>
              </div>
              <RefreshCw :size="18" />
            </div>
            <div class="saved-list">
              <article v-for="run in runs.slice(0, 8)" :key="run.run_id" class="saved-card clickable" @click="openRun(run.run_id)">
                <strong>{{ run.test_name }} / {{ run.status }}</strong>
                <small>{{ formatDateTime(run.created_at) }} · {{ formatScore(run.best_score) }}</small>
              </article>
              <div v-if="!runs.length" class="small-state">{{ t.noRuns }}</div>
            </div>
          </section>
        </div>
      </section>
    </main>
  </div>
</template>
