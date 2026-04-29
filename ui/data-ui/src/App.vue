<script setup lang="ts">
import {
  Activity,
  BarChart3,
  CandlestickChart as CandleIcon,
  Coins,
  Database,
  Globe2,
  RefreshCw,
  Search,
  TrendingUp,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import { getCurrencies, getDividends, getPrices, getStocks } from "./api";
import CandlestickChartPanel from "./components/CandlestickChart.vue";
import { messages } from "./i18n";
import type { Candle, Currency, Dividend, DividendSummary, Locale, Stock, StockFilters } from "./types";

const savedLocale = localStorage.getItem("its-data-locale") as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");
const t = computed(() => messages[locale.value]);

type ViewTab = "quotes" | "dividends" | "instruments" | "currencies";
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
const dividends = ref<Dividend[]>([]);
const dividendsSummary = ref<DividendSummary[]>([]);

const search = ref("");
const classCode = ref("TQBR");
const currencyClassCode = ref("");
const interval = ref("CANDLE_INTERVAL_DAY");
const selectedFigi = ref("");
const startDate = ref(formatDate(addDays(new Date(), -180)));
const endDate = ref(formatDate(new Date()));
const isLoadingStocks = ref(false);
const isLoadingPrices = ref(false);
const isLoadingDividends = ref(false);
const isLoadingCurrencies = ref(false);
const error = ref("");

const orderedCandles = computed(() =>
  [...candles.value].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
);
const selectedStock = computed(() => stocks.value.find((stock) => stock.figi === selectedFigi.value));
const lastCandle = computed(() => orderedCandles.value[orderedCandles.value.length - 1]);
const firstCandle = computed(() => orderedCandles.value[0]);
const selectedTicker = computed(
  () => selectedStock.value?.ticker ?? lastCandle.value?.ticker ?? t.value.empty,
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
    isLoadingDividends.value ||
    isLoadingCurrencies.value,
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

const totalDividendsNet = computed(() =>
  dividendsSummary.value.reduce((sum, d) => sum + Number(d.total_net ?? 0), 0),
);
const totalDividendsCount = computed(() =>
  dividendsSummary.value.reduce((sum, d) => sum + d.count, 0),
);

watch(locale, (value) => localStorage.setItem("its-data-locale", value));

onMounted(async () => {
  await loadStocks();
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
      start_date: startDate.value,
      end_date: endDate.value,
      interval: interval.value,
      is_complete: true,
    });
    candles.value = response.items;
  } catch (err) {
    error.value = formatError(err);
    candles.value = [];
  } finally {
    isLoadingPrices.value = false;
  }
}

function onToolbarChange() {
  if (activeTab.value === "quotes") {
    void loadPrices();
  } else if (activeTab.value === "dividends") {
    void loadDividends();
  } else if (activeTab.value === "currencies") {
    void loadCurrencies();
  }
}

function onSubmitToolbar() {
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

function addDays(date: Date, days: number) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
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

function setActiveTab(tab: ViewTab) {
  activeTab.value = tab;
  if (tab === "quotes" && selectedFigi.value && candles.value.length === 0) {
    void loadPrices();
  } else if (tab === "dividends" && selectedFigi.value && dividends.value.length === 0) {
    void loadDividends();
  } else if (tab === "currencies" && currencies.value.length === 0) {
    void loadCurrencies();
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
      </aside>

      <section class="content">
        <form class="toolbar" @submit.prevent="onSubmitToolbar">
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

          <label v-if="activeTab === 'quotes' || activeTab === 'dividends'" class="control compact">
            <span>{{ t.interval }}</span>
            <select v-model="interval" @change="onToolbarChange">
              <option v-for="item in filters.intervals" :key="item" :value="item">
                {{ item.replace("CANDLE_INTERVAL_", "") }}
              </option>
            </select>
          </label>

          <label v-if="activeTab === 'quotes' || activeTab === 'dividends'" class="control date-control">
            <span>{{ t.from }}</span>
            <input v-model="startDate" type="date" @change="onToolbarChange" />
          </label>

          <label v-if="activeTab === 'quotes' || activeTab === 'dividends'" class="control date-control">
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
        <section v-else class="metrics" :aria-label="t.currencies">
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

        <section class="visual-grid" :class="{ 'full-width': activeTab === 'instruments' || activeTab === 'currencies' }">
          <template v-if="activeTab === 'quotes'">
            <div class="chart-panel">
              <div class="panel-head">
                <div>
                  <span>{{ t.quotes }}</span>
                  <strong>{{ selectedStock?.name ?? selectedTicker }}</strong>
                </div>
                <Activity :size="18" />
              </div>
              <CandlestickChartPanel
                :candles="orderedCandles"
                :interval="interval"
                :locale="locale"
              />
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
                      <th>{{ t.dividendNet }}</th>
                      <th>{{ t.dividendType }}</th>
                      <th>{{ t.closePrice }}</th>
                      <th>{{ t.yieldPercent }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(div, idx) in dividends" :key="idx">
                      <td>{{ formatDateOnly(div.payment_date) }}</td>
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
                    <tr v-for="currencyItem in currencies" :key="currencyItem.figi">
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
  </div>
</template>
