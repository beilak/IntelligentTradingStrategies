<script setup lang="ts">
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  BarChart3,
  BriefcaseBusiness,
  CircleHelp,
  ClipboardCheck,
  Home,
  Landmark,
  Link2,
  Loader2,
  LogOut,
  Play,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Trash2,
  X,
  WalletCards,
} from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  accessTokenForWebSocket,
  clearAuthTokens,
  createOrder,
  createStopOrder,
  assignExecutionStrategy,
  getAccounts,
  getCurrentUser,
  getExecutionStrategies,
  getLastPrice,
  getOverview,
  getPrices,
  getTradableInstruments,
  runExecutionStrategy,
  unassignExecutionStrategy,
} from "./api";
import AllocationBarChart from "./components/AllocationBarChart.vue";
import AllocationChart from "./components/AllocationChart.vue";
import OrderBookPanel from "./components/OrderBookPanel.vue";
import TicketCandlestickChart from "./components/TicketCandlestickChart.vue";
import OperationsCashflowChart from "./components/OperationsCashflowChart.vue";
import StrategyPlanChart from "./components/StrategyPlanChart.vue";
import { MARKET_TIME_ZONE, formatMarketDateInput } from "./marketTime";
import type {
  AccountItem,
  AccountOverview,
  Candle,
  ExecutionStrategiesResponse,
  ExecutionStrategyAssignment,
  ExecutionStrategyItem,
  InstrumentsResponse,
  MoneyAmount,
  OperationItem,
  OrderBookSnapshot,
  OrderTicket,
  PortfolioPosition,
  StopOrderTicket,
  StrategyRunRequest,
  StrategyRunResult,
  StubResponse,
  TradableInstrument,
  User,
} from "./types";

const docsHref = "/docs/?lang=ru";
const authHref = "/tech/auth/?returnTo=/execution/";
const executionApiBase = import.meta.env.VITE_EXECUTION_API_BASE ?? "/api/execution";

const chartIntervals = [
  { value: "CANDLE_INTERVAL_1_MIN", label: "1m", days: 1 },
  { value: "CANDLE_INTERVAL_5_MIN", label: "5m", days: 5 },
  { value: "CANDLE_INTERVAL_15_MIN", label: "15m", days: 14 },
  { value: "CANDLE_INTERVAL_HOUR", label: "1h", days: 60 },
  { value: "CANDLE_INTERVAL_DAY", label: "1d", days: 365 },
  { value: "CANDLE_INTERVAL_WEEK", label: "1w", days: 1825 },
  { value: "CANDLE_INTERVAL_MONTH", label: "1M", days: 3650 },
];

type OrderBookStatus = "idle" | "connecting" | "live" | "stale" | "error";

const user = ref<User | null>(null);
const isCheckingAuth = ref(true);
const isLoadingAccounts = ref(false);
const isLoadingOverview = ref(false);
const isSubmittingOrder = ref(false);
const isSubmittingStop = ref(false);
const error = ref("");
const accounts = ref<AccountItem[]>([]);
const selectedAccountId = ref("");
const overview = ref<AccountOverview | null>(null);
const operationsDays = ref(30);
const activeTicket = ref<"order" | "stop">("order");
const latestStub = ref<StubResponse | null>(null);
const selectedInstrument = ref<TradableInstrument | null>(null);
const isInstrumentPickerOpen = ref(false);
const isStrategyModalOpen = ref(false);
const isLoadingStrategies = ref(false);
const isAssigningStrategy = ref(false);
const isRunningStrategy = ref(false);
const strategyError = ref("");
const strategyAssignments = ref<ExecutionStrategyAssignment[]>([]);
const availableStrategies = ref<ExecutionStrategyItem[]>([]);
const strategyTotal = ref(0);
const selectedStrategyName = ref("");
const strategyAssignComment = ref("");
const strategyRunResult = ref<StrategyRunResult | null>(null);
const strategyRunSettings = ref<StrategyRunRequest>({
  start_date: formatDateInput(addDays(new Date(), -365)),
  end_date: formatDateInput(new Date()),
  interval: "CANDLE_INTERVAL_DAY",
  class_code: "TQBR",
  order_type: "limit",
  limit_offset_pct: 0.001,
  min_order_value: 100,
});
const isLoadingInstruments = ref(false);
const instrumentError = ref("");
const instrumentSearch = ref("");
const instrumentTypeFilter = ref("");
const instrumentClassCode = ref("");
const instrumentExchange = ref("");
const instrumentCurrency = ref("");
const instruments = ref<TradableInstrument[]>([]);
const instrumentTotal = ref(0);
const instrumentFilters = ref<InstrumentsResponse["filters"]>({
  instrument_types: [],
  class_codes: [],
  exchanges: [],
  currencies: [],
  intervals: [],
});
const candles = ref<Candle[]>([]);
const isLoadingCandles = ref(false);
const chartError = ref("");
const chartInterval = ref("CANDLE_INTERVAL_DAY");
const chartEndDate = ref(formatDateInput(new Date()));
const chartStartDate = ref(formatDateInput(addDays(new Date(), -365)));
const orderBook = ref<OrderBookSnapshot | null>(null);
const orderBookStatus = ref<OrderBookStatus>("idle");
const orderBookError = ref("");

let instrumentLoadRequest = 0;
let orderBookSocket: WebSocket | null = null;
let orderBookNoDataTimer: number | undefined;
let orderBookStaleTimer: number | undefined;

const orderTicket = ref<OrderTicket>({
  instrument_id: "",
  figi: "",
  side: "buy",
  order_type: "limit",
  quantity: 1,
  price: null,
  price_type: "currency",
  time_in_force: "day",
  client_order_id: "",
  comment: "",
});

const stopTicket = ref<StopOrderTicket>({
  instrument_id: "",
  figi: "",
  side: "sell",
  stop_order_type: "stop_loss",
  quantity: 1,
  stop_price: 0,
  limit_price: null,
  price_type: "currency",
  expire_at: null,
  client_order_id: "",
  comment: "",
});

const selectedAccount = computed(() =>
  accounts.value.find((account) => account.id === selectedAccountId.value) ?? null,
);

