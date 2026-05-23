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
  Loader2,
  LogOut,
  RefreshCw,
  Send,
  ShieldCheck,
  WalletCards,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import {
  clearAuthTokens,
  createOrder,
  createStopOrder,
  getAccounts,
  getCurrentUser,
  getOverview,
} from "./api";
import AllocationBarChart from "./components/AllocationBarChart.vue";
import AllocationChart from "./components/AllocationChart.vue";
import OperationsCashflowChart from "./components/OperationsCashflowChart.vue";
import type {
  AccountItem,
  AccountOverview,
  MoneyAmount,
  OperationItem,
  OrderTicket,
  PortfolioPosition,
  StopOrderTicket,
  StubResponse,
  User,
} from "./types";

const docsHref = "/docs/?lang=ru";
const authHref = "/tech/auth/?returnTo=/execution/";

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

const orderTicket = ref<OrderTicket>({
  instrument_id: "",
  figi: "",
  side: "buy",
  order_type: "limit",
  quantity: 1,
  price: null,
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
            <strong>Stub mode</strong>
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
              <div class="segmented">
                <button type="button" :class="{ active: activeTicket === 'order' }" @click="activeTicket = 'order'">
                  Order
                </button>
                <button type="button" :class="{ active: activeTicket === 'stop' }" @click="activeTicket = 'stop'">
                  Stop
                </button>
              </div>
            </header>

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
                Создать stub
              </button>
            </form>

            <form v-else class="ticket-form" @submit.prevent="submitStopOrder">
              <label>
                <span>Instrument ID</span>
                <input v-model.trim="stopTicket.instrument_id" required placeholder="FIGI or UID" />
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
                Создать stub
              </button>
            </form>

            <div v-if="latestStub" class="stub-result">
              <span>{{ latestStub.status }}</span>
              <strong>{{ latestStub.id }}</strong>
              <small>{{ formatDateTime(latestStub.created_at) }}</small>
            </div>
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
  </div>
</template>
