<script setup lang="ts">
import {
  Activity,
  BarChart3,
  CandlestickChart as CandleIcon,
  CircleHelp,
  Coins,
  Database,
  Dices,
  Globe2,
  RefreshCw,
  Rss,
  Search,
  TrendingUp,
  X,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import { getCurrencies, getCustomGoldBars, getDividends, getMonteCarlo, getPrices, getRssItems, getRssSources, getStocks, loadRssItems } from "./api";
import CandlestickChartPanel from "./components/CandlestickChart.vue";
import CloseLineChartPanel from "./components/CloseLineChart.vue";
import MonteCarloPathsChartPanel from "./components/MonteCarloPathsChart.vue";
import { messages } from "./i18n";
import type { Candle, Currency, Dividend, DividendSummary, GoldBarType, Locale, MonteCarloClosePoint, MonteCarloDriftMode, MonteCarloResponse, RssItem, RssLoadResponse, Stock, StockFilters } from "./types";

const savedLocale = localStorage.getItem("its-data-locale") as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");
const t = computed(() => messages[locale.value]);
const docsHref = computed(() => `/docs/?lang=${locale.value}`);

type ViewTab = "quotes" | "dividends" | "instruments" | "currencies" | "rss";
const activeTab = ref<ViewTab>("quotes");

const stocks = ref<Stock[]>([]);
const stockTotal = ref(0);
const filters = ref<StockFilters>({
  class_codes: ["TQBR"],
  exchanges: [],
  sectors: [],
  countries: [],
  intervals: ["CANDLE_INTERVAL_DAY"],
});
const currencies = ref<Currency[]>([]);
const currencyTotal = ref(0);
const currencyFilters = ref<StockFilters>({
  class_codes: [],
  exchanges: [],
  sectors: [],
  countries: [],
  intervals: ["CANDLE_INTERVAL_DAY"],
});
const candles = ref<Candle[]>([]);
const currencyCandles = ref<Candle[]>([]);
const customGoldBars = ref<Candle[]>([]);
const dividends = ref<Dividend[]>([]);
const dividendsSummary = ref<DividendSummary[]>([]);
const rssItems = ref<RssItem[]>([]);
const rssTotal = ref(0);
const rssSources = ref<string[]>([]);
const rssLoadResult = ref<RssLoadResponse | null>(null);
const monteCarloResult = ref<MonteCarloResponse | null>(null);

const search = ref("");
const classCode = ref("TQBR");
const currencyClassCode = ref("");
const interval = ref("CANDLE_INTERVAL_DAY");
const selectedFigi = ref("");
const selectedCurrencyFigi = ref("");
const startDate = ref(formatDate(addDays(new Date(), -180)));
const endDate = ref(formatDate(new Date()));
const rssPubDateFrom = ref("");
const rssPubDateTo = ref("");
const rssTitle = ref("");
const rssText = ref("");
const rssSource = ref("");
const isMonteCarloOpen = ref(false);
const monteCarloStartDate = ref("");
const monteCarloTrainUntil = ref("");
const monteCarloSimulationEnd = ref("");
const monteCarloPathCount = ref(100);
const monteCarloSeed = ref<number | null>(42);
const monteCarloVolatilityScale = ref(1);
const monteCarloDriftMode = ref<MonteCarloDriftMode>("historical");
const goldBarCount = ref(1);
const goldBarType = ref("T_OUNCE_400");
const goldBarTypes = ref<GoldBarType[]>([
  { name: "GRAM", grams: 1 },
  { name: "T_OUNCE", grams: 31.1034768 },
  { name: "KG", grams: 1000 },
  { name: "KG_11", grams: 11000 },
  { name: "T_OUNCE_400", grams: 12441.39072 },
]);
const isLoadingStocks = ref(false);
const isLoadingPrices = ref(false);
const isLoadingCurrencyPrices = ref(false);
const isLoadingCustomGoldBars = ref(false);
const isLoadingDividends = ref(false);
const isLoadingCurrencies = ref(false);
const isLoadingRss = ref(false);
const isUpdatingRss = ref(false);
const isLoadingMonteCarlo = ref(false);
const monteCarloError = ref("");
const error = ref("");

const orderedCandles = computed(() =>
  [...candles.value].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
);
const orderedCurrencyCandles = computed(() =>
  [...currencyCandles.value].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
);
const orderedCustomGoldBars = computed(() =>
  [...customGoldBars.value].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
);
const selectedStock = computed(() => stocks.value.find((stock) => stock.figi === selectedFigi.value));
const selectedCurrency = computed(() => currencies.value.find((currencyItem) => currencyItem.figi === selectedCurrencyFigi.value));
const lastCandle = computed(() => orderedCandles.value[orderedCandles.value.length - 1]);
const firstCandle = computed(() => orderedCandles.value[0]);
const lastCurrencyCandle = computed(() => orderedCurrencyCandles.value[orderedCurrencyCandles.value.length - 1]);
const selectedTicker = computed(
  () => selectedStock.value?.ticker ?? lastCandle.value?.ticker ?? t.value.empty,
);
const selectedCurrencyTicker = computed(
  () => selectedCurrency.value?.ticker ?? lastCurrencyCandle.value?.ticker ?? t.value.empty,
);
const selectedClassCode = computed({
  get: () => (activeTab.value === "currencies" ? currencyClassCode.value : classCode.value),
  set: (value: string) => {
    if (activeTab.value === "currencies") {
      currencyClassCode.value = value;
      return;
    }
    classCode.value = value;
  },
});
const activeClassOptions = computed(() =>
  activeTab.value === "currencies" ? currencyFilters.value.class_codes : filters.value.class_codes,
);
const isBusy = computed(
  () =>
    isLoadingStocks.value ||
    isLoadingPrices.value ||
    isLoadingCurrencyPrices.value ||
    isLoadingCustomGoldBars.value ||
    isLoadingDividends.value ||
    isLoadingCurrencies.value ||
    isLoadingRss.value ||
    isUpdatingRss.value,
);
const priceChangePct = computed(() => {
  if (!firstCandle.value || !lastCandle.value || !firstCandle.value.close) {
    return null;
  }
  return ((lastCandle.value.close - firstCandle.value.close) / firstCandle.value.close) * 100;
});
const totalVolume = computed(() =>
  orderedCandles.value.reduce((sum, candle) => sum + Number(candle.volume ?? 0), 0),
);
const closeLinePoints = computed<MonteCarloClosePoint[]>(() =>
  monteCarloResult.value?.actual.length
    ? monteCarloResult.value.actual
    : orderedCandles.value.map((candle) => ({
        time: candle.time,
        close: candle.close,
        figi: candle.figi,
        ticker: candle.ticker,
      })),
);
const monteCarloCanRun = computed(() => {
  if (
    !selectedFigi.value ||
    !monteCarloStartDate.value ||
    !monteCarloTrainUntil.value ||
    !monteCarloSimulationEnd.value
  ) {
    return false;
  }

  const simulationStart = parseDateInput(monteCarloStartDate.value);
  const trainUntil = parseDateInput(monteCarloTrainUntil.value);
  const simulationEnd = parseDateInput(monteCarloSimulationEnd.value);
  return simulationStart < trainUntil && trainUntil < simulationEnd;
});

const totalDividendsNet = computed(() =>
  dividendsSummary.value.reduce((sum, d) => sum + Number(d.total_net ?? 0), 0),
);
const totalDividendsCount = computed(() =>
  dividendsSummary.value.reduce((sum, d) => sum + d.count, 0),
);

watch(locale, (value) => localStorage.setItem("its-data-locale", value));

onMounted(async () => {
  await Promise.all([loadStocks(), loadRssSources()]);
});

async function loadStocks() {
  isLoadingStocks.value = true;
  error.value = "";
  try {
    const response = await getStocks({
      class_code: classCode.value,
      search: search.value,
      limit: 300,
    });
    stocks.value = response.items;
    stockTotal.value = response.total;
    filters.value = response.filters;

    if (!stocks.value.some((stock) => stock.figi === selectedFigi.value)) {
      selectedFigi.value = stocks.value.find((stock) => stock.ticker === "SBER")?.figi ?? stocks.value[0]?.figi ?? "";
    }

    if (selectedFigi.value) {
      if (activeTab.value === "quotes") {
        await loadPrices();
      } else if (activeTab.value === "dividends") {
        await loadDividends();
      }
    } else {
      candles.value = [];
      dividends.value = [];
    }
  } catch (err) {
    error.value = formatError(err);
    candles.value = [];
    stockTotal.value = 0;
  } finally {
    isLoadingStocks.value = false;
  }
}

async function loadCurrencies() {
  isLoadingCurrencies.value = true;
  error.value = "";
  try {
    const response = await getCurrencies({
      class_code: currencyClassCode.value || undefined,
      search: search.value,
      limit: 300,
    });
    currencies.value = response.items;
    currencyTotal.value = response.total;
    currencyFilters.value = {
      ...currencyFilters.value,
      ...response.filters,
      sectors: [],
    };

    if (!currencies.value.some((currencyItem) => currencyItem.figi === selectedCurrencyFigi.value)) {
      selectedCurrencyFigi.value =
        currencies.value.find((currencyItem) => currencyItem.ticker === "GLDRUB_TOM")?.figi ??
        currencies.value[0]?.figi ??
        "";
    }

    if (selectedCurrencyFigi.value) {
      await loadCurrencyPrices();
    } else {
      currencyCandles.value = [];
    }
  } catch (err) {
    error.value = formatError(err);
    currencies.value = [];
    currencyTotal.value = 0;
  } finally {
    isLoadingCurrencies.value = false;
  }
}

async function loadPrices() {
  if (!selectedFigi.value) {
    candles.value = [];
    return;
  }

  isLoadingPrices.value = true;
  error.value = "";
  try {
    const response = await getPrices({
      figis: [selectedFigi.value],
      class_code: classCode.value,
      instrument_type: "stocks",
      start_date: startDate.value,
      end_date: endDate.value,
      interval: interval.value,
      is_complete: true,
    });
    candles.value = response.items;
    await loadCustomGoldBars();
  } catch (err) {
    error.value = formatError(err);
    candles.value = [];
    customGoldBars.value = [];
  } finally {
    isLoadingPrices.value = false;
  }
}

async function loadCurrencyPrices() {
  if (!selectedCurrencyFigi.value) {
    currencyCandles.value = [];
    return;
  }

  isLoadingCurrencyPrices.value = true;
  error.value = "";
  try {
    const response = await getPrices({
      figis: [selectedCurrencyFigi.value],
      class_code: currencyClassCode.value,
      instrument_type: "currencies",
      start_date: startDate.value,
      end_date: endDate.value,
      interval: interval.value,
      is_complete: true,
    });
    currencyCandles.value = response.items;
  } catch (err) {
    error.value = formatError(err);
    currencyCandles.value = [];
  } finally {
    isLoadingCurrencyPrices.value = false;
  }
}

async function loadCustomGoldBars() {
  if (!selectedFigi.value) {
    customGoldBars.value = [];
    return;
  }

  isLoadingCustomGoldBars.value = true;
  try {
    const response = await getCustomGoldBars({
      figis: [selectedFigi.value],
      class_code: classCode.value,
      instrument_type: "stocks",
      start_date: startDate.value,
      end_date: endDate.value,
      interval: interval.value,
      is_complete: true,
      count: goldBarCount.value,
      bar_type: goldBarType.value,
      gold_ticker: "GLDRUB_TOM",
      gold_class_code: "CETS",
    });
    customGoldBars.value = response.items;
    if (response.meta.gold_bar_types.length) {
      goldBarTypes.value = response.meta.gold_bar_types;
    }
  } catch (err) {
    error.value = formatError(err);
    customGoldBars.value = [];
  } finally {
    isLoadingCustomGoldBars.value = false;
  }
}

function openMonteCarlo() {
  resetMonteCarloDefaults();
  window.scrollTo({ left: 0, top: 0 });
  isMonteCarloOpen.value = true;
  monteCarloError.value = "";
  monteCarloResult.value = null;
  void runMonteCarlo();
}

function closeMonteCarlo() {
  isMonteCarloOpen.value = false;
}

function resetMonteCarloDefaults() {
  const sourceCandles = orderedCandles.value;
  const firstSourceCandle = sourceCandles[0];
  const lastSourceCandle = sourceCandles[sourceCandles.length - 1];
  const fallbackStart = firstSourceCandle ? toDateInput(firstSourceCandle.time) : startDate.value;
  const fallbackEnd = lastSourceCandle ? toDateInput(lastSourceCandle.time) : endDate.value;

  monteCarloStartDate.value = fallbackStart || startDate.value;

  if (sourceCandles.length > 2) {
    const trainIndex = Math.min(
      sourceCandles.length - 2,
      Math.max(1, Math.floor((sourceCandles.length - 1) * 0.72)),
    );
    monteCarloTrainUntil.value = toDateInput(sourceCandles[trainIndex].time);
  } else {
    monteCarloTrainUntil.value = startDate.value;
  }

  monteCarloSimulationEnd.value = endDate.value || fallbackEnd || formatDate(new Date());
  monteCarloPathCount.value = 100;
  monteCarloSeed.value = 42;
  monteCarloVolatilityScale.value = 1;
  monteCarloDriftMode.value = "historical";
}

async function runMonteCarlo() {
  if (!selectedFigi.value || !monteCarloCanRun.value) {
    return;
  }

  isLoadingMonteCarlo.value = true;
  monteCarloError.value = "";
  try {
    monteCarloResult.value = await getMonteCarlo({
      figis: [selectedFigi.value],
      class_code: classCode.value,
      instrument_type: "stocks",
      start_date: monteCarloStartDate.value,
      end_date: monteCarloSimulationEnd.value,
      interval: interval.value,
      is_complete: true,
      train_until_date: monteCarloTrainUntil.value,
      simulation_end_date: monteCarloSimulationEnd.value,
      path_count: monteCarloPathCount.value,
      seed: monteCarloSeed.value,
      volatility_scale: monteCarloVolatilityScale.value,
      drift_mode: monteCarloDriftMode.value,
    });
  } catch (err) {
    monteCarloError.value = formatError(err);
    monteCarloResult.value = null;
  } finally {
    isLoadingMonteCarlo.value = false;
  }
}

function onToolbarChange() {
  if (activeTab.value === "quotes") {
    void loadPrices();
  } else if (activeTab.value === "dividends") {
    void loadDividends();
  } else if (activeTab.value === "currencies") {
    void loadCurrencyPrices();
  }
}

function onSubmitToolbar() {
  if (activeTab.value === "rss") {
    void loadRss();
    return;
  }
  if (activeTab.value === "currencies") {
    void loadCurrencies();
    return;
  }
  void loadStocks();
}

function onClassCodeChange() {
  if (activeTab.value === "currencies") {
    void loadCurrencies();
    return;
  }
  void loadStocks();
}

function selectStock(stock: Stock) {
  selectedFigi.value = stock.figi;
  if (activeTab.value === "quotes") {
    void loadPrices();
  } else if (activeTab.value === "dividends") {
    void loadDividends();
  }
}

function selectCurrency(currencyItem: Currency) {
  selectedCurrencyFigi.value = currencyItem.figi;
  void loadCurrencyPrices();
}

function addDays(date: Date, days: number) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function toDateInput(value: string) {
  const isoDate = value.match(/^\d{4}-\d{2}-\d{2}/)?.[0];
  if (isoDate) {
    return isoDate;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return formatDate(new Date());
  }
  return formatDate(parsed);
}

function parseDateInput(value: string) {
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? Number.NaN : parsed.getTime();
}

function formatError(err: unknown) {
  return err instanceof Error ? err.message : String(err);
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat(locale.value === "ru" ? "ru-RU" : "en-US", {
    maximumFractionDigits: digits,
  }).format(value);
}

function formatPercentValue(value: number | null | undefined, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${formatNumber(value * 100, digits)}%`;
}

function formatDateOnly(dateStr: string | null) {
  if (!dateStr) return "—";
  const parsed = new Date(dateStr);
  if (Number.isNaN(parsed.getTime())) return dateStr;
  return new Intl.DateTimeFormat(locale.value === "ru" ? "ru-RU" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parsed);
}

function formatDateTime(dateStr: string | null) {
  if (!dateStr) return "—";
  const parsed = new Date(dateStr);
  if (Number.isNaN(parsed.getTime())) return dateStr;
  return new Intl.DateTimeFormat(locale.value === "ru" ? "ru-RU" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function formatVolume(value: number) {
  return new Intl.NumberFormat(locale.value === "ru" ? "ru-RU" : "en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatBool(value: boolean | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return value ? t.value.yes : t.value.no;
}

async function loadDividends() {
  if (!selectedFigi.value) {
    dividends.value = [];
    return;
  }

  isLoadingDividends.value = true;
  error.value = "";
  try {
    const response = await getDividends({
      figis: [selectedFigi.value],
      class_code: classCode.value,
      start_date: startDate.value,
      end_date: endDate.value,
    });
    dividends.value = response.items;
    dividendsSummary.value = response.summary;
  } catch (err) {
    error.value = formatError(err);
    dividends.value = [];
  } finally {
    isLoadingDividends.value = false;
  }
}

async function loadRss() {
  isLoadingRss.value = true;
  error.value = "";
  try {
    const response = await getRssItems({
      pub_date_from: rssPubDateFrom.value,
      pub_date_to: rssPubDateTo.value,
      title: rssTitle.value,
      text: rssText.value,
      source: rssSource.value,
      limit: 500,
    });
    rssItems.value = response.items;
    rssTotal.value = response.total;
  } catch (err) {
    error.value = formatError(err);
    rssItems.value = [];
    rssTotal.value = 0;
  } finally {
    isLoadingRss.value = false;
  }
}

async function loadRssSources() {
  try {
    const response = await getRssSources();
    rssSources.value = response.items;
  } catch (err) {
    error.value = formatError(err);
    rssSources.value = [];
  }
}

async function updateRss() {
  isUpdatingRss.value = true;
  error.value = "";
  try {
    rssLoadResult.value = await loadRssItems();
    await loadRss();
  } catch (err) {
    error.value = formatError(err);
  } finally {
    isUpdatingRss.value = false;
  }
}

function setActiveTab(tab: ViewTab) {
  activeTab.value = tab;
  if (tab === "quotes" && selectedFigi.value && candles.value.length === 0) {
    void loadPrices();
  } else if (tab === "dividends" && selectedFigi.value && dividends.value.length === 0) {
    void loadDividends();
  } else if (tab === "currencies" && currencies.value.length === 0) {
    void loadCurrencies();
  } else if (tab === "rss" && rssItems.value.length === 0) {
    if (rssSources.value.length === 0) {
      void loadRssSources();
    }
    void loadRss();
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">
          <Database :size="22" />
        </div>
        <div>
          <strong>{{ t.appTitle }}</strong>
          <span>{{ t.appSubtitle }}</span>
        </div>
      </div>

      <div class="top-actions" :aria-label="t.language">
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
          <button type="button" :class="{ active: locale === 'ru' }" @click="locale = 'ru'">RU</button>
          <button type="button" :class="{ active: locale === 'en' }" @click="locale = 'en'">EN</button>
        </div>
      </div>
    </header>

    <main class="workspace">
      <aside class="source-rail" :aria-label="t.source">
        <button
          class="source-item"
          :class="{ active: activeTab === 'quotes' }"
          type="button"
          @click="setActiveTab('quotes')"
        >
          <CandleIcon :size="18" />
          <span>{{ t.quotes }}</span>
        </button>
        <button
          class="source-item"
          :class="{ active: activeTab === 'dividends' }"
          type="button"
          @click="setActiveTab('dividends')"
        >
          <TrendingUp :size="18" />
          <span>{{ t.dividends }}</span>
        </button>
        <button
          class="source-item"
          :class="{ active: activeTab === 'instruments' }"
          type="button"
          @click="setActiveTab('instruments')"
        >
          <BarChart3 :size="18" />
          <span>{{ t.instruments }}</span>
        </button>
        <button
          class="source-item"
          :class="{ active: activeTab === 'currencies' }"
          type="button"
          @click="setActiveTab('currencies')"
        >
          <Coins :size="18" />
          <span>{{ t.currencies }}</span>
        </button>
        <button
          class="source-item"
          :class="{ active: activeTab === 'rss' }"
          type="button"
          @click="setActiveTab('rss')"
        >
          <Rss :size="18" />
          <span>{{ t.rss }}</span>
        </button>
      </aside>

      <section class="content">
        <form v-if="activeTab === 'rss'" class="toolbar rss-toolbar" @submit.prevent="loadRss">
          <label class="control date-control">
            <span>{{ t.from }}</span>
            <input v-model="rssPubDateFrom" type="date" />
          </label>

          <label class="control date-control">
            <span>{{ t.to }}</span>
            <input v-model="rssPubDateTo" type="date" />
          </label>

          <label class="control">
            <span>{{ t.source }}</span>
            <select v-model="rssSource">
              <option value="">{{ t.all }}</option>
              <option v-for="source in rssSources" :key="source" :value="source">
                {{ source }}
              </option>
              <option v-if="rssSource && !rssSources.includes(rssSource)" :value="rssSource">
                {{ rssSource }}
              </option>
            </select>
          </label>

          <label class="control">
            <span>{{ t.title }}</span>
            <input v-model="rssTitle" type="search" :placeholder="t.title" />
          </label>

          <label class="control">
            <span>{{ t.text }}</span>
            <input v-model="rssText" type="search" :placeholder="t.text" />
          </label>

          <button class="refresh-button" type="submit" :disabled="isLoadingRss || isUpdatingRss">
            <RefreshCw :class="{ spin: isLoadingRss }" :size="17" />
            <span>{{ t.load }}</span>
          </button>

          <button class="refresh-button secondary-button" type="button" :disabled="isLoadingRss || isUpdatingRss" @click="updateRss">
            <RefreshCw :class="{ spin: isUpdatingRss }" :size="17" />
            <span>{{ t.update }}</span>
          </button>
        </form>

        <form v-else class="toolbar" @submit.prevent="onSubmitToolbar">
          <label class="control search-control">
            <span>{{ t.search }}</span>
            <div class="input-shell">
              <Search :size="17" />
              <input v-model="search" type="search" :placeholder="t.searchPlaceholder" />
            </div>
          </label>

          <label class="control compact">
            <span>{{ t.classCode }}</span>
            <select v-model="selectedClassCode" @change="onClassCodeChange">
              <option v-if="activeTab === 'currencies'" value="">{{ t.all }}</option>
              <option v-for="code in activeClassOptions" :key="code" :value="code">{{ code }}</option>
              <option v-if="selectedClassCode && !activeClassOptions.includes(selectedClassCode)" :value="selectedClassCode">
                {{ selectedClassCode }}
              </option>
            </select>
          </label>

          <label v-if="activeTab === 'quotes' || activeTab === 'dividends' || activeTab === 'currencies'" class="control compact">
            <span>{{ t.interval }}</span>
            <select v-model="interval" @change="onToolbarChange">
              <option v-for="item in filters.intervals" :key="item" :value="item">
                {{ item.replace("CANDLE_INTERVAL_", "") }}
              </option>
            </select>
          </label>

          <label v-if="activeTab === 'quotes' || activeTab === 'dividends' || activeTab === 'currencies'" class="control date-control">
            <span>{{ t.from }}</span>
            <input v-model="startDate" type="date" @change="onToolbarChange" />
          </label>

          <label v-if="activeTab === 'quotes' || activeTab === 'dividends' || activeTab === 'currencies'" class="control date-control">
            <span>{{ t.to }}</span>
            <input v-model="endDate" type="date" @change="onToolbarChange" />
          </label>

          <button class="refresh-button" type="submit" :disabled="isBusy">
            <RefreshCw :class="{ spin: isBusy }" :size="17" />
            <span>{{ t.refresh }}</span>
          </button>
        </form>

        <p v-if="error" class="error-banner">{{ error }}</p>

        <section v-if="activeTab === 'quotes' || activeTab === 'dividends'" class="metrics" :aria-label="t.marketData">
          <article class="metric">
            <span>{{ t.selected }}</span>
            <strong>{{ selectedTicker }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.lastPrice }}</span>
            <strong>{{ formatNumber(lastCandle?.close) }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.change }}</span>
            <strong :class="priceChangePct !== null && priceChangePct < 0 ? 'negative' : 'positive'">
              {{ formatNumber(priceChangePct) }}%
            </strong>
          </article>
          <article class="metric">
            <span>{{ t.volume }}</span>
            <strong>{{ formatVolume(totalVolume) }}</strong>
          </article>
        </section>
        <section v-else-if="activeTab === 'instruments'" class="metrics" :aria-label="t.instruments">
          <article class="metric">
            <span>{{ t.instruments }}</span>
            <strong>{{ stockTotal }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.class }}</span>
            <strong>{{ classCode }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.sector }}</span>
            <strong>{{ filters.sectors.length }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.country }}</span>
            <strong>{{ filters.countries.length }}</strong>
          </article>
        </section>
        <section v-else-if="activeTab === 'rss'" class="metrics" :aria-label="t.rss">
          <article class="metric">
            <span>{{ t.records }}</span>
            <strong>{{ rssTotal }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.source }}</span>
            <strong>{{ rssSource || t.all }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.parsed }}</span>
            <strong>{{ rssLoadResult?.parsed_items ?? "—" }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.saved }}</span>
            <strong>{{ rssLoadResult?.saved_items ?? "—" }}</strong>
          </article>
        </section>
        <section v-else-if="activeTab === 'currencies'" class="metrics" :aria-label="t.currencies">
          <article class="metric">
            <span>{{ t.currencies }}</span>
            <strong>{{ currencyTotal }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.class }}</span>
            <strong>{{ currencyClassCode || t.all }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.exchange }}</span>
            <strong>{{ currencyFilters.exchanges.length }}</strong>
          </article>
          <article class="metric">
            <span>{{ t.country }}</span>
            <strong>{{ currencyFilters.countries.length }}</strong>
          </article>
        </section>

        <section class="visual-grid" :class="{ 'full-width': activeTab === 'instruments' || activeTab === 'currencies' || activeTab === 'rss' }">
          <template v-if="activeTab === 'quotes'">
            <div class="quote-chart-stack">
              <div class="chart-panel">
                <div class="panel-head">
                  <div>
                    <span>{{ t.quotes }}</span>
                    <strong>{{ selectedStock?.name ?? selectedTicker }}</strong>
                  </div>
                  <div class="panel-actions">
                    <button
                      class="panel-action-button"
                      type="button"
                      :disabled="orderedCandles.length < 3 || isLoadingPrices"
                      @click="openMonteCarlo"
                    >
                      <Dices :size="16" />
                      <span>{{ t.monteCarlo }}</span>
                    </button>
                    <Activity :size="18" />
                  </div>
                </div>
                <CandlestickChartPanel
                  :candles="orderedCandles"
                  :interval="interval"
                  :locale="locale"
                />
              </div>

              <div class="chart-panel">
                <div class="panel-head custom-panel-head">
                  <div>
                    <span>{{ t.customGoldBar }}</span>
                    <strong>{{ selectedStock?.name ?? selectedTicker }} - GOLD BAR</strong>
                  </div>
                  <div class="custom-controls">
                    <label class="control compact">
                      <span>{{ t.count }}</span>
                      <input v-model.number="goldBarCount" min="1" type="number" @change="loadCustomGoldBars" />
                    </label>
                    <label class="control compact">
                      <span>{{ t.barType }}</span>
                      <select v-model="goldBarType" @change="loadCustomGoldBars">
                        <option v-for="item in goldBarTypes" :key="item.name" :value="item.name">
                          {{ item.name }}
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
                <div v-if="isLoadingCustomGoldBars" class="loading-state">
                  <RefreshCw :class="{ spin: true }" :size="24" />
                  <span>{{ t.loading }}</span>
                </div>
                <CandlestickChartPanel
                  v-else
                  :candles="orderedCustomGoldBars"
                  :interval="interval"
                  :locale="locale"
                />
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'dividends'">
            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.dividends }}</span>
                  <strong>{{ selectedStock?.name ?? selectedTicker }}</strong>
                </div>
                <TrendingUp :size="18" />
              </div>
              <div v-if="isLoadingDividends" class="loading-state">
                <RefreshCw :class="{ spin: true }" :size="24" />
                <span>{{ t.loading }}</span>
              </div>
              <div v-else-if="dividends.length === 0" class="empty-state">
                <span>{{ t.empty }}</span>
              </div>
              <div v-else class="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{{ t.paymentDate }}</th>
                      <th>{{ t.declaredDate }}</th>
                      <th>{{ t.lastBuyDate }}</th>
                      <th>{{ t.dividendNet }}</th>
                      <th>{{ t.dividendType }}</th>
                      <th>{{ t.closePrice }}</th>
                      <th>{{ t.yieldPercent }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(div, idx) in dividends" :key="idx">
                      <td>{{ formatDateOnly(div.payment_date) }}</td>
                      <td>{{ formatDateOnly(div.declared_date) }}</td>
                      <td>{{ formatDateOnly(div.last_buy_date) }}</td>
                      <td>
                        <strong>{{ formatNumber(div.dividend_net) }}</strong>
                      </td>
                      <td>{{ div.dividend_type }}</td>
                      <td>{{ formatNumber(div.close_price) }}</td>
                      <td>{{ formatNumber(div.yield_value, 2) }}%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'instruments'">
            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.instruments }}</span>
                  <strong>{{ stockTotal }}</strong>
                </div>
                <BarChart3 :size="18" />
              </div>
              <div v-if="isLoadingStocks" class="loading-state">
                <RefreshCw :class="{ spin: true }" :size="24" />
                <span>{{ t.loading }}</span>
              </div>
              <div v-else-if="stocks.length === 0" class="empty-state">
                <span>{{ t.empty }}</span>
              </div>
              <div v-else class="table-scroll wide-table">
                <table>
                  <thead>
                    <tr>
                      <th>{{ t.ticker }}</th>
                      <th>{{ t.name }}</th>
                      <th>{{ t.sector }}</th>
                      <th>{{ t.exchange }}</th>
                      <th>{{ t.country }}</th>
                      <th>{{ t.class }}</th>
                      <th>{{ t.lot }}</th>
                      <th>{{ t.status }}</th>
                      <th>{{ t.availability }}</th>
                      <th>{{ t.isin }}</th>
                      <th>{{ t.uid }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="stock in stocks"
                      :key="stock.figi"
                      :class="{ selected: stock.figi === selectedFigi }"
                      @click="selectStock(stock)"
                    >
                      <td>
                        <strong>{{ stock.ticker }}</strong>
                        <small>{{ stock.currency }}</small>
                      </td>
                      <td>{{ stock.name }}</td>
                      <td>{{ stock.sector ?? "—" }}</td>
                      <td>{{ stock.exchange }}</td>
                      <td>{{ stock.country_of_risk_name ?? stock.country_of_risk ?? "—" }}</td>
                      <td>{{ stock.class_code }}</td>
                      <td>{{ stock.lot ?? "—" }}</td>
                      <td>{{ stock.trading_status ?? "—" }}</td>
                      <td>
                        <strong>{{ formatBool(stock.buy_available_flag) }} / {{ formatBool(stock.sell_available_flag) }}</strong>
                        <small>API {{ formatBool(stock.api_trade_available_flag) }}</small>
                      </td>
                      <td>{{ stock.isin ?? "—" }}</td>
                      <td>{{ stock.uid ?? "—" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'rss'">
            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.rss }}</span>
                  <strong>{{ rssTotal }}</strong>
                </div>
                <Rss :size="18" />
              </div>
              <div v-if="isLoadingRss || isUpdatingRss" class="loading-state">
                <RefreshCw :class="{ spin: true }" :size="24" />
                <span>{{ t.loading }}</span>
              </div>
              <div v-else-if="rssItems.length === 0" class="empty-state">
                <span>{{ t.empty }}</span>
              </div>
              <div v-else class="table-scroll wide-table rss-table">
                <table>
                  <thead>
                    <tr>
                      <th>{{ t.pubDate }}</th>
                      <th>{{ t.title }}</th>
                      <th>{{ t.text }}</th>
                      <th>{{ t.source }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in rssItems" :key="`${item.source}-${item.pub_date}-${item.title}`">
                      <td>
                        <strong>{{ formatDateTime(item.pub_date) }}</strong>
                      </td>
                      <td>{{ item.title }}</td>
                      <td class="text-cell">{{ item.text }}</td>
                      <td>{{ item.source }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'currencies'">
            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.currencies }}</span>
                  <strong>{{ currencyTotal }}</strong>
                </div>
                <Coins :size="18" />
              </div>
              <div v-if="isLoadingCurrencies" class="loading-state">
                <RefreshCw :class="{ spin: true }" :size="24" />
                <span>{{ t.loading }}</span>
              </div>
              <div v-else-if="currencies.length === 0" class="empty-state">
                <span>{{ t.empty }}</span>
              </div>
              <div v-else class="table-scroll wide-table">
                <table>
                  <thead>
                    <tr>
                      <th>{{ t.ticker }}</th>
                      <th>{{ t.name }}</th>
                      <th>{{ t.isoCurrency }}</th>
                      <th>{{ t.exchange }}</th>
                      <th>{{ t.country }}</th>
                      <th>{{ t.class }}</th>
                      <th>{{ t.lot }}</th>
                      <th>{{ t.status }}</th>
                      <th>{{ t.availability }}</th>
                      <th>{{ t.weekend }}</th>
                      <th>{{ t.uid }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="currencyItem in currencies"
                      :key="currencyItem.figi"
                      :class="{ selected: currencyItem.figi === selectedCurrencyFigi }"
                      @click="selectCurrency(currencyItem)"
                    >
                      <td>
                        <strong>{{ currencyItem.ticker }}</strong>
                        <small>{{ currencyItem.currency }}</small>
                      </td>
                      <td>{{ currencyItem.name }}</td>
                      <td>{{ currencyItem.iso_currency_name ?? "—" }}</td>
                      <td>{{ currencyItem.exchange }}</td>
                      <td>{{ currencyItem.country_of_risk_name ?? currencyItem.country_of_risk ?? "—" }}</td>
                      <td>{{ currencyItem.class_code }}</td>
                      <td>{{ currencyItem.lot ?? "—" }}</td>
                      <td>{{ currencyItem.trading_status ?? "—" }}</td>
                      <td>
                        <strong>{{ formatBool(currencyItem.buy_available_flag) }} / {{ formatBool(currencyItem.sell_available_flag) }}</strong>
                        <small>API {{ formatBool(currencyItem.api_trade_available_flag) }}</small>
                      </td>
                      <td>{{ formatBool(currencyItem.weekend_flag) }}</td>
                      <td>{{ currencyItem.uid ?? currencyItem.position_uid ?? "—" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.quotes }}</span>
                  <strong>{{ selectedCurrency?.name ?? selectedCurrencyTicker }}</strong>
                </div>
                <Activity :size="18" />
              </div>
              <div v-if="isLoadingCurrencyPrices" class="loading-state">
                <RefreshCw :class="{ spin: true }" :size="24" />
                <span>{{ t.loading }}</span>
              </div>
              <CandlestickChartPanel
                v-else
                :candles="orderedCurrencyCandles"
                :interval="interval"
                :locale="locale"
              />
            </div>
          </template>

          <div v-if="activeTab === 'quotes' || activeTab === 'dividends'" class="instrument-panel">
            <div class="panel-head">
              <div>
                <span>{{ t.instruments }}</span>
                <strong>{{ stockTotal }}</strong>
              </div>
              <BarChart3 :size="18" />
            </div>

            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{{ t.ticker }}</th>
                    <th>{{ t.name }}</th>
                    <th>{{ t.sector }}</th>
                    <th>{{ t.exchange }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="stock in stocks"
                    :key="stock.figi"
                    :class="{ selected: stock.figi === selectedFigi }"
                    @click="selectStock(stock)"
                  >
                    <td>
                      <strong>{{ stock.ticker }}</strong>
                      <small>{{ stock.currency }}</small>
                    </td>
                    <td>{{ stock.name }}</td>
                    <td>{{ stock.sector ?? "—" }}</td>
                    <td>{{ stock.exchange }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </section>
    </main>

    <div v-if="isMonteCarloOpen" class="modal-backdrop" role="dialog" aria-modal="true" @click.self="closeMonteCarlo">
      <section class="monte-carlo-window">
        <header class="modal-head">
          <div>
            <span>{{ t.monteCarloGenerator }}</span>
            <strong>{{ selectedStock?.name ?? selectedTicker }}</strong>
          </div>
          <button class="icon-button" type="button" :aria-label="t.close" @click="closeMonteCarlo">
            <X :size="18" />
          </button>
        </header>

        <div class="monte-carlo-layout">
          <aside class="monte-carlo-controls">
            <form class="monte-carlo-form" @submit.prevent="runMonteCarlo">
              <label class="control">
                <span>{{ t.simulationStart }}</span>
                <input v-model="monteCarloStartDate" type="date" />
              </label>

              <label class="control">
                <span>{{ t.trainingUntil }}</span>
                <input v-model="monteCarloTrainUntil" type="date" />
              </label>

              <label class="control">
                <span>{{ t.simulationUntil }}</span>
                <input v-model="monteCarloSimulationEnd" type="date" />
              </label>

              <label class="control">
                <span>{{ t.paths }}</span>
                <input v-model.number="monteCarloPathCount" min="1" max="500" step="1" type="number" />
              </label>

              <label class="control">
                <span>{{ t.seed }}</span>
                <input v-model.number="monteCarloSeed" type="number" />
              </label>

              <label class="control">
                <span class="label-with-tooltip">
                  {{ t.volatilityScale }}
                  <span class="help-tooltip" :aria-label="t.volatilityScaleHelp" tabindex="0">
                    <CircleHelp :size="14" />
                    <span class="tooltip-content" aria-hidden="true" role="tooltip">{{ t.volatilityScaleHelp }}</span>
                  </span>
                </span>
                <input v-model.number="monteCarloVolatilityScale" min="0" max="10" step="0.1" type="number" />
              </label>

              <label class="control">
                <span>{{ t.driftMode }}</span>
                <select v-model="monteCarloDriftMode">
                  <option value="historical">{{ t.historicalDrift }}</option>
                  <option value="zero">{{ t.zeroDrift }}</option>
                </select>
              </label>

              <button class="refresh-button" type="submit" :disabled="isLoadingMonteCarlo || !monteCarloCanRun">
                <RefreshCw :class="{ spin: isLoadingMonteCarlo }" :size="17" />
                <span>{{ t.runSimulation }}</span>
              </button>
            </form>

            <p v-if="monteCarloError" class="error-banner">{{ monteCarloError }}</p>

            <section v-if="monteCarloResult" class="monte-carlo-stats">
              <article class="modal-stat">
                <span>{{ t.trainingPoints }}</span>
                <strong>{{ monteCarloResult.meta.training_points }}</strong>
              </article>
              <article class="modal-stat">
                <span>{{ t.simulationSteps }}</span>
                <strong>{{ monteCarloResult.meta.simulation_steps }}</strong>
              </article>
              <article class="modal-stat">
                <span>{{ t.meanReturn }}</span>
                <strong>{{ formatPercentValue(monteCarloResult.meta.mean_log_return) }}</strong>
              </article>
              <article class="modal-stat">
                <span>{{ t.volatility }}</span>
                <strong>{{ formatPercentValue(monteCarloResult.meta.scaled_volatility) }}</strong>
              </article>
              <article class="modal-stat">
                <span>{{ t.anchorPrice }}</span>
                <strong>{{ formatNumber(monteCarloResult.meta.anchor_close) }}</strong>
              </article>
            </section>
          </aside>

          <div class="monte-carlo-charts">
            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.actualClose }}</span>
                  <strong>{{ selectedStock?.name ?? selectedTicker }}</strong>
                </div>
                <Activity :size="18" />
              </div>
              <CloseLineChartPanel
                :interval="interval"
                :locale="locale"
                :points="closeLinePoints"
              />
            </div>

            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.simulatedPaths }}</span>
                  <strong>{{ selectedTicker }}</strong>
                </div>
                <Dices :size="18" />
              </div>
              <div v-if="isLoadingMonteCarlo" class="loading-state monte-carlo-loading">
                <RefreshCw :class="{ spin: true }" :size="24" />
                <span>{{ t.loading }}</span>
              </div>
              <MonteCarloPathsChartPanel
                v-else-if="monteCarloResult"
                :interval="interval"
                :locale="locale"
                :paths="monteCarloResult.paths"
                :train-until="monteCarloResult.meta.train_until"
                :training="monteCarloResult.training"
              />
              <div v-else class="empty-state monte-carlo-loading">
                <span>{{ t.empty }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