const summary = computed(() => overview.value?.summary ?? null);
const portfolioPositions = computed<PortfolioPosition[]>(
  () => overview.value?.sections.portfolio?.positions ?? [],
);
const securities = computed(() => overview.value?.sections.positions?.securities ?? []);
const moneyRows = computed(() => overview.value?.summary.money ?? []);
const blockedMoneyRows = computed(() => overview.value?.summary.blocked_money ?? []);
const orders = computed(() => overview.value?.sections.orders?.orders ?? []);
const stopOrders = computed(() => overview.value?.sections.stop_orders?.stop_orders ?? []);
const operations = computed<OperationItem[]>(() =>
  [...(overview.value?.sections.operations?.operations ?? [])].sort(
    (a, b) => new Date(b.date ?? 0).getTime() - new Date(a.date ?? 0).getTime(),
  ),
);
const sectionErrorRows = computed(() => Object.entries(overview.value?.section_errors ?? {}));
const totalCash = computed(() => moneyRows.value.reduce((sum, item) => sum + Number(item.value ?? 0), 0));
const availableAccounts = computed(() => accounts.value.filter((account) => account.is_available));
const primaryCurrency = computed(
  () =>
    summary.value?.total_amount_portfolio?.currency ??
    moneyRows.value.find((item) => item.currency)?.currency ??
    "rub",
);
const selectedInstrumentId = computed(() =>
  selectedInstrument.value ? instrumentIdFor(selectedInstrument.value) : orderTicket.value.instrument_id,
);
const selectedInstrumentLabel = computed(() => {
  const instrument = selectedInstrument.value;
  if (!instrument) return "Инструмент не выбран";
  return `${instrument.ticker || instrument.figi} / ${instrument.name || instrument.figi}`;
});
const submissionModeLabel = computed(() =>
  overview.value?.order_submission_mode === "stub" ? "Stub mode" : "Live mode",
);
const submitOrderLabel = computed(() =>
  overview.value?.order_submission_mode === "stub" ? "Создать stub" : "Отправить приказ",
);
const submitStopOrderLabel = computed(() =>
  overview.value?.order_submission_mode === "stub" ? "Создать stub" : "Отправить стоп",
);
const selectedStrategyAssignment = computed(() =>
  strategyAssignments.value.find((item) => item.strategy_name === selectedStrategyName.value) ?? null,
);
const selectedAvailableStrategy = computed(() =>
  availableStrategies.value.find((item) => item.name === selectedStrategyName.value) ?? null,
);
const assignedStrategyNames = computed(() =>
  new Set(strategyAssignments.value.map((item) => item.strategy_name)),
);

watch(
  () => orderTicket.value.order_type,
  (orderType) => {
    if (orderType === "market") {
      orderTicket.value.price = null;
    }
  },
);

onMounted(async () => {
  await requireAuth();
  if (user.value) {
    await loadAccounts();
  }
});

onBeforeUnmount(() => {
  disconnectOrderBook("idle");
});

async function requireAuth() {
  isCheckingAuth.value = true;
  const currentUser = await getCurrentUser();
  if (!currentUser) {
    clearAuthTokens();
    window.location.replace(authHref);
    return;
  }
  user.value = currentUser;
  isCheckingAuth.value = false;
}

async function loadAccounts() {
  isLoadingAccounts.value = true;
  error.value = "";
  try {
    const response = await getAccounts();
    accounts.value = response.items;
    const currentStillExists = accounts.value.some((account) => account.id === selectedAccountId.value);
    if (!currentStillExists) {
      selectedAccountId.value = availableAccounts.value[0]?.id ?? accounts.value[0]?.id ?? "";
    }
    if (selectedAccountId.value) {
      await loadOverview();
    }
  } catch (cause) {
    error.value = errorMessage(cause);
  } finally {
    isLoadingAccounts.value = false;
  }
}

async function loadOverview() {
  if (!selectedAccountId.value) return;
  isLoadingOverview.value = true;
  error.value = "";
  try {
    overview.value = await getOverview(selectedAccountId.value, operationsDays.value);
  } catch (cause) {
    error.value = errorMessage(cause);
    overview.value = null;
  } finally {
    isLoadingOverview.value = false;
  }
}

async function selectAccount(account: AccountItem) {
  if (!account.is_available) return;
  selectedAccountId.value = account.id;
  await loadOverview();
  if (isStrategyModalOpen.value) {
    await loadExecutionStrategies();
  }
}

async function openInstrumentPicker() {
  isInstrumentPickerOpen.value = true;
  if (!instruments.value.length) {
    await loadInstruments();
  }
}

async function loadInstruments() {
  const requestId = ++instrumentLoadRequest;
  isLoadingInstruments.value = true;
  instrumentError.value = "";
  try {
    const response = await getTradableInstruments({
      search: instrumentSearch.value,
      instrument_types: instrumentTypeFilter.value ? [instrumentTypeFilter.value] : undefined,
      class_code: instrumentClassCode.value,
      exchange: instrumentExchange.value,
      currency: instrumentCurrency.value,
      api_trade_available: true,
      limit: 150,
      offset: 0,
    });
    if (requestId !== instrumentLoadRequest) return;
    instruments.value = response.items;
    instrumentTotal.value = response.total;
    instrumentFilters.value = response.filters;
  } catch (cause) {
    if (requestId === instrumentLoadRequest) {
      instrumentError.value = errorMessage(cause);
      instruments.value = [];
      instrumentTotal.value = 0;
    }
  } finally {
    if (requestId === instrumentLoadRequest) {
      isLoadingInstruments.value = false;
    }
  }
}

async function openStrategyModal() {
  isStrategyModalOpen.value = true;
  strategyError.value = "";
  await loadExecutionStrategies();
}

async function loadExecutionStrategies() {
  if (!selectedAccountId.value) return;
  isLoadingStrategies.value = true;
  strategyError.value = "";
  try {
    const response: ExecutionStrategiesResponse = await getExecutionStrategies(selectedAccountId.value);
    strategyAssignments.value = response.items;
    availableStrategies.value = response.available;
    strategyTotal.value = response.total;
    if (!selectedStrategyName.value || !strategyNameExists(selectedStrategyName.value)) {
      selectedStrategyName.value =
        strategyAssignments.value[0]?.strategy_name ?? availableStrategies.value[0]?.name ?? "";
    }
  } catch (cause) {
    strategyError.value = errorMessage(cause);
    strategyAssignments.value = [];
    availableStrategies.value = [];
    strategyTotal.value = 0;
  } finally {
    isLoadingStrategies.value = false;
  }
}

async function assignSelectedStrategy() {
  if (!selectedAccountId.value || !selectedStrategyName.value) return;
  isAssigningStrategy.value = true;
  strategyError.value = "";
  try {
    await assignExecutionStrategy(selectedAccountId.value, selectedStrategyName.value, {
      comment: textOrNull(strategyAssignComment.value),
    });
    strategyAssignComment.value = "";
    await loadExecutionStrategies();
  } catch (cause) {
    strategyError.value = errorMessage(cause);
  } finally {
    isAssigningStrategy.value = false;
  }
}

async function unassignStrategy(strategyName: string) {
  if (!selectedAccountId.value) return;
  isAssigningStrategy.value = true;
  strategyError.value = "";
  try {
    await unassignExecutionStrategy(selectedAccountId.value, strategyName);
    if (selectedStrategyName.value === strategyName) {
      strategyRunResult.value = null;
    }
    await loadExecutionStrategies();
  } catch (cause) {
    strategyError.value = errorMessage(cause);
  } finally {
    isAssigningStrategy.value = false;
  }
}

async function runSelectedStrategy() {
  if (!selectedAccountId.value || !selectedStrategyName.value) return;
  isRunningStrategy.value = true;
  strategyError.value = "";
  try {
    strategyRunResult.value = await runExecutionStrategy(
      selectedAccountId.value,
      selectedStrategyName.value,
      normalizeStrategyRunSettings(),
    );
  } catch (cause) {
    strategyError.value = errorMessage(cause);
    strategyRunResult.value = null;
  } finally {
    isRunningStrategy.value = false;
  }
}

