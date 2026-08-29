<script setup lang="ts">
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  BarChart3,
  BriefcaseBusiness,
  CircleHelp,
  ClipboardCheck,
  FileChartColumn,
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
  executeExecutionStrategy,
  getAccounts,
  getCurrentUser,
  getExecutionStrategies,
  getLastPrice,
  getOverview,
  getPnlReport,
  getPrices,
  getTradableInstruments,
  runExecutionStrategy,
  unassignExecutionStrategy,
} from "./api";
import AllocationBarChart from "./components/AllocationBarChart.vue";
import AllocationChart from "./components/AllocationChart.vue";
import MetricHelp from "./components/MetricHelp.vue";
import OrderBookPanel from "./components/OrderBookPanel.vue";
import TicketCandlestickChart from "./components/TicketCandlestickChart.vue";
import OperationsCashflowChart from "./components/OperationsCashflowChart.vue";
import PnlReportCharts from "./components/PnlReportCharts.vue";
import StrategyPlanChart from "./components/StrategyPlanChart.vue";
import { MARKET_TIME_ZONE, formatMarketDateInput } from "./marketTime";
import { PNL_HELP } from "./pnlHelp";
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
  PnlReport,
  PortfolioPosition,
  StopOrderTicket,
  StrategyRunRequest,
  StrategyRunResult,
  StrategyExecutionResult,
  StrategyExecutionOrderResult,
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
const isPnlModalOpen = ref(false);
const isLoadingPnlReport = ref(false);
const pnlError = ref("");
const pnlReport = ref<PnlReport | null>(null);
const pnlSettings = ref({
  from_date: formatDateInput(new Date(new Date().getFullYear(), 0, 1)),
  to_date: formatDateInput(new Date()),
  strategy_name: "",
});
const isLoadingStrategies = ref(false);
const isAssigningStrategy = ref(false);
const isRunningStrategy = ref(false);
const isExecutingStrategy = ref(false);
const strategyError = ref("");
const strategyAssignments = ref<ExecutionStrategyAssignment[]>([]);
const availableStrategies = ref<ExecutionStrategyItem[]>([]);
const strategyTotal = ref(0);
const selectedStrategyName = ref("");
const strategyAssignComment = ref("");
const strategyRunResult = ref<StrategyRunResult | null>(null);
const strategyExecutionResult = ref<StrategyExecutionResult | null>(null);
const strategyRunSettings = ref<StrategyRunRequest>({
  start_date: formatDateInput(addDays(new Date(), -365)),
  end_date: formatDateInput(new Date()),
  interval: "CANDLE_INTERVAL_DAY",
  class_code: "TQBR",
  order_type: "market",
  limit_offset_pct: 0.001,
  min_order_value: 0,
  cash_buffer_pct: 0.01,
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
const requiredSubmissionPermission = computed(() =>
  overview.value?.order_submission_mode === "stub" ? "trading.paper.start" : "trading.live.start",
);
const canSubmitOrders = computed(() =>
  user.value?.permissions.includes(requiredSubmissionPermission.value) ?? false,
);
const strategyPlanAlreadyExecuted = computed(
  () =>
    Boolean(strategyRunResult.value?.plan_id) &&
    strategyExecutionResult.value?.plan_id === strategyRunResult.value?.plan_id,
);
const strategyStopPositionCount = computed(
  () => new Set((strategyRunResult.value?.stop_orders ?? []).map((row) => row.ticker)).size,
);
const strategyExecutionFailures = computed(() =>
  (strategyExecutionResult.value?.results ?? []).filter(
    (row) => row.status === "failed" || row.status === "skipped",
  ),
);

watch(
  () => orderTicket.value.order_type,
  (orderType) => {
    if (orderType === "market") {
      orderTicket.value.price = null;
    }
  },
);

watch(selectedAccountId, () => {
  strategyRunResult.value = null;
  strategyExecutionResult.value = null;
});

watch(selectedStrategyName, () => {
  strategyRunResult.value = null;
  strategyExecutionResult.value = null;
});

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
  strategyRunResult.value = null;
  strategyExecutionResult.value = null;
  pnlReport.value = null;
  pnlError.value = "";
  await loadOverview();
  if (isStrategyModalOpen.value) {
    await loadExecutionStrategies();
  }
  if (isPnlModalOpen.value) {
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

async function openPnlReport() {
  isPnlModalOpen.value = true;
  pnlError.value = "";
  if (!strategyAssignments.value.length) {
    await loadExecutionStrategies();
  }
  if (!pnlSettings.value.strategy_name && strategyAssignments.value.length === 1) {
    pnlSettings.value.strategy_name = strategyAssignments.value[0].strategy_name;
  }
}

async function generatePnlReport() {
  if (!selectedAccountId.value) return;
  isLoadingPnlReport.value = true;
  pnlError.value = "";
  try {
    pnlReport.value = await getPnlReport(selectedAccountId.value, {
      from_date: pnlSettings.value.from_date,
      to_date: pnlSettings.value.to_date,
      strategy_name: textOrNull(pnlSettings.value.strategy_name),
    });
  } catch (cause) {
    pnlError.value = errorMessage(cause);
    pnlReport.value = null;
  } finally {
    isLoadingPnlReport.value = false;
  }
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
      strategyExecutionResult.value = null;
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
    strategyExecutionResult.value = null;
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

async function executeSelectedStrategy() {
  const plan = strategyRunResult.value;
  if (!selectedAccountId.value || !selectedStrategyName.value || !plan) return;
  const orderCount = plan.orders.length;
  const mode = overview.value?.order_submission_mode === "stub" ? "STUB" : "LIVE";
  const confirmed = window.confirm(
    `${mode}: исполнить ${orderCount} рыночных заявок по плану ${plan.plan_id.slice(0, 12)}? ` +
      "Сначала будут отправлены продажи, затем покупки. Стоп-заявки не входят в пакет.",
  );
  if (!confirmed) return;

  isExecutingStrategy.value = true;
  strategyError.value = "";
  try {
    strategyExecutionResult.value = await executeExecutionStrategy(
      selectedAccountId.value,
      selectedStrategyName.value,
      {
        ...normalizeStrategyRunSettings(),
        order_type: "market",
        plan_id: plan.plan_id,
        confirmation: "execute_market_orders",
      },
    );
    await loadOverview();
  } catch (cause) {
    strategyError.value = errorMessage(cause);
  } finally {
    isExecutingStrategy.value = false;
  }
}

function normalizeStrategyRunSettings(): StrategyRunRequest {
  return {
    ...strategyRunSettings.value,
    start_date: textOrNull(strategyRunSettings.value.start_date),
    end_date: textOrNull(strategyRunSettings.value.end_date),
    limit_offset_pct: Number(strategyRunSettings.value.limit_offset_pct),
    min_order_value: Number(strategyRunSettings.value.min_order_value),
    cash_buffer_pct: Number(strategyRunSettings.value.cash_buffer_pct),
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

function strategyDeltaLabel(value: number): string {
  if (value > 0) return `Купить ${value}`;
  if (value < 0) return `Продать ${Math.abs(value)}`;
  return "Без изменений";
}

function strategyConstraintLabel(value: string | null): string {
  if (value === "below_one_lot") return "Целевая сумма меньше одного лота";
  if (value === "cash_limited") return "Ограничено доступными деньгами";
  if (value === "below_min_order") return "Ниже минимальной суммы заявки";
  return "";
}

function strategyExecutionError(row: StrategyExecutionOrderResult): string {
  const brokerResponse = row.response?.broker_response as
    | { message?: unknown; detail?: unknown }
    | null
    | undefined;
  return (
    readableErrorDetail(row.error) ||
    readableErrorDetail(row.response?.message) ||
    readableErrorDetail(brokerResponse?.message) ||
    readableErrorDetail(brokerResponse?.detail) ||
    readableErrorDetail(row.response?.broker_response) ||
    (row.status === "skipped" ? "Заявка пропущена" : "Брокер отклонил заявку без текста ошибки")
  );
}

function readableErrorDetail(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (!value || typeof value !== "object") return "";
  const detail = value as { message?: unknown; detail?: unknown; error?: unknown };
  for (const candidate of [detail.message, detail.detail, detail.error]) {
    const result = readableErrorDetail(candidate);
    if (result) return result;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
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
        <button class="secondary-button pnl-report-trigger" type="button" @click="openPnlReport">
          <FileChartColumn :size="17" />
          Отчет PnL
        </button>
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
              <button class="primary-button" type="submit" :disabled="isSubmittingOrder || !selectedAccountId || !canSubmitOrders">
                <Send :size="16" />
                {{ submitOrderLabel }}
              </button>
              <small v-if="!canSubmitOrders" class="permission-hint">
                Нужна роль «Торговый оператор» (право {{ requiredSubmissionPermission }})
              </small>
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
              <button class="primary-button" type="submit" :disabled="isSubmittingStop || !selectedAccountId || !canSubmitOrders">
                <Send :size="16" />
                {{ submitStopOrderLabel }}
              </button>
              <small v-if="!canSubmitOrders" class="permission-hint">
                Нужна роль «Торговый оператор» (право {{ requiredSubmissionPermission }})
              </small>
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

    <div v-if="isPnlModalOpen" class="instrument-modal-backdrop" @click.self="isPnlModalOpen = false">
      <section class="pnl-modal" role="dialog" aria-modal="true" aria-label="Отчет PnL">
        <header class="instrument-modal-head">
          <div>
            <span>Execution · T-Invest</span>
            <strong>Отчет PnL</strong>
          </div>
          <button class="icon-button" type="button" title="Закрыть" aria-label="Закрыть" @click="isPnlModalOpen = false">
            <X :size="18" />
          </button>
        </header>

        <div class="pnl-modal-body">
          <section class="pnl-report-toolbar">
            <label>
              <span class="metric-label-with-help">Период с <MetricHelp :help="PNL_HELP.periodFrom" /></span>
              <input v-model="pnlSettings.from_date" type="date" :max="pnlSettings.to_date" />
            </label>
            <label>
              <span class="metric-label-with-help">Период по <MetricHelp :help="PNL_HELP.periodTo" /></span>
              <input v-model="pnlSettings.to_date" type="date" :min="pnlSettings.from_date" :max="formatDateInput(new Date())" />
            </label>
            <label>
              <span class="metric-label-with-help">Контекст стратегии <MetricHelp :help="PNL_HELP.strategyContext" /></span>
              <select v-model="pnlSettings.strategy_name">
                <option value="">Весь счет</option>
                <option v-for="assignment in strategyAssignments" :key="assignment.id" :value="assignment.strategy_name">
                  {{ assignment.strategy_name }}
                </option>
              </select>
            </label>
            <button class="primary-button" type="button" :disabled="isLoadingPnlReport" @click="generatePnlReport">
              <FileChartColumn :class="{ spin: isLoadingPnlReport }" :size="17" />
              Сгенерировать отчет
            </button>
          </section>

          <div v-if="pnlError" class="inline-error">{{ pnlError }}</div>

          <div v-if="isLoadingPnlReport" class="pnl-report-loading">
            <Loader2 class="spin" :size="28" />
            <span>Загружаем полную историю операций и дневные цены T-Invest…</span>
          </div>

          <template v-else-if="pnlReport">
            <section class="pnl-report-identity">
              <div>
                <span class="metric-label-with-help">Счет <MetricHelp :help="PNL_HELP.account" /></span>
                <strong>{{ pnlReport.account_name }}</strong>
                <small>{{ shortId(pnlReport.account_id) }}</small>
              </div>
              <div>
                <span class="metric-label-with-help">Период <MetricHelp :help="PNL_HELP.reportPeriod" /></span>
                <strong>{{ formatDateOnly(pnlReport.period.from) }} — {{ formatDateOnly(pnlReport.period.to) }}</strong>
                <small>{{ pnlReport.period.calendar_days }} дней · {{ pnlReport.period.observations }} наблюдений</small>
              </div>
              <div>
                <span class="metric-label-with-help">Стратегия <MetricHelp :help="PNL_HELP.strategyScope" /></span>
                <strong>{{ pnlReport.strategy.name || "Весь счет" }}</strong>
                <small>{{ pnlReport.strategy.attribution_mode === "dedicated_account_proxy" ? "прокси выделенного счета" : "результат счета" }}</small>
              </div>
              <div>
                <span class="metric-label-with-help">Сформирован <MetricHelp :help="PNL_HELP.generatedAt" /></span>
                <strong>{{ formatDateTime(pnlReport.generated_at) }}</strong>
                <small>{{ pnlReport.data_quality.operations_source }}</small>
              </div>
            </section>

            <ul v-if="pnlReport.data_quality.warnings.length" class="pnl-quality-warnings">
              <li v-for="warning in pnlReport.data_quality.warnings" :key="warning">{{ warning }}</li>
            </ul>

            <section class="pnl-kpi-grid">
              <article class="pnl-kpi primary">
                <span class="metric-label-with-help">Итоговый PnL <MetricHelp :help="PNL_HELP.totalPnl" /></span>
                <strong :class="{ positive: pnlReport.summary.total_pnl >= 0, negative: pnlReport.summary.total_pnl < 0 }">
                  {{ formatValue(pnlReport.summary.total_pnl) }}
                </strong>
                <small>после внешних вводов и выводов</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">TWR <MetricHelp :help="PNL_HELP.twr" /></span>
                <strong :class="{ positive: pnlReport.summary.twr >= 0, negative: pnlReport.summary.twr < 0 }">
                  {{ formatPercent(pnlReport.summary.twr) }}
                </strong>
                <small>time-weighted return</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">MWR / XIRR <MetricHelp :help="PNL_HELP.mwr" /></span>
                <strong>{{ formatPercent(pnlReport.summary.mwr) }}</strong>
                <small>money-weighted, годовых</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">NAV начало → конец <MetricHelp :help="PNL_HELP.nav" /></span>
                <strong>{{ formatValue(pnlReport.summary.opening_nav) }}</strong>
                <small>{{ formatValue(pnlReport.summary.ending_nav) }}</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">Max drawdown <MetricHelp :help="PNL_HELP.maxDrawdown" /></span>
                <strong class="negative">{{ formatPercent(pnlReport.risk.max_drawdown) }}</strong>
                <small>по cash-flow adjusted кривой</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">Sharpe / Sortino <MetricHelp :help="PNL_HELP.sharpeSortino" /></span>
                <strong>{{ formatNumber(pnlReport.risk.sharpe_ratio) }} / {{ formatNumber(pnlReport.risk.sortino_ratio) }}</strong>
                <small>безрисковая ставка 0%</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">Волатильность <MetricHelp :help="PNL_HELP.annualizedVolatility" /></span>
                <strong>{{ formatPercent(pnlReport.risk.annualized_volatility) }}</strong>
                <small>annualized · 252</small>
              </article>
              <article class="pnl-kpi">
                <span class="metric-label-with-help">Profit factor / Win rate <MetricHelp :help="PNL_HELP.profitFactorWinRate" /></span>
                <strong>{{ formatNumber(pnlReport.risk.profit_factor) }} / {{ formatPercent(pnlReport.risk.win_rate) }}</strong>
                <small>{{ pnlReport.risk.positive_days }}+ / {{ pnlReport.risk.negative_days }}− дней</small>
              </article>
            </section>

            <PnlReportCharts :report="pnlReport" />

            <section class="pnl-detail-grid">
              <article class="pnl-detail-card">
                <header>
                  <span>Денежный результат</span>
                  <strong>Costs &amp; income</strong>
                </header>
                <dl>
                  <div><dt class="metric-label-with-help">Realized PnL брокера <MetricHelp :help="PNL_HELP.realizedPnl" /></dt><dd>{{ formatValue(pnlReport.summary.realized_pnl_broker) }}</dd></div>
                  <div><dt class="metric-label-with-help">Unrealized, оценка на конец <MetricHelp :help="PNL_HELP.unrealizedPnl" /></dt><dd>{{ formatValue(pnlReport.summary.unrealized_pnl_estimate) }}</dd></div>
                  <div><dt class="metric-label-with-help">Дивиденды <MetricHelp :help="PNL_HELP.dividends" /></dt><dd>{{ formatValue(pnlReport.summary.dividends) }}</dd></div>
                  <div><dt class="metric-label-with-help">Купоны <MetricHelp :help="PNL_HELP.coupons" /></dt><dd>{{ formatValue(pnlReport.summary.coupons) }}</dd></div>
                  <div><dt class="metric-label-with-help">Комиссии <MetricHelp :help="PNL_HELP.fees" /></dt><dd class="negative">{{ formatValue(pnlReport.summary.fees) }}</dd></div>
                  <div><dt class="metric-label-with-help">Налоги <MetricHelp :help="PNL_HELP.taxes" /></dt><dd class="negative">{{ formatValue(pnlReport.summary.taxes) }}</dd></div>
                  <div><dt class="metric-label-with-help">Вводы <MetricHelp :help="PNL_HELP.inflows" /></dt><dd>{{ formatValue(pnlReport.summary.inflows) }}</dd></div>
                  <div><dt class="metric-label-with-help">Выводы <MetricHelp :help="PNL_HELP.outflows" /></dt><dd>{{ formatValue(pnlReport.summary.outflows) }}</dd></div>
                </dl>
              </article>

              <article class="pnl-detail-card">
                <header>
                  <span>Торговая активность</span>
                  <strong>Execution statistics</strong>
                </header>
                <dl>
                  <div><dt class="metric-label-with-help">Сделок <MetricHelp :help="PNL_HELP.trades" /></dt><dd>{{ pnlReport.summary.trades }}</dd></div>
                  <div><dt class="metric-label-with-help">Покупок / продаж <MetricHelp :help="PNL_HELP.buysSells" /></dt><dd>{{ pnlReport.summary.buys }} / {{ pnlReport.summary.sells }}</dd></div>
                  <div><dt class="metric-label-with-help">Оборот <MetricHelp :help="PNL_HELP.turnover" /></dt><dd>{{ formatValue(pnlReport.summary.turnover) }}</dd></div>
                  <div><dt class="metric-label-with-help">Turnover ratio <MetricHelp :help="PNL_HELP.turnoverRatio" /></dt><dd>{{ formatPercent(pnlReport.summary.turnover_ratio) }}</dd></div>
                  <div><dt class="metric-label-with-help">Лучший день <MetricHelp :help="PNL_HELP.bestDay" /></dt><dd class="positive">{{ formatValue(pnlReport.risk.best_day_pnl) }}</dd></div>
                  <div><dt class="metric-label-with-help">Худший день <MetricHelp :help="PNL_HELP.worstDay" /></dt><dd class="negative">{{ formatValue(pnlReport.risk.worst_day_pnl) }}</dd></div>
                  <div><dt class="metric-label-with-help">Historical VaR 95% <MetricHelp :help="PNL_HELP.historicalVar95" /></dt><dd>{{ formatValue(pnlReport.risk.historical_var_95_amount) }}</dd></div>
                  <div><dt class="metric-label-with-help">Calmar <MetricHelp :help="PNL_HELP.calmar" /></dt><dd>{{ formatNumber(pnlReport.risk.calmar_ratio) }}</dd></div>
                </dl>
              </article>
            </section>

            <section class="pnl-table-card">
              <header>
                <div>
                  <span class="metric-label-with-help">Attribution <MetricHelp :help="PNL_HELP.attribution" /></span>
                  <strong>Вклад инструментов в PnL</strong>
                </div>
                <small>{{ pnlReport.attribution.length }} инструментов</small>
              </header>
              <div class="pnl-table-shell">
                <table class="pnl-table">
                  <thead>
                    <tr>
                      <th><span class="metric-label-with-help">Ticker <MetricHelp :help="PNL_HELP.ticker" /></span></th>
                      <th><span class="metric-label-with-help">Кол-во начало <MetricHelp :help="PNL_HELP.openingQuantity" /></span></th>
                      <th><span class="metric-label-with-help">Кол-во конец <MetricHelp :help="PNL_HELP.endingQuantity" /></span></th>
                      <th><span class="metric-label-with-help">Стоимость начало <MetricHelp :help="PNL_HELP.openingValue" /></span></th>
                      <th><span class="metric-label-with-help">Стоимость конец <MetricHelp :help="PNL_HELP.endingValue" /></span></th>
                      <th><span class="metric-label-with-help">Вклад PnL <MetricHelp :help="PNL_HELP.pnlContribution" /></span></th>
                      <th><span class="metric-label-with-help">Realized <MetricHelp :help="PNL_HELP.instrumentRealized" /></span></th>
                      <th><span class="metric-label-with-help">Оборот <MetricHelp :help="PNL_HELP.instrumentTurnover" /></span></th>
                      <th><span class="metric-label-with-help">Сделок <MetricHelp :help="PNL_HELP.instrumentTrades" /></span></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in pnlReport.attribution" :key="row.instrument_id">
                      <td><strong>{{ row.ticker }}</strong><small>{{ row.name }}</small></td>
                      <td>{{ formatNumber(row.opening_quantity, 4) }}</td>
                      <td>{{ formatNumber(row.ending_quantity, 4) }}</td>
                      <td>{{ formatValue(row.opening_value) }}</td>
                      <td>{{ formatValue(row.ending_value) }}</td>
                      <td :class="{ positive: row.pnl_contribution >= 0, negative: row.pnl_contribution < 0 }">
                        {{ formatValue(row.pnl_contribution) }}
                      </td>
                      <td>{{ formatValue(row.realized_pnl_broker) }}</td>
                      <td>{{ formatValue(row.turnover) }}</td>
                      <td>{{ row.trades }}</td>
                    </tr>
                    <tr v-if="!pnlReport.attribution.length"><td colspan="9">Нет инструментов за период</td></tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section class="pnl-table-card monthly-card">
              <header>
                <div>
                  <span class="metric-label-with-help">Monthly performance <MetricHelp :help="PNL_HELP.monthlyPerformance" /></span>
                  <strong>Доходность по месяцам</strong>
                </div>
              </header>
              <div class="pnl-table-shell">
                <table class="pnl-table monthly-table">
                  <thead>
                    <tr>
                      <th><span class="metric-label-with-help">Месяц <MetricHelp :help="PNL_HELP.month" /></span></th>
                      <th><span class="metric-label-with-help">Доходность <MetricHelp :help="PNL_HELP.monthReturn" /></span></th>
                      <th><span class="metric-label-with-help">PnL <MetricHelp :help="PNL_HELP.monthPnl" /></span></th>
                      <th><span class="metric-label-with-help">NAV на конец <MetricHelp :help="PNL_HELP.monthEndingNav" /></span></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in pnlReport.monthly_returns" :key="row.month">
                      <td>{{ row.month }}</td>
                      <td :class="{ positive: row.return >= 0, negative: row.return < 0 }">{{ formatPercent(row.return) }}</td>
                      <td :class="{ positive: row.pnl >= 0, negative: row.pnl < 0 }">{{ formatValue(row.pnl) }}</td>
                      <td>{{ formatValue(row.ending_nav) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <footer class="pnl-methodology">
              <strong class="metric-label-with-help">Методика <MetricHelp :help="PNL_HELP.methodology" /></strong>
              <span>
                Transaction replay + mark-to-market. Операции: {{ pnlReport.data_quality.operations }};
                <span class="metric-label-with-help">покрытие ценами <MetricHelp :help="PNL_HELP.priceCoverage" /></span>:
                {{ pnlReport.data_quality.priced_instruments }} из {{ pnlReport.data_quality.total_instruments }}
                ({{ formatPercent(pnlReport.data_quality.price_coverage) }}).
              </span>
              <span>
                Источники: {{ pnlReport.data_quality.operations_source }} · {{ pnlReport.data_quality.prices_source }}.
                Отчет аналитический и не заменяет официальный брокерский или налоговый отчет.
              </span>
            </footer>
          </template>

          <section v-else class="pnl-empty-state">
            <FileChartColumn :size="34" />
            <strong>Выберите период и сформируйте отчет</strong>
            <span>Будут загружены операции, комиссии, налоги, выплаты и дневные цены T-Invest.</span>
          </section>
        </div>
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
                <span>План ребалансировки</span>
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
                  <select v-model="strategyRunSettings.order_type" disabled>
                    <option value="market">Market</option>
                  </select>
                </label>
                <label>
                  <span>Мин. сумма (0 = все дельты)</span>
                  <input v-model.number="strategyRunSettings.min_order_value" min="0" step="100" type="number" />
                </label>
                <label>
                  <span>Резерв cash (0.01 = 1%)</span>
                  <input v-model.number="strategyRunSettings.cash_buffer_pct" min="0" max="0.2" step="0.005" type="number" />
                </label>
              </div>
              <button
                class="primary-button"
                type="button"
                :disabled="isRunningStrategy || !selectedStrategyAssignment"
                @click="runSelectedStrategy"
              >
                <Play :class="{ spin: isRunningStrategy }" :size="16" />
                Рассчитать план
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
                <strong>
                  {{ strategyRunResult?.summary.planned_target_positions ?? 0 }} из
                  {{ strategyRunResult?.summary.model_target_positions ?? 0 }}
                </strong>
              </article>
              <article>
                <span>Приказы</span>
                <strong>{{ strategyRunResult?.summary.orders ?? 0 }}</strong>
              </article>
              <article>
                <span>Стоп/тейк / позиции</span>
                <strong>{{ strategyRunResult?.summary.stop_orders ?? 0 }} / {{ strategyStopPositionCount }}</strong>
              </article>
              <article>
                <span>Cash сейчас</span>
                <strong>{{ formatValue(strategyRunResult?.summary.available_cash) }}</strong>
              </article>
              <article>
                <span>Cash после плана</span>
                <strong :class="{ positive: Number(strategyRunResult?.summary.estimated_cash_after_orders ?? 0) >= 0, negative: Number(strategyRunResult?.summary.estimated_cash_after_orders ?? 0) < 0 }">
                  {{ formatValue(strategyRunResult?.summary.estimated_cash_after_orders) }}
                </strong>
              </article>
            </section>

            <section v-if="strategyRunResult" class="strategy-box execution-box">
              <header>
                <span>Исполнение модели</span>
                <strong>{{ submissionModeLabel }} / {{ strategyRunResult.plan_id.slice(0, 12) }}</strong>
              </header>
              <div class="execution-copy">
                <span>
                  Сервер повторно сверит портфель и план, затем отправит рыночные продажи и только после них покупки.
                  Стопы и тейки в этот пакет не входят.
                </span>
                <div class="strategy-plan-explanation">
                  <span>
                    Модель: <strong>{{ strategyRunResult.summary.model_target_positions }}</strong> бумаг;
                    достижимо целыми лотами: <strong>{{ strategyRunResult.summary.planned_target_positions }}</strong>.
                  </span>
                  <span>
                    Ниже стоимости одного лота: <strong>{{ strategyRunResult.summary.below_one_lot_target_positions }}</strong>;
                    ограничено деньгами: <strong>{{ strategyRunResult.summary.cash_limited_target_positions }}</strong>.
                  </span>
                  <span>
                    Для одного лота каждой цели по известным ценам нужно минимум
                    <strong>{{ formatValue(strategyRunResult.summary.minimum_one_lot_cost) }}</strong>.
                  </span>
                </div>
                <ul v-if="strategyRunResult.execution.warnings.length" class="execution-warnings">
                  <li v-for="warning in strategyRunResult.execution.warnings" :key="warning">{{ warning }}</li>
                </ul>
                <ul v-if="strategyRunResult.execution.blocking_reasons.length" class="execution-blockers">
                  <li v-for="reason in strategyRunResult.execution.blocking_reasons" :key="reason">{{ reason }}</li>
                </ul>
              </div>
              <button
                class="primary-button execute-button"
                type="button"
                :disabled="
                  isExecutingStrategy ||
                  !canSubmitOrders ||
                  !strategyRunResult.execution.ready ||
                  strategyPlanAlreadyExecuted
                "
                @click="executeSelectedStrategy"
              >
                <Send :class="{ spin: isExecutingStrategy }" :size="16" />
                {{
                  strategyPlanAlreadyExecuted
                    ? "План уже отправлен"
                    : `Исполнить ${strategyRunResult.orders.length} рыночных заявок`
                }}
              </button>
              <small v-if="!canSubmitOrders" class="permission-hint">
                Нужна роль «Торговый оператор» (право {{ requiredSubmissionPermission }})
              </small>

              <div v-if="strategyExecutionResult" class="execution-result">
                <strong>{{ strategyExecutionResult.status }}</strong>
                <span>
                  submitted {{ strategyExecutionResult.summary.submitted }}, simulated
                  {{ strategyExecutionResult.summary.simulated }}, failed
                  {{ strategyExecutionResult.summary.failed }}, skipped
                  {{ strategyExecutionResult.summary.skipped }}
                </span>
                <div v-if="strategyExecutionFailures.length" class="execution-failure-summary">
                  <strong>Не исполнено: {{ strategyExecutionFailures.length }}</strong>
                  <ul>
                    <li
                      v-for="row in strategyExecutionFailures"
                      :key="`failure-${row.ticker}-${row.side}`"
                    >
                      <b>
                        {{ row.ticker }} · {{ strategySideLabel(row.side) }}
                        {{ row.quantity_lots }} лот.
                      </b>
                      <span>{{ strategyExecutionError(row) }}</span>
                    </li>
                  </ul>
                </div>
                <div class="strategy-table-shell compact-strategy-table">
                  <table class="strategy-table execution-result-table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Side</th>
                        <th>Lots</th>
                        <th>Status</th>
                        <th>Broker ID</th>
                        <th>Ошибка</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in strategyExecutionResult.results" :key="`${row.ticker}-${row.side}`">
                        <td>{{ row.ticker }}</td>
                        <td>{{ strategySideLabel(row.side) }}</td>
                        <td>{{ row.quantity_lots }}</td>
                        <td :class="{ positive: row.status === 'submitted' || row.status === 'simulated', negative: row.status === 'failed' }">
                          {{ row.status }}
                        </td>
                        <td>{{ row.broker_order_id || "n/a" }}</td>
                        <td class="execution-error-cell">
                          {{ row.status === "failed" || row.status === "skipped" ? strategyExecutionError(row) : "—" }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
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
                        <th>Модель</th>
                        <th>Один лот</th>
                        <th>План</th>
                        <th>Действие</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in strategyRunResult?.target_weights ?? []" :key="row.ticker">
                        <td>
                          <strong>{{ row.ticker }}</strong>
                          <small>{{ row.name }}</small>
                        </td>
                        <td>
                          {{ formatPercent(row.current_weight) }}
                          <small>{{ formatNumber(row.current_lots, 0) }} лот.</small>
                        </td>
                        <td>
                          {{ formatPercent(row.target_weight) }}
                          <small>{{ formatValue(row.target_value) }}</small>
                        </td>
                        <td>{{ formatValue(row.one_lot_value) }}</td>
                        <td>
                          {{ row.target_lots }} лот.
                          <small>{{ formatPercent(row.planned_weight) }}</small>
                        </td>
                        <td :class="{ positive: row.delta_lots > 0, negative: row.delta_lots < 0 }">
                          {{ strategyDeltaLabel(row.delta_lots) }}
                          <small v-if="row.constraint">{{ strategyConstraintLabel(row.constraint) }}</small>
                          <small v-if="row.blocked_lots">blocked {{ row.blocked_lots }}</small>
                        </td>
                      </tr>
                      <tr v-if="!strategyRunResult?.target_weights.length">
                        <td colspan="6">Нет расчета</td>
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
                <span>Стопы и тейки для позиций после плана</span>
                <strong>{{ strategyRunResult?.stop_orders.length ?? 0 }} / {{ strategyStopPositionCount }} поз.</strong>
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
