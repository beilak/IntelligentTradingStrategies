<script setup lang="ts">
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Boxes,
  CandlestickChart,
  DatabaseZap,
  Dna,
  Globe2,
  Layers3,
  LineChart,
  Play,
  ShieldCheck,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";

type Locale = "ru" | "en";

const savedLocale = localStorage.getItem("its-launchpad-locale") as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");

const messages = {
  ru: {
    appTitle: "ITS Launchpad",
    appSubtitle: "Единая точка запуска рабочих интерфейсов",
    language: "Язык",
    open: "Открыть",
    ready: "Готово",
    dataTitle: "Данные рынка",
    dataSubtitle: "Котировки, инструменты, дивиденды и источники данных",
    dataBody: "Быстрый просмотр T-Invest/MOEX данных, свечей, объемов и справочников бумаг.",
    strategyTitle: "Ядро стратегий",
    strategySubtitle: "Компоненты моделей, CPCV, WalkForward и Backtesting",
    strategyBody: "Рабочая зона модельера: registry компонентов, состав стратегии и отчеты тестирования.",
    gaTitle: "GA генератор",
    gaSubtitle: "Генетические алгоритмы для поиска стратегий",
    gaBody: "Алфавиты компонентов, эволюционный запуск, визуализация поколений и материализация TOP-3 стратегий.",
    observabilityTitle: "Контроль системы",
    observabilitySubtitle: "Состояние сервисов и маршрутов",
    observabilityBody: "Health endpoints, gateway routes и базовая навигация по контейнерам.",
    roadmapTitle: "Следующие интерфейсы",
    roadmapSubtitle: "Место для новых UI",
    roadmapBody: "Сюда можно добавить риск-панель, execution, portfolio monitor или research notebooks.",
    statusData: "Data backend",
    statusStrategy: "Strategy backend",
    stack: "VueJS / FastAPI / Docker",
  },
  en: {
    appTitle: "ITS Launchpad",
    appSubtitle: "One place to open every working interface",
    language: "Language",
    open: "Open",
    ready: "Ready",
    dataTitle: "Market Data",
    dataSubtitle: "Quotes, instruments, dividends, and data sources",
    dataBody: "Fast access to T-Invest/MOEX candles, volumes, instruments, and reference data.",
    strategyTitle: "Strategy Core",
    strategySubtitle: "Model components, CPCV, WalkForward, and Backtesting",
    strategyBody: "Modeler workspace: component registry, strategy composition, and testing reports.",
    gaTitle: "GA Generator",
    gaSubtitle: "Genetic algorithms for strategy search",
    gaBody: "Component alphabets, evolutionary runs, generation visualization, and TOP-3 materialization.",
    observabilityTitle: "System Control",
    observabilitySubtitle: "Service and route status",
    observabilityBody: "Health endpoints, gateway routes, and basic navigation across containers.",
    roadmapTitle: "Next Interfaces",
    roadmapSubtitle: "Space for upcoming UI modules",
    roadmapBody: "Add risk dashboards, execution, portfolio monitoring, or research notebooks here.",
    statusData: "Data backend",
    statusStrategy: "Strategy backend",
    stack: "VueJS / FastAPI / Docker",
  },
} satisfies Record<Locale, Record<string, string>>;

const t = computed(() => messages[locale.value]);

const tiles = computed(() => [
  {
    id: "data",
    title: t.value.dataTitle,
    subtitle: t.value.dataSubtitle,
    body: t.value.dataBody,
    href: "/data/",
    icon: CandlestickChart,
    accent: "#66d9ef",
    metrics: ["Stocks", "Candles", "Dividends"],
  },
  {
    id: "strategies",
    title: t.value.strategyTitle,
    subtitle: t.value.strategySubtitle,
    body: t.value.strategyBody,
    href: "/strategies/",
    icon: Boxes,
    accent: "#ffcc66",
    metrics: ["Registry", "CPCV", "Backtest"],
  },
  {
    id: "ga",
    title: t.value.gaTitle,
    subtitle: t.value.gaSubtitle,
    body: t.value.gaBody,
    href: "/ga/",
    icon: Dna,
    accent: "#aee9d1",
    metrics: ["Alphabets", "PyGAD", "TOP-3"],
  },
  {
    id: "system",
    title: t.value.observabilityTitle,
    subtitle: t.value.observabilitySubtitle,
    body: t.value.observabilityBody,
    href: "/health",
    icon: Activity,
    accent: "#aee9d1",
    metrics: [t.value.statusData, t.value.statusStrategy],
  },
  {
    id: "roadmap",
    title: t.value.roadmapTitle,
    subtitle: t.value.roadmapSubtitle,
    body: t.value.roadmapBody,
    href: "#",
    icon: Layers3,
    accent: "#b48cf2",
    metrics: ["Risk", "Execution", "Monitor"],
  },
]);

watch(locale, (value) => localStorage.setItem("its-launchpad-locale", value));
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
          <span>{{ t.stack }}</span>
        </div>
      </div>

      <div class="top-actions" :aria-label="t.language">
        <Globe2 :size="18" />
        <div class="segmented">
          <button type="button" :class="{ active: locale === 'ru' }" @click="locale = 'ru'">RU</button>
          <button type="button" :class="{ active: locale === 'en' }" @click="locale = 'en'">EN</button>
        </div>
      </div>
    </header>

    <main class="workspace">
      <section class="hero">
        <div class="hero-copy">
          <span class="eyebrow">
            <ShieldCheck :size="16" />
            {{ t.ready }}
          </span>
          <h1>{{ t.appTitle }}</h1>
          <p>{{ t.appSubtitle }}</p>
        </div>
        <div class="hero-signal" aria-hidden="true">
          <LineChart :size="44" />
          <div class="bars">
            <span style="height: 32%"></span>
            <span style="height: 54%"></span>
            <span style="height: 42%"></span>
            <span style="height: 76%"></span>
            <span style="height: 62%"></span>
            <span style="height: 86%"></span>
          </div>
        </div>
      </section>

      <section class="tile-grid">
        <a
          v-for="tile in tiles"
          :key="tile.id"
          class="launch-tile"
          :href="tile.href"
          :class="{ muted: tile.href === '#' }"
          :style="{ '--accent': tile.accent }"
        >
          <div class="tile-head">
            <div class="tile-icon">
              <component :is="tile.icon" :size="24" />
            </div>
            <ArrowUpRight v-if="tile.href !== '#'" class="open-icon" :size="20" />
          </div>

          <div class="tile-content">
            <span>{{ tile.subtitle }}</span>
            <strong>{{ tile.title }}</strong>
            <p>{{ tile.body }}</p>
          </div>

          <div class="tile-footer">
            <small v-for="metric in tile.metrics" :key="metric">{{ metric }}</small>
          </div>

          <button v-if="tile.href !== '#'" class="tile-action" type="button">
            <Play :size="15" />
            {{ t.open }}
          </button>
        </a>
      </section>

      <section class="status-strip">
        <article>
          <BarChart3 :size="18" />
          <span>{{ t.statusData }}</span>
        </article>
        <article>
          <Boxes :size="18" />
          <span>{{ t.statusStrategy }}</span>
        </article>
      </section>
    </main>
  </div>
</template>