function normalizeStrategyRunSettings(): StrategyRunRequest {
  return {
    ...strategyRunSettings.value,
    start_date: textOrNull(strategyRunSettings.value.start_date),
    end_date: textOrNull(strategyRunSettings.value.end_date),
    limit_offset_pct: Number(strategyRunSettings.value.limit_offset_pct),
    min_order_value: Number(strategyRunSettings.value.min_order_value),
  };
}

function strategyNameExists(strategyName: string): boolean {
  return (
    strategyAssignments.value.some((item) => item.strategy_name === strategyName) ||
    availableStrategies.value.some((item) => item.name === strategyName)
  );
}

async function chooseInstrument(instrument: TradableInstrument) {
  selectedInstrument.value = instrument;
  isInstrumentPickerOpen.value = false;
  applyInstrumentToTickets(instrument);
  await Promise.allSettled([
    loadLastPriceForSelectedInstrument(),
    loadTicketCandles(),
    connectOrderBook(),
  ]);
}

function applyInstrumentToTickets(instrument: TradableInstrument) {
  const instrumentId = instrumentIdFor(instrument);
  const ticketPriceType = priceTypeForInstrument(instrument);
  orderTicket.value.instrument_id = instrumentId;
  orderTicket.value.figi = instrument.figi;
  orderTicket.value.price_type = ticketPriceType;
  stopTicket.value.instrument_id = instrumentId;
  stopTicket.value.figi = instrument.figi;
  stopTicket.value.price_type = ticketPriceType;
}

async function loadLastPriceForSelectedInstrument() {
  const instrument = selectedInstrument.value;
  if (!instrument) return;

  try {
    const lastPrice = await getLastPrice({
      instrument_id: instrumentIdFor(instrument),
      figi: instrument.figi,
    });
    if (
      orderTicket.value.order_type === "limit" &&
      Number.isFinite(lastPrice.price_value ?? NaN)
    ) {
      orderTicket.value.price = Number(lastPrice.price_value);
    }
    if (
      Number(stopTicket.value.stop_price ?? 0) <= 0 &&
      Number.isFinite(lastPrice.price_value ?? NaN)
    ) {
      stopTicket.value.stop_price = Number(lastPrice.price_value);
    }
  } catch (cause) {
    chartError.value = `Last price: ${errorMessage(cause)}`;
  }
}

async function loadTicketCandles() {
  const instrument = selectedInstrument.value;
  if (!instrument?.figi) return;

  isLoadingCandles.value = true;
  chartError.value = "";
  try {
    const response = await getPrices({
      figis: [instrument.figi],
      instrument_type: "all",
      class_code: null,
      start_date: chartStartDate.value,
      end_date: chartEndDate.value,
      interval: chartInterval.value,
      is_complete: false,
    });
    candles.value = response.items;
  } catch (cause) {
    candles.value = [];
    chartError.value = errorMessage(cause);
  } finally {
    isLoadingCandles.value = false;
  }
}

async function setChartInterval(interval: string) {
  chartInterval.value = interval;
  const option = chartIntervals.find((item) => item.value === interval);
  chartEndDate.value = formatDateInput(new Date());
  chartStartDate.value = formatDateInput(addDays(new Date(), -(option?.days ?? 365)));
  await loadTicketCandles();
}

async function connectOrderBook() {
  const instrument = selectedInstrument.value;
  disconnectOrderBook("connecting");
  orderBook.value = null;
  orderBookError.value = "";

  if (!instrument) {
    orderBookStatus.value = "idle";
    return;
  }

  const token = await accessTokenForWebSocket();
  if (!token) {
    orderBookStatus.value = "error";
    orderBookError.value = "Нет access token для WebSocket";
    return;
  }

  const socket = new WebSocket(buildExecutionWsUrl("/ws/orderbook"));
  orderBookSocket = socket;

  socket.addEventListener("open", () => {
    socket.send(
      JSON.stringify({
        type: "auth",
        access_token: token,
        instrument_id: instrumentIdFor(instrument),
        figi: instrument.figi,
        depth: 20,
      }),
    );
    scheduleOrderBookNoDataMark();
  });

  socket.addEventListener("message", (event) => {
    const payload = parseJsonMessage(event.data);
    if (!payload) return;
    if (payload.type === "error") {
      clearOrderBookNoDataTimer();
      orderBookStatus.value = "error";
      orderBookError.value = String(payload.message ?? "Ошибка стакана");
      socket.close(4000);
      return;
    }
    if (payload.type === "orderbook") {
      clearOrderBookNoDataTimer();
      orderBook.value = payload as unknown as OrderBookSnapshot;
      orderBookStatus.value = "live";
      orderBookError.value = "";
      scheduleOrderBookStaleMark();
    }
  });

  socket.addEventListener("error", () => {
    if (orderBookSocket !== socket) return;
    orderBookStatus.value = "error";
    orderBookError.value = "WebSocket стакана недоступен";
  });

  socket.addEventListener("close", () => {
    if (orderBookSocket !== socket) return;
    orderBookSocket = null;
    clearOrderBookNoDataTimer();
    clearOrderBookStaleTimer();
    if (orderBookStatus.value !== "error") {
      orderBookStatus.value = orderBook.value ? "stale" : "idle";
    }
  });
}

function disconnectOrderBook(nextStatus: OrderBookStatus = "idle") {
  clearOrderBookNoDataTimer();
  clearOrderBookStaleTimer();
  if (orderBookSocket) {
    const socket = orderBookSocket;
    orderBookSocket = null;
    socket.close(1000);
  }
  orderBookStatus.value = nextStatus;
}

async function submitOrder() {
  if (!selectedAccountId.value) return;
  isSubmittingOrder.value = true;
  error.value = "";
  try {
    const ticket = normalizeOrderTicket();
    latestStub.value = await createOrder(selectedAccountId.value, ticket);
  } catch (cause) {
    error.value = errorMessage(cause);
  } finally {
    isSubmittingOrder.value = false;
  }
}

async function submitStopOrder() {
  if (!selectedAccountId.value) return;
  isSubmittingStop.value = true;
  error.value = "";
  try {
    latestStub.value = await createStopOrder(selectedAccountId.value, normalizeStopTicket());
  } catch (cause) {
    error.value = errorMessage(cause);
  } finally {
    isSubmittingStop.value = false;
  }
}

async function signOut() {
  clearAuthTokens();
  window.location.replace(authHref);
}

function normalizeOrderTicket(): OrderTicket {
  const ticket = orderTicket.value;
  return {
    ...ticket,
    figi: textOrNull(ticket.figi),
    price: ticket.order_type === "market" ? null : Number(ticket.price),
    client_order_id: textOrNull(ticket.client_order_id),
    comment: textOrNull(ticket.comment),
  };
}

function normalizeStopTicket(): StopOrderTicket {
  const ticket = stopTicket.value;
  return {
    ...ticket,
    figi: textOrNull(ticket.figi),
    stop_price: Number(ticket.stop_price),
    limit_price: ticket.limit_price ? Number(ticket.limit_price) : null,
    expire_at: textOrNull(ticket.expire_at),
    client_order_id: textOrNull(ticket.client_order_id),
    comment: textOrNull(ticket.comment),
  };
}

function textOrNull(value: string | null | undefined): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Не удалось выполнить запрос";
}

function accountTypeLabel(value?: string | number | null): string {
  const labels: Record<string, string> = {
    ACCOUNT_TYPE_TINKOFF: "Брокерский",
    ACCOUNT_TYPE_TINKOFF_IIS: "ИИС",
    ACCOUNT_TYPE_INVEST_BOX: "Инвесткопилка",
    ACCOUNT_TYPE_INVEST_FUND: "Фонд",
  };
  const text = enumText(value);
  return text ? labels[text] ?? text.replace("ACCOUNT_TYPE_", "") : "Счет";
}

function statusLabel(value?: string | number | null): string {
  const labels: Record<string, string> = {
    ACCOUNT_STATUS_OPEN: "Открыт",
    ACCOUNT_STATUS_CLOSED: "Закрыт",
    ACCOUNT_STATUS_NEW: "Новый",
    NOT_RETURNED_BY_BROKER: "Нет доступа",
  };
  const text = enumText(value);
  return text ? labels[text] ?? text.replace("ACCOUNT_STATUS_", "") : "Неизвестно";
}

function sideLabel(value?: string | number | null): string {
  const text = enumText(value);
  if (!text) return "";
  if (text.includes("BUY")) return "Покупка";
  if (text.includes("SELL")) return "Продажа";
  return text;
}

function enumText(value?: string | number | null): string {
  return value === undefined || value === null ? "" : String(value);
}

function formatMoney(amount?: MoneyAmount | null, fallbackCurrency = primaryCurrency.value): string {
  if (!amount || !Number.isFinite(amount.value ?? NaN)) return "n/a";
  const currency = String(amount.currency ?? fallbackCurrency ?? "rub").toUpperCase();
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: currency === "RUB" ? "RUB" : currency,
      maximumFractionDigits: 2,
    }).format(Number(amount.value));
  } catch {
    return `${formatNumber(Number(amount.value))} ${currency}`;
  }
}

function formatValue(value?: number | null): string {
  if (!Number.isFinite(value ?? NaN)) return "n/a";
  return formatMoney({ value, currency: primaryCurrency.value });
}

function formatNumber(value?: number | null, digits = 2): string {
  if (!Number.isFinite(value ?? NaN)) return "n/a";
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: digits,
  }).format(Number(value));
}

function formatPercent(value?: number | null): string {
  if (!Number.isFinite(value ?? NaN)) return "n/a";
  return `${formatNumber(Number(value) * 100, 2)}%`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: MARKET_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortId(value: string): string {
  return value.length > 8 ? `...${value.slice(-8)}` : value;
}

function instrumentIdFor(instrument: TradableInstrument): string {
  return instrument.uid || instrument.instrument_uid || instrument.figi;
}

function instrumentTypeLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    share: "Акция",
    etf: "ETF",
    bond: "Облигация",
    currency: "Валюта",
    future: "Фьючерс",
  };
  const key = String(value ?? "").toLowerCase();
  return labels[key] ?? key;
}

function priceTypeForInstrument(instrument: TradableInstrument): "currency" | "point" {
  return String(instrument.instrument_type ?? "").toLowerCase() === "future" ? "point" : "currency";
}

function flagLabel(value?: boolean | null): string {
  return value ? "yes" : "no";
}

function strategySideLabel(value: string): string {
  return value === "buy" ? "Покупка" : "Продажа";
}

function strategyStopKindLabel(value: string): string {
  if (value === "stop_loss") return "Стоп-лосс";
  if (value === "take_profit") return "Тейк-профит";
  return value;
}

function formatDateOnly(value?: string | null): string {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: MARKET_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function addDays(value: Date, days: number): Date {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function formatDateInput(value: Date): string {
  return formatMarketDateInput(value);
}

function buildExecutionWsUrl(path: string): string {
  const url = new URL(`${executionApiBase}${path}`, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function parseJsonMessage(value: unknown): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(String(value));
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function scheduleOrderBookNoDataMark() {
  clearOrderBookNoDataTimer();
  orderBookNoDataTimer = window.setTimeout(() => {
    if (orderBookStatus.value === "connecting") {
      orderBookStatus.value = "stale";
    }
  }, 12_000);
}

function scheduleOrderBookStaleMark() {
  clearOrderBookStaleTimer();
  orderBookStaleTimer = window.setTimeout(() => {
    if (orderBookStatus.value === "live") {
      orderBookStatus.value = "stale";
    }
  }, 15_000);
}

function clearOrderBookNoDataTimer() {
  if (orderBookNoDataTimer !== undefined) {
    window.clearTimeout(orderBookNoDataTimer);
    orderBookNoDataTimer = undefined;
  }
}

function clearOrderBookStaleTimer() {
  if (orderBookStaleTimer !== undefined) {
    window.clearTimeout(orderBookStaleTimer);
    orderBookStaleTimer = undefined;
  }
}
</script>

<template>
  <div v-if="isCheckingAuth" class="auth-check-shell">
    <Loader2 class="spin" :size="28" />
    <span>Проверка входа</span>
  </div>

  <div v-else class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">
          <Landmark :size="23" />
        </div>
        <div>
          <strong>ITS Execution</strong>
          <span>T-Invest cockpit</span>
        </div>
      </div>

      <div class="top-actions">
        <div class="account-select-shell">
          <WalletCards :size="17" />
          <select v-model="selectedAccountId" :disabled="isLoadingAccounts" @change="loadOverview">
            <option v-for="account in accounts" :key="account.id" :value="account.id">
              {{ account.name }} / {{ shortId(account.id) }}
            </option>
          </select>
        </div>
        <select v-model.number="operationsDays" class="compact-select" @change="loadOverview">
          <option :value="7">7 дней</option>
          <option :value="30">30 дней</option>
          <option :value="90">90 дней</option>
          <option :value="365">365 дней</option>
        </select>
        <button class="icon-button" type="button" title="Обновить" aria-label="Обновить" @click="loadOverview">
          <RefreshCw :class="{ spin: isLoadingOverview }" :size="18" />
        </button>
        <button class="icon-button" type="button" title="Стратегии" aria-label="Стратегии" @click="openStrategyModal">
          <Link2 :size="18" />
        </button>
        <a class="icon-button" href="/launchpad/" title="Launchpad" aria-label="Launchpad">
          <Home :size="18" />
        </a>
        <a class="icon-button" :href="docsHref" title="Документация" aria-label="Документация">
          <CircleHelp :size="18" />
        </a>
        <button class="icon-button" type="button" title="Выйти" aria-label="Выйти" @click="signOut">
          <LogOut :size="18" />
        </button>
      </div>
    </header>

    <main class="workspace">
      <aside class="account-rail">
        <button
          v-for="account in accounts"
          :key="account.id"
          class="account-item"
          type="button"
          :class="{ active: account.id === selectedAccountId, unavailable: !account.is_available }"
          :disabled="!account.is_available"
          @click="selectAccount(account)"
        >
          <BriefcaseBusiness :size="18" />
          <span>
            <strong>{{ account.name }}</strong>
            <small>{{ accountTypeLabel(account.type) }} / {{ statusLabel(account.status) }}</small>
          </span>
        </button>

        <div class="rail-status">
          <ShieldCheck :size="17" />
          <span>{{ user?.email }}</span>
        </div>
      </aside>

      <section class="content">
        <div v-if="error" class="error-banner">
          {{ error }}
        </div>

        <section class="mode-strip">
          <div>
            <span>Счет</span>
            <strong>{{ selectedAccount?.name ?? "Не выбран" }}</strong>
          </div>
          <div>
            <span>Статус</span>
            <strong>{{ statusLabel(selectedAccount?.status) }}</strong>
          </div>
          <div>
            <span>Приказы</span>
            <strong>{{ submissionModeLabel }}</strong>
          </div>
          <div>
            <span>Срез</span>
            <strong>{{ overview ? formatDateTime(overview.as_of) : "n/a" }}</strong>
          </div>
        </section>

        <section class="metric-grid">
          <article class="metric">
            <Activity :size="20" />
            <div>
              <span>Портфель</span>
              <strong>{{ formatMoney(summary?.total_amount_portfolio) }}</strong>
            </div>
          </article>
          <article class="metric">
            <ArrowUpRight :size="20" />
            <div>
              <span>Ожидаемый результат</span>
              <strong :class="{ positive: Number(summary?.expected_yield_value ?? 0) >= 0, negative: Number(summary?.expected_yield_value ?? 0) < 0 }">
                {{ formatNumber(summary?.expected_yield_value) }}
              </strong>
            </div>
          </article>
          <article class="metric">
            <ArrowDownLeft :size="20" />
            <div>
              <span>День</span>
              <strong :class="{ positive: Number(summary?.daily_yield_value ?? 0) >= 0, negative: Number(summary?.daily_yield_value ?? 0) < 0 }">
                {{ formatMoney(summary?.daily_yield) }} / {{ formatPercent(summary?.daily_yield_relative_value) }}
              </strong>
            </div>
          </article>
          <article class="metric">
            <WalletCards :size="20" />
            <div>
              <span>Деньги</span>
              <strong>{{ formatValue(totalCash) }}</strong>
            </div>
          </article>
          <article class="metric">
            <ClipboardCheck :size="20" />
            <div>
              <span>Заявки</span>
              <strong>{{ summary?.open_orders_count ?? 0 }} / {{ summary?.stop_orders_count ?? 0 }}</strong>
            </div>
          </article>
        </section>

        <section class="dashboard-grid">
          <article class="panel chart-panel">
            <header class="panel-head">
              <div>
                <span>Структура</span>
                <strong>Allocation</strong>
              </div>
              <BarChart3 :size="18" />
            </header>
            <AllocationChart :allocation="summary?.allocation ?? []" />
          </article>

          <article class="panel chart-panel">
            <header class="panel-head">
              <div>
                <span>Классы активов</span>
                <strong>Стоимость</strong>
              </div>
              <BarChart3 :size="18" />
            </header>
            <AllocationBarChart :allocation="summary?.allocation ?? []" />
          </article>

          <article class="panel chart-panel">
            <header class="panel-head">
              <div>
                <span>Операции</span>
                <strong>Cashflow</strong>
              </div>
              <Activity :size="18" />
            </header>
            <OperationsCashflowChart :operations="operations" />
          </article>

          <article class="panel ticket-panel">
            <header class="panel-head">
              <div>
                <span>Приказ</span>
                <strong>Ticket</strong>
              </div>
              <div class="ticket-actions">
                <button class="secondary-button" type="button" @click="openInstrumentPicker">
                  <Search :size="15" />
                  Выбрать
                </button>
                <div class="segmented">
                  <button type="button" :class="{ active: activeTicket === 'order' }" @click="activeTicket = 'order'">
                    Order
                  </button>
                  <button type="button" :class="{ active: activeTicket === 'stop' }" @click="activeTicket = 'stop'">
                    Stop
                  </button>
                </div>
              </div>
            </header>

            <div class="ticket-instrument-strip" :class="{ empty: !selectedInstrument }">
              <span>{{ selectedInstrumentLabel }}</span>
              <strong>{{ selectedInstrumentId || "no instrument_id" }}</strong>
            </div>

            <form v-if="activeTicket === 'order'" class="ticket-form" @submit.prevent="submitOrder">
              <label>
                <span>Instrument ID</span>
                <input v-model.trim="orderTicket.instrument_id" required placeholder="FIGI or UID" />
              </label>
              <label>
                <span>FIGI</span>
                <input v-model.trim="orderTicket.figi" placeholder="optional" />
              </label>
              <div class="form-row">
                <label>
                  <span>Side</span>
                  <select v-model="orderTicket.side">
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </label>
                <label>
                  <span>Type</span>
                  <select v-model="orderTicket.order_type">
                    <option value="limit">Limit</option>
                    <option value="market">Market</option>
                  </select>
                </label>
              </div>
              <div class="form-row">
                <label>
                  <span>Lots</span>
                  <input v-model.number="orderTicket.quantity" min="1" required type="number" />
                </label>
                <label>
                  <span>Price</span>
                  <input
                    v-model.number="orderTicket.price"
                    :disabled="orderTicket.order_type === 'market'"
                    :required="orderTicket.order_type === 'limit'"
                    min="0"
                    step="0.0000001"
                    type="number"
                  />
                </label>
              </div>
              <button class="primary-button" type="submit" :disabled="isSubmittingOrder || !selectedAccountId">
                <Send :size="16" />
                {{ submitOrderLabel }}
              </button>
            </form>

            <form v-else class="ticket-form" @submit.prevent="submitStopOrder">
              <label>
                <span>Instrument ID</span>
                <input v-model.trim="stopTicket.instrument_id" required placeholder="FIGI or UID" />
              </label>
              <label>
                <span>FIGI</span>
                <input v-model.trim="stopTicket.figi" placeholder="optional" />
              </label>
              <div class="form-row">
                <label>
                  <span>Side</span>
                  <select v-model="stopTicket.side">
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </label>
                <label>
                  <span>Type</span>
                  <select v-model="stopTicket.stop_order_type">
                    <option value="stop_loss">Stop-loss</option>
                    <option value="take_profit">Take-profit</option>
                  </select>
                </label>
              </div>
              <div class="form-row">
                <label>
                  <span>Lots</span>
                  <input v-model.number="stopTicket.quantity" min="1" required type="number" />
                </label>
                <label>
                  <span>Stop price</span>
                  <input v-model.number="stopTicket.stop_price" min="0" required step="0.0000001" type="number" />
                </label>
              </div>
              <button class="primary-button" type="submit" :disabled="isSubmittingStop || !selectedAccountId">
                <Send :size="16" />
                {{ submitStopOrderLabel }}
              </button>
            </form>

            <div v-if="latestStub" class="stub-result">
              <span>{{ latestStub.status }}</span>
              <strong>{{ latestStub.id }}</strong>
              <small>{{ formatDateTime(latestStub.created_at) }}</small>
            </div>
          </article>
        </section>

        <section class="terminal-grid">
          <article class="panel market-panel">
            <header class="panel-head market-head">
              <div>
                <span>График</span>
                <strong>{{ selectedInstrument?.ticker ?? "Ticket" }}</strong>
              </div>
              <div class="chart-controls">
                <div class="interval-strip">
                  <button
                    v-for="interval in chartIntervals"
                    :key="interval.value"
                    type="button"
                    :class="{ active: chartInterval === interval.value }"
                    @click="setChartInterval(interval.value)"
                  >
                    {{ interval.label }}
                  </button>
                </div>
                <input v-model="chartStartDate" type="date" @change="loadTicketCandles" />
                <input v-model="chartEndDate" type="date" @change="loadTicketCandles" />
                <button class="icon-button" type="button" title="Обновить график" aria-label="Обновить график" @click="loadTicketCandles">
                  <RefreshCw :class="{ spin: isLoadingCandles }" :size="17" />
                </button>
              </div>
            </header>
            <div v-if="chartError" class="inline-error">{{ chartError }}</div>
            <TicketCandlestickChart :candles="candles" :interval="chartInterval" />
          </article>

          <article class="panel market-panel">
            <header class="panel-head market-head">
              <div>
                <span>Стакан</span>
                <strong>{{ selectedInstrument?.ticker ?? "Live order book" }}</strong>
              </div>
              <button
                class="icon-button"
                type="button"
                title="Переподключить стакан"
                aria-label="Переподключить стакан"
                :disabled="!selectedInstrument"
                @click="connectOrderBook"
              >
                <RefreshCw :class="{ spin: orderBookStatus === 'connecting' }" :size="17" />
              </button>
            </header>
            <OrderBookPanel :snapshot="orderBook" :status="orderBookStatus" :error="orderBookError" />
          </article>
        </section>

        <section v-if="sectionErrorRows.length" class="section-errors">
          <article v-for="[name, message] in sectionErrorRows" :key="name">
            <strong>{{ name }}</strong>
            <span>{{ message }}</span>
          </article>
        </section>

        <section class="data-grid">
          <article class="panel table-panel">
            <header class="panel-head">
              <div>
                <span>Портфель</span>
                <strong>{{ portfolioPositions.length }} позиций</strong>
              </div>
            </header>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Тикер</th>
                    <th>Тип</th>
                    <th>Лоты</th>
                    <th>Средняя</th>
                    <th>Текущая</th>
                    <th>Результат</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="position in portfolioPositions" :key="position.position_uid || position.figi">
                    <td>
                      <strong>{{ position.ticker || shortId(position.figi) }}</strong>
                      <small>{{ shortId(position.figi) }}</small>
                    </td>
                    <td>{{ position.instrument_type }}</td>
                    <td>{{ formatNumber(position.quantity_lots?.value ?? position.quantity?.value, 4) }}</td>
                    <td>{{ formatMoney(position.average_position_price) }}</td>
                    <td>{{ formatMoney(position.current_price) }}</td>
                    <td>{{ formatNumber(position.expected_yield?.value) }}</td>
                  </tr>
                  <tr v-if="!portfolioPositions.length">
                    <td colspan="6">Нет данных</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article class="panel table-panel">
            <header class="panel-head">
              <div>
                <span>Деньги и бумаги</span>
                <strong>{{ securities.length }} / {{ moneyRows.length }}</strong>
              </div>
            </header>
            <div class="money-list">
              <div v-for="money in moneyRows" :key="`${money.currency}-${money.value}`">
                <span>{{ String(money.currency ?? "").toUpperCase() }}</span>
                <strong>{{ formatMoney(money) }}</strong>
              </div>
              <div v-for="money in blockedMoneyRows" :key="`blocked-${money.currency}-${money.value}`" class="blocked">
                <span>Blocked {{ String(money.currency ?? "").toUpperCase() }}</span>
                <strong>{{ formatMoney(money) }}</strong>
              </div>
            </div>
            <div class="table-scroll compact-table">
              <table>
                <thead>
                  <tr>
                    <th>FIGI</th>
                    <th>Баланс</th>
                    <th>Блок</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="security in securities" :key="security.position_uid || security.figi">
                    <td>
                      <strong>{{ security.ticker || shortId(security.figi) }}</strong>
                      <small>{{ security.instrument_type }}</small>
                    </td>
                    <td>{{ security.balance }}</td>
                    <td>{{ security.blocked }}</td>
                  </tr>
                  <tr v-if="!securities.length">
                    <td colspan="3">Нет данных</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section class="data-grid">
          <article class="panel table-panel">
            <header class="panel-head">
              <div>
                <span>Активные заявки</span>
                <strong>{{ orders.length }}</strong>
              </div>
            </header>
            <div class="table-scroll compact-table">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Side</th>
                    <th>Lots</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="order in orders" :key="order.order_id">
                    <td>{{ shortId(order.order_id) }}</td>
                    <td>{{ sideLabel(order.direction) }}</td>
                    <td>{{ order.lots_executed ?? 0 }} / {{ order.lots_requested ?? 0 }}</td>
                    <td>{{ formatMoney(order.total_order_amount) }}</td>
                    <td>{{ order.execution_report_status }}</td>
                  </tr>
                  <tr v-if="!orders.length">
                    <td colspan="5">Нет активных заявок</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article class="panel table-panel">
            <header class="panel-head">
              <div>
                <span>Стоп-заявки</span>
                <strong>{{ stopOrders.length }}</strong>
              </div>
            </header>
            <div class="table-scroll compact-table">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Тип</th>
                    <th>Тикер</th>
                    <th>Stop</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="order in stopOrders" :key="order.stop_order_id">
                    <td>{{ shortId(order.stop_order_id) }}</td>
                    <td>{{ order.order_type }}</td>
                    <td>{{ order.ticker || shortId(order.figi || "") }}</td>
                    <td>{{ formatMoney(order.stop_price) }}</td>
                    <td>{{ order.status }}</td>
                  </tr>
                  <tr v-if="!stopOrders.length">
                    <td colspan="5">Нет стоп-заявок</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <article class="panel table-panel">
          <header class="panel-head">
            <div>
              <span>История</span>
              <strong>{{ operations.length }} операций</strong>
            </div>
          </header>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Операция</th>
                  <th>Инструмент</th>
                  <th>Кол-во</th>
                  <th>Сумма</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="operation in operations.slice(0, 80)" :key="operation.id">
                  <td>{{ formatDateTime(operation.date) }}</td>
                  <td>{{ operation.type || operation.operation_type }}</td>
                  <td>{{ operation.figi ? shortId(operation.figi) : "n/a" }}</td>
                  <td>{{ operation.quantity ?? "n/a" }}</td>
                  <td>{{ formatMoney(operation.payment) }}</td>
                  <td>{{ operation.state }}</td>
                </tr>
                <tr v-if="!operations.length">
                  <td colspan="6">Нет операций за период</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <div v-if="isLoadingAccounts || isLoadingOverview" class="loading-overlay">
          <Loader2 class="spin" :size="30" />
        </div>
      </section>
    </main>

    <div v-if="isInstrumentPickerOpen" class="instrument-modal-backdrop" @click.self="isInstrumentPickerOpen = false">
      <section class="instrument-modal" role="dialog" aria-modal="true" aria-label="Выбор инструмента">
        <header class="instrument-modal-head">
          <div>
            <span>Справочник</span>
            <strong>Выбор инструмента</strong>
          </div>
          <button class="icon-button" type="button" title="Закрыть" aria-label="Закрыть" @click="isInstrumentPickerOpen = false">
            <X :size="18" />
          </button>
        </header>

        <div class="instrument-toolbar">
          <label class="search-field">
            <Search :size="16" />
            <input
              v-model.trim="instrumentSearch"
              placeholder="Ticker, name, FIGI"
              @keydown.enter.prevent="loadInstruments"
            />
          </label>
          <select v-model="instrumentTypeFilter" @change="loadInstruments">
            <option value="">Все типы</option>
            <option v-for="type in instrumentFilters.instrument_types" :key="type" :value="type">
              {{ instrumentTypeLabel(type) }}
            </option>
          </select>
          <select v-model="instrumentClassCode" @change="loadInstruments">
            <option value="">Все классы</option>
            <option v-for="classCode in instrumentFilters.class_codes" :key="classCode" :value="classCode">
              {{ classCode }}
            </option>
          </select>
          <select v-model="instrumentCurrency" @change="loadInstruments">
            <option value="">Все валюты</option>
            <option v-for="currency in instrumentFilters.currencies" :key="currency" :value="currency">
              {{ String(currency).toUpperCase() }}
            </option>
          </select>
          <select v-model="instrumentExchange" @change="loadInstruments">
            <option value="">Все биржи</option>
            <option v-for="exchange in instrumentFilters.exchanges" :key="exchange" :value="exchange">
              {{ exchange }}
            </option>
          </select>
          <button class="secondary-button" type="button" :disabled="isLoadingInstruments" @click="loadInstruments">
            <RefreshCw :class="{ spin: isLoadingInstruments }" :size="15" />
            Поиск
          </button>
        </div>

        <div v-if="instrumentError" class="inline-error">{{ instrumentError }}</div>

        <div class="instrument-table-shell">
          <table class="instrument-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th>Type</th>
                <th>Class</th>
                <th>Currency</th>
                <th>Lot</th>
                <th>Flags</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="instrument in instruments"
                :key="instrument.uid || instrument.figi"
                :class="{ selected: selectedInstrument?.figi === instrument.figi }"
                @dblclick="chooseInstrument(instrument)"
              >
                <td>
                  <strong>{{ instrument.ticker || "n/a" }}</strong>
                  <small>{{ instrument.figi }}</small>
                </td>
                <td>{{ instrument.name }}</td>
                <td>{{ instrumentTypeLabel(instrument.instrument_type) }}</td>
                <td>{{ instrument.class_code || "n/a" }}</td>
                <td>{{ String(instrument.currency || "").toUpperCase() || "n/a" }}</td>
                <td>{{ formatNumber(instrument.lot, 0) }}</td>
                <td>
                  <span class="flag" :class="{ on: instrument.api_trade_available_flag }">API {{ flagLabel(instrument.api_trade_available_flag) }}</span>
                  <span class="flag" :class="{ on: instrument.buy_available_flag }">Buy {{ flagLabel(instrument.buy_available_flag) }}</span>
                  <span class="flag" :class="{ on: instrument.sell_available_flag }">Sell {{ flagLabel(instrument.sell_available_flag) }}</span>
                </td>
                <td>
                  <button class="mini-button" type="button" @click="chooseInstrument(instrument)">Выбрать</button>
                </td>
              </tr>
              <tr v-if="!instruments.length">
                <td colspan="8">Нет инструментов</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="instrument-modal-foot">
          <span>{{ instruments.length }} / {{ instrumentTotal }}</span>
        </footer>
      </section>
    </div>

    <div v-if="isStrategyModalOpen" class="instrument-modal-backdrop" @click.self="isStrategyModalOpen = false">
      <section class="strategy-modal" role="dialog" aria-modal="true" aria-label="Стратегии счета">
        <header class="instrument-modal-head">
          <div>
            <span>Execution</span>
            <strong>Стратегии счета</strong>
          </div>
          <button class="icon-button" type="button" title="Закрыть" aria-label="Закрыть" @click="isStrategyModalOpen = false">
            <X :size="18" />
          </button>
        </header>

        <div class="strategy-modal-body">
          <aside class="strategy-control-panel">
            <section class="strategy-account-card">
              <span>Счет</span>
              <strong>{{ selectedAccount?.name ?? selectedAccountId }}</strong>
              <small>{{ shortId(selectedAccountId) }} / {{ strategyTotal }} стратегий</small>
            </section>

            <section class="strategy-box">
              <header>
                <span>Назначить</span>
                <button class="icon-button compact-icon" type="button" title="Обновить" aria-label="Обновить" @click="loadExecutionStrategies">
                  <RefreshCw :class="{ spin: isLoadingStrategies }" :size="15" />
                </button>
              </header>
              <label>
                <span>Prod-ready стратегия</span>
                <select v-model="selectedStrategyName">
                  <option v-for="strategy in availableStrategies" :key="strategy.name" :value="strategy.name">
                    {{ strategy.name }}{{ assignedStrategyNames.has(strategy.name) ? " / assigned" : "" }}
                  </option>
                </select>
              </label>
              <label>
                <span>Комментарий</span>
                <input v-model.trim="strategyAssignComment" placeholder="например: основной счет" />
              </label>
              <button class="primary-button" type="button" :disabled="isAssigningStrategy || !selectedStrategyName" @click="assignSelectedStrategy">
                <Link2 :size="16" />
                Присвоить
              </button>
            </section>

            <section class="strategy-box">
              <header>
                <span>Ручной запуск</span>
                <strong>{{ selectedStrategyAssignment?.strategy_name ?? (selectedStrategyName || "n/a") }}</strong>
              </header>
              <div class="strategy-run-grid">
                <label>
                  <span>Дата с</span>
                  <input v-model="strategyRunSettings.start_date" type="date" />
                </label>
                <label>
                  <span>Дата по</span>
                  <input v-model="strategyRunSettings.end_date" type="date" />
                </label>
                <label>
                  <span>Интервал</span>
                  <select v-model="strategyRunSettings.interval">
                    <option value="CANDLE_INTERVAL_DAY">1d</option>
                    <option value="CANDLE_INTERVAL_WEEK">1w</option>
                    <option value="CANDLE_INTERVAL_MONTH">1M</option>
                  </select>
                </label>
                <label>
                  <span>Класс</span>
                  <input v-model.trim="strategyRunSettings.class_code" />
                </label>
                <label>
                  <span>Приказы</span>
                  <select v-model="strategyRunSettings.order_type">
                    <option value="limit">Limit</option>
                    <option value="market">Market</option>
                  </select>
                </label>
                <label>
                  <span>Offset limit</span>
                  <input v-model.number="strategyRunSettings.limit_offset_pct" min="0" max="0.1" step="0.0005" type="number" />
                </label>
                <label>
                  <span>Мин. сумма</span>
                  <input v-model.number="strategyRunSettings.min_order_value" min="0" step="100" type="number" />
                </label>
              </div>
              <button
                class="primary-button"
                type="button"
                :disabled="isRunningStrategy || !selectedStrategyAssignment"
                @click="runSelectedStrategy"
              >
                <Play :class="{ spin: isRunningStrategy }" :size="16" />
                Запустить dry-run
              </button>
            </section>
          </aside>

          <section class="strategy-result-panel">
            <div v-if="strategyError" class="inline-error">{{ strategyError }}</div>

            <section class="strategy-box assigned-box">
              <header>
                <span>Присвоено счету</span>
                <strong>{{ strategyAssignments.length }}</strong>
              </header>
              <div class="strategy-table-shell">
                <table class="strategy-table">
                  <thead>
                    <tr>
                      <th>Стратегия</th>
                      <th>Prod</th>
                      <th>Комментарий</th>
                      <th>Назначена</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="assignment in strategyAssignments"
                      :key="assignment.id"
                      :class="{ selected: selectedStrategyName === assignment.strategy_name }"
                      @click="selectedStrategyName = assignment.strategy_name"
                    >
                      <td>
                        <strong>{{ assignment.strategy_name }}</strong>
                        <small>{{ assignment.strategy.description }}</small>
                      </td>
                      <td>
                        <span class="flag on">ready</span>
                      </td>
                      <td>{{ assignment.comment || "n/a" }}</td>
                      <td>{{ formatDateOnly(assignment.created_at) }}</td>
                      <td>
                        <button class="mini-button danger" type="button" @click.stop="unassignStrategy(assignment.strategy_name)">
                          <Trash2 :size="14" />
                        </button>
                      </td>
                    </tr>
                    <tr v-if="!strategyAssignments.length">
                      <td colspan="5">Стратегии еще не присвоены</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section class="strategy-summary-grid">
              <article>
                <span>Портфель</span>
                <strong>{{ formatValue(strategyRunResult?.portfolio.value) }}</strong>
              </article>
              <article>
                <span>Целевые бумаги</span>
                <strong>{{ strategyRunResult?.summary.target_positions ?? 0 }}</strong>
              </article>
              <article>
                <span>Приказы</span>
                <strong>{{ strategyRunResult?.summary.orders ?? 0 }}</strong>
              </article>
              <article>
                <span>Стоп/тейк</span>
                <strong>{{ strategyRunResult?.summary.stop_orders ?? 0 }}</strong>
              </article>
              <article>
                <span>Net cash</span>
                <strong :class="{ positive: Number(strategyRunResult?.summary.net_cash_need ?? 0) <= 0, negative: Number(strategyRunResult?.summary.net_cash_need ?? 0) > 0 }">
                  {{ formatValue(strategyRunResult?.summary.net_cash_need) }}
                </strong>
              </article>
            </section>

            <section class="strategy-box chart-box">
              <header>
                <span>Графики</span>
                <strong>{{ strategyRunResult?.strategy_name ?? "Dry-run" }}</strong>
              </header>
              <StrategyPlanChart :result="strategyRunResult" />
            </section>

            <section class="strategy-result-grid">
              <article class="strategy-box">
                <header>
                  <span>Целевые веса</span>
                  <strong>{{ strategyRunResult?.target_weights.length ?? 0 }}</strong>
                </header>
                <div class="strategy-table-shell compact-strategy-table">
                  <table class="strategy-table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Сейчас</th>
                        <th>Цель</th>
                        <th>Лоты</th>
                        <th>Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in strategyRunResult?.target_weights ?? []" :key="row.ticker">
                        <td>
                          <strong>{{ row.ticker }}</strong>
                          <small>{{ row.name }}</small>
                        </td>
                        <td>{{ formatPercent(row.current_weight) }}</td>
                        <td>{{ formatPercent(row.target_weight) }}</td>
                        <td>{{ formatNumber(row.current_lots, 0) }} -> {{ row.target_lots }}</td>
                        <td :class="{ positive: row.delta_lots > 0, negative: row.delta_lots < 0 }">
                          {{ row.delta_lots }}
                        </td>
                      </tr>
                      <tr v-if="!strategyRunResult?.target_weights.length">
                        <td colspan="5">Нет расчета</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </article>

              <article class="strategy-box">
                <header>
                  <span>Приказы</span>
                  <strong>{{ strategyRunResult?.orders.length ?? 0 }}</strong>
                </header>
                <div class="strategy-table-shell compact-strategy-table">
                  <table class="strategy-table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Side</th>
                        <th>Type</th>
                        <th>Lots</th>
                        <th>Price</th>
                        <th>Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in strategyRunResult?.orders ?? []" :key="`${row.ticker}-${row.side}`">
                        <td>
                          <strong>{{ row.ticker }}</strong>
                          <small>{{ row.name }}</small>
                        </td>
                        <td :class="{ positive: row.side === 'buy', negative: row.side === 'sell' }">
                          {{ strategySideLabel(row.side) }}
                        </td>
                        <td>{{ row.order_type }}</td>
                        <td>{{ row.quantity_lots }}</td>
                        <td>{{ formatNumber(row.limit_price ?? row.last_price, 4) }}</td>
                        <td>{{ formatValue(row.estimated_amount) }}</td>
                      </tr>
                      <tr v-if="!strategyRunResult?.orders.length">
                        <td colspan="6">Нет приказов</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </article>
            </section>

            <section class="strategy-box">
              <header>
                <span>Стопы и тейки</span>
                <strong>{{ strategyRunResult?.stop_orders.length ?? 0 }}</strong>
              </header>
              <div class="strategy-table-shell compact-strategy-table">
                <table class="strategy-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Тип</th>
                      <th>Lots</th>
                      <th>Trigger</th>
                      <th>Distance</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in strategyRunResult?.stop_orders ?? []" :key="`${row.ticker}-${row.kind}`">
                      <td>
                        <strong>{{ row.ticker }}</strong>
                        <small>{{ row.name }}</small>
                      </td>
                      <td>{{ strategyStopKindLabel(row.kind) }}</td>
                      <td>{{ row.quantity_lots }}</td>
                      <td>{{ formatNumber(row.stop_price, 4) }}</td>
                      <td>{{ formatPercent(row.distance_pct) }}</td>
                    </tr>
                    <tr v-if="!strategyRunResult?.stop_orders.length">
                      <td colspan="5">Стратегия не вернула стоп/тейк уровни</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>
