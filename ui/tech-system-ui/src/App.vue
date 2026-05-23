<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Filter,
  Home,
  KeyRound,
  KeySquare,
  Loader2,
  LockKeyhole,
  LogIn,
  LogOut,
  Mail,
  RefreshCw,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  UserRound,
  UserPlus,
  Users,
  XCircle,
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiError,
  approveRoleRequest,
  clearAuthSession,
  createRoleRequest,
  fetchEventLogFilterOptions,
  fetchEventLogs,
  fetchCurrentUser,
  fetchMyRoleRequests,
  fetchPermissions,
  fetchProfileRoles,
  fetchRequestableRoles,
  fetchRoleRequests,
  fetchRoles,
  fetchUsers,
  login,
  logout,
  register,
  rejectRoleRequest,
  saveAuthSession,
  type EventLogEntry,
  type EventLogFilters,
  type Permission,
  type Role,
  type RoleAssignment,
  type RoleRequest,
  type User,
} from "./api";

type Mode = "login" | "register";
type SystemView = "home" | "event_logs" | "access";

const mode = ref<Mode>("login");
const email = ref("");
const password = ref("");
const user = ref<User | null>(null);
const isCheckingSession = ref(true);
const isSubmitting = ref(false);
const errorMessage = ref("");
const currentPath = ref(window.location.pathname);
const activeSystemView = ref<SystemView>("home");

const query = new URLSearchParams(window.location.search);
const requestedReturnTo = query.get("returnTo");
const profileHref = "/tech/profile/";
const systemHref = "/tech/system/";
const launchpadHref = "/launchpad/";
const authProfileHref = `/tech/auth/?returnTo=${profileHref}`;
const authSystemHref = `/tech/auth/?returnTo=${systemHref}`;

const isProfilePage = computed(() => currentPath.value.startsWith(profileHref));
const isSystemPage = computed(() => currentPath.value.startsWith(systemHref));

const returnTo = computed(() => {
  if (requestedReturnTo?.startsWith("/") && !requestedReturnTo.startsWith("//")) {
    return requestedReturnTo;
  }
  return launchpadHref;
});

const title = computed(() => (mode.value === "login" ? "Вход в ITS" : "Создание аккаунта"));
const actionText = computed(() => (mode.value === "login" ? "Войти" : "Создать аккаунт"));
const switchText = computed(() =>
  mode.value === "login" ? "Нужен аккаунт" : "Уже есть аккаунт",
);
const eventLogColumns = ref<string[]>([
  "id",
  "date_time",
  "service",
  "user",
  "http_action",
  "ip_address",
  "path",
  "header",
  "body",
]);
const eventLogs = ref<EventLogEntry[]>([]);
const profileRoles = ref<RoleAssignment[]>([]);
const requestableRoles = ref<Role[]>([]);
const myRoleRequests = ref<RoleRequest[]>([]);
const selectedRoleCode = ref("");
const roleJustification = ref("");
const roleRequestMessage = ref("");
const profileAccessError = ref("");
const isProfileAccessLoading = ref(false);
const accessRoles = ref<Role[]>([]);
const accessUsers = ref<User[]>([]);
const accessPermissions = ref<Permission[]>([]);
const accessRoleRequests = ref<RoleRequest[]>([]);
const accessDecisionComments = reactive<Record<string, string>>({});
const accessError = ref("");
const isAccessLoading = ref(false);
const eventLogServiceOptions = ref<string[]>([]);
const eventLogUserOptions = ref<string[]>([]);
const eventLogTotal = ref(0);
const eventLogLimit = ref(100);
const eventLogOffset = ref(0);
const isEventLogsLoading = ref(false);
const eventLogsError = ref("");
const eventLogFilters = reactive<Record<keyof Omit<EventLogFilters, "limit" | "offset">, string>>({
  id: "",
  date_time_from: "",
  date_time_to: "",
  service: "",
  user: "",
  http_action: "",
  ip_address: "",
  path: "",
  header: "",
  body: "",
});
const hasNextEventPage = computed(
  () => eventLogOffset.value + eventLogLimit.value < eventLogTotal.value,
);
const eventLogRange = computed(() => {
  if (eventLogTotal.value === 0) return "0 / 0";
  const start = eventLogOffset.value + 1;
  const end = Math.min(eventLogOffset.value + eventLogs.value.length, eventLogTotal.value);
  return `${start}-${end} / ${eventLogTotal.value}`;
});
const permissionGroups = computed(() => groupPermissionLabels(user.value?.permissions || []));
const canViewEventLogs = computed(() => hasPermission("system.logs.read"));
const canManageAccess = computed(() =>
  hasAnyPermission([
    "user.read",
    "role.read",
    "permission.read",
    "role.request.read",
    "role.request.approve",
  ]),
);

const roleTitles: Record<string, string> = {
  documentation_reader: "Документация",
  viewer: "Наблюдатель",
  quant_researcher: "Исследователь стратегий",
  data_manager: "Менеджер данных",
  strategy_releaser: "Ответственный за релиз стратегии",
  production_approver: "Согласующий production",
  trading_operator: "Оператор торгового контура",
  risk_manager: "Риск-менеджер",
  secret_manager: "Администратор секретов",
  role_admin: "Администратор доступа",
  system_admin: "Системный администратор",
  auditor: "Аудитор",
};

const roleDescriptions: Record<string, string> = {
  documentation_reader: "Первичный доступ к документации и заявкам на расширение доступа.",
  viewer: "Просмотр доступных разделов, отчетов и документации без запуска расчетов.",
  quant_researcher: "Работа с гипотезами, моделями стратегий, проверками и GA-запусками.",
  data_manager: "Загрузка рыночных данных, справочников и управление источниками данных.",
  strategy_releaser: "Подготовка стратегии к передаче в production-контур.",
  production_approver: "Проверка и согласование заявок на вывод стратегии в production.",
  trading_operator: "Запуск и остановка paper/live торговых процессов без доступа к секретам.",
  risk_manager: "Контроль лимитов, риск-согласование и остановка торгового контура.",
  secret_manager: "Создание, обновление и ротация ссылок на секреты без чтения их значений.",
  role_admin: "Управление пользователями, ролями, заявками и историей изменений доступа.",
  system_admin: "Управление техническим состоянием ITS, настройками, журналами и интеграциями.",
  auditor: "Просмотр истории действий, заявок и изменений без права вносить изменения.",
};

const permissionTitles: Record<string, string> = {
  "app.launchpad.read": "Открытие рабочего стола",
  "app.docs.read": "Просмотр документации",
  "profile.self.read": "Просмотр своего профиля",
  "profile.self.update": "Обновление своего профиля",
  "data.sources.read": "Просмотр источников данных",
  "data.instruments.read": "Просмотр инструментов",
  "data.prices.read": "Просмотр котировок",
  "data.dividends.read": "Просмотр дивидендов",
  "data.custom_bars.read": "Просмотр производных баров",
  "data.upload.create": "Загрузка новых данных",
  "data.upload.read": "Просмотр истории загрузок",
  "data.version.deactivate": "Деактивация версии данных",
  "data.source.create": "Добавление источника данных",
  "data.source.update": "Обновление источника данных",
  "strategy.component.read": "Просмотр компонентов стратегий",
  "strategy.component.create": "Создание компонентов стратегий",
  "strategy.component.update": "Обновление компонентов стратегий",
  "strategy.component.delete": "Удаление компонентов стратегий",
  "strategy.model.read": "Просмотр моделей стратегий",
  "strategy.model.create": "Создание моделей стратегий",
  "strategy.model.update": "Обновление моделей стратегий",
  "strategy.model.delete": "Удаление моделей стратегий",
  "strategy.test.run": "Запуск проверок стратегий",
  "strategy.test.read": "Просмотр результатов проверок",
  "strategy.compare.read": "Сравнение стратегий",
  "strategy.production.request": "Подготовка стратегии к production",
  "ga.alphabet.read": "Просмотр алфавитов GA",
  "ga.alphabet.update": "Обновление алфавитов GA",
  "ga.run.create": "Запуск GA",
  "ga.run.read": "Просмотр результатов GA",
  "ga.run.cancel": "Остановка GA-запуска",
  "ga.candidate.materialize": "Материализация GA-кандидата",
  "production.strategy.request": "Создание заявки на production",
  "production.strategy.read": "Просмотр production-стратегий",
  "production.strategy.approve": "Согласование production",
  "production.strategy.reject": "Отклонение production-заявки",
  "production.strategy.deploy": "Размещение production-стратегии",
  "production.strategy.disable": "Отключение production-стратегии",
  "trading.paper.start": "Запуск paper trading",
  "trading.paper.stop": "Остановка paper trading",
  "trading.live.start": "Запуск live trading",
  "trading.live.stop": "Остановка live trading",
  "trading.orders.read": "Просмотр ордеров",
  "trading.trades.read": "Просмотр сделок",
  "trading.positions.read": "Просмотр позиций",
  "trading.emergency_stop": "Аварийная остановка торговли",
  "risk.limits.read": "Просмотр риск-лимитов",
  "risk.limits.update": "Изменение риск-лимитов",
  "risk.events.read": "Просмотр риск-событий",
  "risk.strategy.approve": "Риск-согласование стратегии",
  "risk.strategy.block": "Блокировка стратегии по риску",
  "secret.reference.read": "Просмотр ссылок на секреты",
  "secret.reference.create": "Создание ссылки на секрет",
  "secret.reference.update": "Обновление ссылки на секрет",
  "secret.reference.delete": "Удаление ссылки на секрет",
  "secret.reference.rotate": "Ротация секрета",
  "broker.account.read": "Просмотр брокерских аккаунтов",
  "broker.account.create": "Создание брокерского аккаунта",
  "broker.account.update": "Обновление брокерского аккаунта",
  "user.read": "Просмотр пользователей",
  "user.update": "Обновление пользователей",
  "user.block": "Блокировка пользователей",
  "role.read": "Просмотр уровней доступа",
  "role.create": "Создание уровня доступа",
  "role.update": "Обновление уровня доступа",
  "role.delete": "Удаление уровня доступа",
  "role.assign": "Назначение уровня доступа",
  "role.revoke": "Отзыв уровня доступа",
  "role.request.create": "Создание заявки на доступ",
  "role.request.read": "Просмотр заявок на доступ",
  "role.request.approve": "Одобрение заявки на доступ",
  "role.request.reject": "Отклонение заявки на доступ",
  "permission.read": "Просмотр прав доступа",
  "audit.auth.read": "Просмотр истории входов",
  "audit.role.read": "Просмотр истории доступа",
  "audit.production.read": "Просмотр production-аудита",
  "audit.trading.read": "Просмотр торгового аудита",
  "audit.secret.read": "Просмотр аудита секретов",
  "system.health.read": "Просмотр состояния системы",
  "system.settings.read": "Просмотр системных настроек",
  "system.settings.update": "Изменение системных настроек",
  "system.logs.read": "Просмотр системных журналов",
  "system.integrations.manage": "Управление интеграциями",
};

const permissionDomains: Record<string, string> = {
  app: "Рабочая среда",
  profile: "Профиль",
  data: "Данные рынка",
  strategy: "Стратегии",
  ga: "GA Lab",
  production: "Production",
  trading: "Торговый контур",
  risk: "Риски",
  secret: "Секреты",
  broker: "Брокерские аккаунты",
  user: "Пользователи",
  role: "Управление доступом",
  permission: "Права доступа",
  audit: "Аудит",
  system: "Система",
};

function hasPermission(permission: string): boolean {
  return user.value?.permissions.includes(permission) ?? false;
}

function hasAnyPermission(permissions: string[]): boolean {
  return permissions.some((permission) => hasPermission(permission));
}

function displayRoleTitle(role: { code: string; title: string }): string {
  return roleTitles[role.code] || role.title;
}

function displayRoleDescription(role: { code: string; description?: string | null }): string {
  return roleDescriptions[role.code] || role.description || "Описание пока не задано";
}

function displayPermissionTitle(permission: string | Permission): string {
  const code = typeof permission === "string" ? permission : permission.code;
  return permissionTitles[code] || (typeof permission === "string" ? permission : permission.title);
}

function displayRequestStatus(status: string): string {
  if (status === "pending") return "На рассмотрении";
  if (status === "approved") return "Одобрена";
  if (status === "rejected") return "Отклонена";
  if (status === "cancelled") return "Отменена";
  return status;
}

function groupPermissionLabels(permissions: string[]) {
  const grouped = permissions.reduce<Record<string, { code: string; title: string }[]>>(
    (acc, permission) => {
      const domain = permission.split(".")[0] || "other";
      acc[domain] = acc[domain] || [];
      acc[domain].push({ code: permission, title: displayPermissionTitle(permission) });
      return acc;
    },
    {},
  );

  return Object.entries(grouped).map(([domain, items]) => ({
    domain,
    title: permissionDomains[domain] || domain,
    items,
  }));
}

function mapError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return "Пользователь с таким email уже существует.";
    if (error.status === 401) return "Неверный email или пароль.";
    if (error.status === 422) return "Проверьте email и длину пароля.";
    return error.message;
  }
  return "Сервис авторизации временно недоступен.";
}

function switchMode() {
  errorMessage.value = "";
  mode.value = mode.value === "login" ? "register" : "login";
}

function continueToLaunchpad() {
  window.location.assign(returnTo.value);
}

function openLaunchpad() {
  window.location.assign(launchpadHref);
}

function openProfile() {
  window.location.assign(profileHref);
}

function formatDate(value: string | null): string {
  if (!value) return "Пока нет данных";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

async function submit() {
  errorMessage.value = "";
  isSubmitting.value = true;

  try {
    const response =
      mode.value === "login"
        ? await login(email.value, password.value)
        : await register(email.value, password.value);
    saveAuthSession(response);
    user.value = response.user;
    continueToLaunchpad();
  } catch (error) {
    errorMessage.value = mapError(error);
  } finally {
    isSubmitting.value = false;
  }
}

async function signOut() {
  await logout();
  user.value = null;
  password.value = "";
  if (isProfilePage.value || isSystemPage.value) {
    window.location.replace("/tech/auth/");
  }
}

function mapEventLogError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Сессия истекла. Выполните вход еще раз.";
    return error.message;
  }
  return "Сервис event log временно недоступен.";
}

function buildEventLogFilters(): EventLogFilters {
  return {
    id: eventLogFilters.id,
    date_time_from: eventLogFilters.date_time_from,
    date_time_to: eventLogFilters.date_time_to,
    service: eventLogFilters.service,
    user: eventLogFilters.user,
    http_action: eventLogFilters.http_action,
    ip_address: eventLogFilters.ip_address,
    path: eventLogFilters.path,
    header: eventLogFilters.header,
    body: eventLogFilters.body,
    limit: eventLogLimit.value,
    offset: eventLogOffset.value,
  };
}

async function loadEventLogFilterOptions() {
  const response = await fetchEventLogFilterOptions();
  eventLogServiceOptions.value = response.services;
  eventLogUserOptions.value = response.users;
}

async function openEventLogs() {
  if (!canViewEventLogs.value) return;
  activeSystemView.value = "event_logs";
  eventLogOffset.value = 0;
  eventLogsError.value = "";
  try {
    await Promise.all([loadEventLogFilterOptions(), loadEventLogs()]);
  } catch (error) {
    eventLogsError.value = mapEventLogError(error);
    if (error instanceof ApiError && error.status === 401) {
      clearAuthSession();
      window.location.replace(authSystemHref);
    }
  }
}

async function openAccessManagement() {
  activeSystemView.value = "access";
  await loadAccessManagement();
}

function closeEventLogs() {
  activeSystemView.value = "home";
}

function closeAccessManagement() {
  activeSystemView.value = "home";
}

async function loadProfileAccess() {
  if (!isProfilePage.value || !user.value) return;
  profileAccessError.value = "";
  isProfileAccessLoading.value = true;
  try {
    const [roles, requestable, requests] = await Promise.all([
      fetchProfileRoles(),
      fetchRequestableRoles(),
      fetchMyRoleRequests(),
    ]);
    profileRoles.value = roles;
    requestableRoles.value = requestable;
    myRoleRequests.value = requests;
    if (!selectedRoleCode.value && requestable.length > 0) {
      selectedRoleCode.value = requestable[0].code;
    }
  } catch (error) {
    profileAccessError.value = mapError(error);
  } finally {
    isProfileAccessLoading.value = false;
  }
}

async function submitRoleRequest() {
  if (!selectedRoleCode.value) return;
  roleRequestMessage.value = "";
  profileAccessError.value = "";
  try {
    await createRoleRequest(selectedRoleCode.value, roleJustification.value);
    roleJustification.value = "";
    roleRequestMessage.value = "Заявка отправлена на рассмотрение.";
    await loadProfileAccess();
  } catch (error) {
    profileAccessError.value = mapError(error);
  }
}

async function loadAccessManagement() {
  if (!isSystemPage.value || !user.value || activeSystemView.value !== "access") return;
  accessError.value = "";
  isAccessLoading.value = true;
  try {
    const [roles, permissions, users, requests] = await Promise.all([
      hasPermission("role.read") ? fetchRoles() : Promise.resolve([]),
      hasPermission("permission.read") ? fetchPermissions() : Promise.resolve([]),
      hasPermission("user.read") ? fetchUsers() : Promise.resolve([]),
      hasPermission("role.request.read") ? fetchRoleRequests() : Promise.resolve([]),
    ]);
    accessRoles.value = roles;
    accessPermissions.value = permissions;
    accessUsers.value = users;
    accessRoleRequests.value = requests;
    for (const request of requests) {
      accessDecisionComments[request.id] =
        accessDecisionComments[request.id] || "Решение администратора доступа.";
    }
  } catch (error) {
    accessError.value = mapError(error);
  } finally {
    isAccessLoading.value = false;
  }
}

async function approveAccessRequest(request: RoleRequest) {
  const comment = accessDecisionComments[request.id] || "";
  if (comment.trim().length < 3) return;
  await approveRoleRequest(request.id, comment);
  await loadAccessManagement();
}

async function rejectAccessRequest(request: RoleRequest) {
  const comment = accessDecisionComments[request.id] || "";
  if (comment.trim().length < 3) return;
  await rejectRoleRequest(request.id, comment);
  await loadAccessManagement();
}

async function loadEventLogs() {
  if (!isSystemPage.value || !user.value || activeSystemView.value !== "event_logs") return;
  eventLogsError.value = "";
  isEventLogsLoading.value = true;
  try {
    const response = await fetchEventLogs(buildEventLogFilters());
    eventLogColumns.value = response.columns;
    eventLogs.value = response.items;
    eventLogTotal.value = response.total;
    eventLogLimit.value = response.limit;
    eventLogOffset.value = response.offset;
  } catch (error) {
    eventLogsError.value = mapEventLogError(error);
    if (error instanceof ApiError && error.status === 401) {
      clearAuthSession();
      window.location.replace(authSystemHref);
    }
  } finally {
    isEventLogsLoading.value = false;
  }
}

function applyEventFilters() {
  eventLogOffset.value = 0;
  void loadEventLogs();
}

function resetEventFilters() {
  for (const key of Object.keys(eventLogFilters) as Array<keyof typeof eventLogFilters>) {
    eventLogFilters[key] = "";
  }
  eventLogOffset.value = 0;
  void loadEventLogs();
}

function previousEventPage() {
  eventLogOffset.value = Math.max(0, eventLogOffset.value - eventLogLimit.value);
  void loadEventLogs();
}

function nextEventPage() {
  if (!hasNextEventPage.value) return;
  eventLogOffset.value += eventLogLimit.value;
  void loadEventLogs();
}

function formatEventCell(row: EventLogEntry, column: string): string {
  const value = row[column as keyof EventLogEntry];
  if (column === "date_time" && typeof value === "string") {
    return formatDate(value);
  }
  if (column === "header" && value && typeof value === "object") {
    return JSON.stringify(value);
  }
  if (value === null || value === undefined || value === "") {
    return "";
  }
  return String(value);
}

onMounted(async () => {
  try {
    user.value = await fetchCurrentUser();
    if (requestedReturnTo && !isProfilePage.value) {
      continueToLaunchpad();
    }
    if (isSystemPage.value) {
      activeSystemView.value = "home";
    }
    if (isProfilePage.value) {
      await loadProfileAccess();
    }
  } catch {
    clearAuthSession();
    if (isSystemPage.value) {
      window.location.replace(authSystemHref);
    } else if (isProfilePage.value) {
      window.location.replace(authProfileHref);
    }
  } finally {
    isCheckingSession.value = false;
  }
});
</script>

<template>
  <div class="auth-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">
          <ShieldCheck :size="22" />
        </div>
        <div>
          <strong>ITS</strong>
          <span>Личный кабинет</span>
        </div>
      </div>
      <div class="top-actions">
        <a class="top-icon-button" href="/launchpad/" title="Launchpad" aria-label="Launchpad">
          <Home :size="18" />
        </a>
        <a class="ghost-link" href="/docs/" target="_blank" rel="noreferrer">
          Документация
          <ArrowRight :size="16" />
        </a>
      </div>
    </header>

    <main
      v-if="isSystemPage"
      :class="activeSystemView === 'event_logs' ? 'event-log-workspace' : 'system-workspace'"
    >
      <section v-if="activeSystemView === 'home'" class="tech-panel">
        <div v-if="isCheckingSession" class="loading-state">
          <Loader2 class="spin" :size="28" />
          <span>Проверка входа</span>
        </div>

        <template v-else-if="user">
          <div class="system-head">
            <div>
              <span class="eyebrow">
                <ShieldCheck :size="16" />
                Управление платформой
              </span>
              <h1>Управление платформой</h1>
              <p>Технические инструменты платформы: аудит, доступы, системные журналы и операции.</p>
            </div>
            <div class="session-actions">
              <button class="secondary-button" type="button" @click="openLaunchpad">
                <ArrowLeft :size="18" />
                Launchpad
              </button>
              <button class="secondary-button" type="button" @click="openProfile">
                <UserRound :size="18" />
                Профиль
              </button>
              <button class="secondary-button" type="button" @click="signOut">
                <LogOut :size="18" />
                Выйти
              </button>
            </div>
          </div>

          <div class="system-module-grid">
            <button
              class="system-module-card primary-module"
              type="button"
              :disabled="!canViewEventLogs"
              @click="openEventLogs"
            >
              <span class="module-icon" :class="{ muted: !canViewEventLogs }">
                <ScrollText :size="24" />
              </span>
              <span class="panel-kicker">Аудит</span>
              <strong>Журнал событий</strong>
              <p>История действий пользователей и сервисов по рабочим разделам платформы.</p>
            </button>
            <button
              class="system-module-card primary-module"
              type="button"
              :disabled="!canManageAccess"
              @click="openAccessManagement"
            >
              <span class="module-icon" :class="{ muted: !canManageAccess }">
                <Users :size="24" />
              </span>
              <span class="panel-kicker">Доступы</span>
              <strong>Управление доступом</strong>
              <p>Пользователи, роли, права и заявки на расширение доступа.</p>
            </button>
            <button class="system-module-card" type="button" disabled>
              <span class="module-icon muted">
                <Settings :size="24" />
              </span>
              <span class="panel-kicker">В планах</span>
              <strong>Настройки системы</strong>
              <p>Будущий раздел для технических параметров платформы.</p>
            </button>
          </div>
        </template>
      </section>

      <section v-else-if="activeSystemView === 'event_logs'" class="event-log-page">
        <div v-if="isCheckingSession" class="loading-state">
          <Loader2 class="spin" :size="28" />
          <span>Проверка входа</span>
        </div>

        <template v-else-if="user">
          <div class="event-toolbar">
            <div>
              <span class="eyebrow">
                <ScrollText :size="16" />
                Управление платформой
              </span>
              <h1>Журнал событий</h1>
            </div>
            <div class="event-toolbar-actions">
              <span>{{ eventLogRange }}</span>
              <button class="secondary-button" type="button" @click="closeEventLogs">
                <ArrowLeft :size="18" />
                Управление
              </button>
              <button class="icon-action" type="button" aria-label="Refresh" @click="loadEventLogs">
                <RefreshCw :class="{ spin: isEventLogsLoading }" :size="18" />
              </button>
            </div>
          </div>

          <form class="event-filters" @submit.prevent="applyEventFilters">
            <label>
              <span>id</span>
              <input v-model.trim="eventLogFilters.id" type="number" min="1" />
            </label>
            <fieldset class="date-range">
              <legend>date_time</legend>
              <label>
                <span>from</span>
                <input v-model="eventLogFilters.date_time_from" type="datetime-local" />
              </label>
              <label>
                <span>to</span>
                <input v-model="eventLogFilters.date_time_to" type="datetime-local" />
              </label>
            </fieldset>
            <label>
              <span>service</span>
              <select v-model="eventLogFilters.service">
                <option value="">Все</option>
                <option v-for="service in eventLogServiceOptions" :key="service" :value="service">
                  {{ service }}
                </option>
              </select>
            </label>
            <label>
              <span>user</span>
              <select v-model="eventLogFilters.user">
                <option value="">Все</option>
                <option v-for="item in eventLogUserOptions" :key="item" :value="item">
                  {{ item }}
                </option>
              </select>
            </label>
            <label>
              <span>http_action</span>
              <select v-model="eventLogFilters.http_action">
                <option value="">Все</option>
                <option>GET</option>
                <option>POST</option>
                <option>PUT</option>
                <option>PATCH</option>
                <option>DELETE</option>
                <option>OPTIONS</option>
              </select>
            </label>
            <label>
              <span>ip_address</span>
              <input v-model.trim="eventLogFilters.ip_address" type="search" />
            </label>
            <label>
              <span>path</span>
              <input v-model.trim="eventLogFilters.path" type="search" />
            </label>
            <label>
              <span>header</span>
              <input v-model.trim="eventLogFilters.header" type="search" />
            </label>
            <label>
              <span>body</span>
              <input v-model.trim="eventLogFilters.body" type="search" />
            </label>

            <div class="filter-actions">
              <button class="primary-button" type="submit">
                <Search :size="18" />
                Найти
              </button>
              <button class="secondary-button" type="button" @click="resetEventFilters">
                <Filter :size="18" />
                Сбросить
              </button>
            </div>
          </form>

          <p v-if="eventLogsError" class="error-message event-error">
            <AlertCircle :size="18" />
            {{ eventLogsError }}
          </p>

          <div class="event-table-wrap">
            <table class="event-table">
              <thead>
                <tr>
                  <th v-for="column in eventLogColumns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="isEventLogsLoading">
                  <td :colspan="eventLogColumns.length" class="empty-cell">
                    <Loader2 class="spin" :size="22" />
                    Загрузка логов
                  </td>
                </tr>
                <tr v-else-if="eventLogs.length === 0">
                  <td :colspan="eventLogColumns.length" class="empty-cell">Нет записей</td>
                </tr>
                <template v-else>
                  <tr v-for="entry in eventLogs" :key="entry.id">
                    <td
                      v-for="column in eventLogColumns"
                      :key="`${entry.id}-${column}`"
                      :class="{ 'code-cell': column === 'header' || column === 'body' || column === 'path' }"
                    >
                      {{ formatEventCell(entry, column) }}
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>

          <div class="pager">
            <button class="secondary-button" type="button" :disabled="eventLogOffset === 0" @click="previousEventPage">
              Назад
            </button>
            <span>{{ eventLogRange }}</span>
            <button class="secondary-button" type="button" :disabled="!hasNextEventPage" @click="nextEventPage">
              Вперед
            </button>
          </div>
        </template>
      </section>

      <section v-else class="event-log-page access-page">
        <div v-if="isCheckingSession" class="loading-state">
          <Loader2 class="spin" :size="28" />
          <span>Проверка входа</span>
        </div>

        <template v-else-if="user">
          <div class="event-toolbar">
            <div>
              <span class="eyebrow">
                <Users :size="16" />
                Управление платформой
              </span>
              <h1>Управление доступом</h1>
            </div>
            <div class="event-toolbar-actions">
              <button class="secondary-button" type="button" @click="closeAccessManagement">
                <ArrowLeft :size="18" />
                Управление
              </button>
              <button class="icon-action" type="button" aria-label="Refresh" @click="loadAccessManagement">
                <RefreshCw :class="{ spin: isAccessLoading }" :size="18" />
              </button>
            </div>
          </div>

          <p v-if="accessError" class="error-message event-error">
            <AlertCircle :size="18" />
            {{ accessError }}
          </p>

          <div class="access-grid">
            <article class="access-section">
              <div class="section-head">
                <Users :size="20" />
                <h2>Пользователи</h2>
              </div>
              <div v-if="isAccessLoading" class="empty-cell">
                <Loader2 class="spin" :size="20" />
                Загрузка
              </div>
              <div v-else-if="accessUsers.length === 0" class="empty-cell">Нет данных</div>
              <table v-else class="compact-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Роли</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in accessUsers" :key="item.id">
                    <td>{{ item.email }}</td>
                    <td>{{ item.roles.map(displayRoleTitle).join(", ") || "без ролей" }}</td>
                    <td>{{ item.is_active ? "Активен" : "Отключен" }}</td>
                  </tr>
                </tbody>
              </table>
            </article>

            <article class="access-section">
              <div class="section-head">
                <KeySquare :size="20" />
                <h2>Роли</h2>
              </div>
              <div v-if="isAccessLoading" class="empty-cell">
                <Loader2 class="spin" :size="20" />
                Загрузка
              </div>
              <div v-else-if="accessRoles.length === 0" class="empty-cell">Нет данных</div>
              <div v-else class="role-list">
                <div v-for="role in accessRoles" :key="role.code" class="role-row">
                  <strong>{{ displayRoleTitle(role) }}</strong>
                  <span>{{ displayRoleDescription(role) }}</span>
                  <small>{{ role.permissions.length }} прав доступа</small>
                </div>
              </div>
            </article>

            <article class="access-section wide">
              <div class="section-head">
                <ClipboardList :size="20" />
                <h2>Заявки на доступ</h2>
              </div>
              <div v-if="isAccessLoading" class="empty-cell">
                <Loader2 class="spin" :size="20" />
                Загрузка
              </div>
              <div v-else-if="accessRoleRequests.length === 0" class="empty-cell">Нет заявок</div>
              <div v-else class="request-list">
                <div v-for="item in accessRoleRequests" :key="item.id" class="request-card">
                  <div>
                    <strong>{{ displayRoleTitle(item.role) }}</strong>
                    <span>{{ item.requester_email || item.requester_id }}</span>
                    <p>{{ item.justification }}</p>
                  </div>
                  <small :class="['status-badge', item.status]">{{ displayRequestStatus(item.status) }}</small>
                  <template v-if="item.status === 'pending'">
                    <textarea
                      v-model="accessDecisionComments[item.id]"
                      rows="2"
                      placeholder="Комментарий к решению"
                    ></textarea>
                    <div class="request-actions">
                      <button
                        class="primary-button"
                        type="button"
                        :disabled="!hasPermission('role.request.approve')"
                        @click="approveAccessRequest(item)"
                      >
                        <CheckCircle2 :size="18" />
                        Одобрить
                      </button>
                      <button
                        class="secondary-button"
                        type="button"
                        :disabled="!hasPermission('role.request.reject')"
                        @click="rejectAccessRequest(item)"
                      >
                        <XCircle :size="18" />
                        Отклонить
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </article>

            <article class="access-section wide">
              <div class="section-head">
                <KeyRound :size="20" />
                <h2>Права доступа</h2>
              </div>
              <div class="permission-cloud">
                <small v-for="permission in accessPermissions" :key="permission.code">
                  {{ displayPermissionTitle(permission) }}
                </small>
              </div>
            </article>
          </div>
        </template>
      </section>
    </main>

    <main v-else-if="isProfilePage" class="profile-workspace">
      <section class="profile-panel">
        <div v-if="isCheckingSession" class="loading-state">
          <Loader2 class="spin" :size="28" />
          <span>Проверка входа</span>
        </div>

        <template v-else-if="user">
          <div class="profile-head">
            <div>
              <span class="eyebrow">
                <UserRound :size="16" />
                Профиль
              </span>
              <h1>Аккаунт</h1>
              <p>{{ user.email }}</p>
            </div>
            <div class="session-actions">
              <button class="primary-button" type="button" @click="openLaunchpad">
                <Home :size="18" />
                Launchpad
              </button>
              <button class="secondary-button" type="button" @click="signOut">
                <LogOut :size="18" />
                Выйти
              </button>
            </div>
          </div>

          <div class="profile-grid">
            <article>
              <Mail :size="20" />
              <span>Email</span>
              <strong>{{ user.email }}</strong>
            </article>
            <article>
              <BadgeCheck :size="20" />
              <span>Статус</span>
              <strong>{{ user.is_active ? "Активен" : "Отключен" }}</strong>
            </article>
            <article>
              <CalendarDays :size="20" />
              <span>Дата регистрации</span>
              <strong>{{ formatDate(user.created_at) }}</strong>
            </article>
            <article>
              <LockKeyhole :size="20" />
              <span>Последний вход</span>
              <strong>{{ formatDate(user.last_login_at) }}</strong>
            </article>
          </div>

          <p v-if="profileAccessError" class="error-message event-error">
            <AlertCircle :size="18" />
            {{ profileAccessError }}
          </p>

          <div class="profile-access-grid">
            <article class="access-section">
              <div class="section-head">
                <KeySquare :size="20" />
                <h2>Мои роли</h2>
              </div>
              <div v-if="isProfileAccessLoading" class="empty-cell">
                <Loader2 class="spin" :size="20" />
                Загрузка
              </div>
              <div v-else-if="profileRoles.length === 0" class="empty-cell">Роли не назначены</div>
              <div v-else class="role-list">
                <div v-for="item in profileRoles" :key="item.role.code" class="role-row">
                  <strong>{{ displayRoleTitle(item.role) }}</strong>
                  <span>{{ displayRoleDescription(item.role) }}</span>
                  <small>Назначена: {{ formatDate(item.assigned_at) }}</small>
                </div>
              </div>
            </article>

            <article class="access-section">
              <div class="section-head">
                <KeyRound :size="20" />
                <h2>Мои права доступа</h2>
              </div>
              <div v-if="permissionGroups.length === 0" class="empty-cell">
                Права доступа не назначены
              </div>
              <div v-else class="permission-groups">
                <div v-for="group in permissionGroups" :key="group.domain">
                  <strong>{{ group.title }}</strong>
                  <small v-for="permission in group.items" :key="permission.code">
                    {{ permission.title }}
                  </small>
                </div>
              </div>
            </article>

            <article class="access-section">
              <div class="section-head">
                <ClipboardList :size="20" />
                <h2>Запросить доступ</h2>
              </div>
              <p v-if="roleRequestMessage" class="success-message">{{ roleRequestMessage }}</p>
              <form class="role-request-form" @submit.prevent="submitRoleRequest">
                <label>
                  <span>Уровень доступа</span>
                  <select v-model="selectedRoleCode" required>
                    <option v-for="role in requestableRoles" :key="role.code" :value="role.code">
                      {{ displayRoleTitle(role) }}
                    </option>
                  </select>
                </label>
                <label>
                  <span>Обоснование</span>
                  <textarea v-model.trim="roleJustification" rows="4" minlength="10" required></textarea>
                </label>
                <button class="primary-button" type="submit" :disabled="requestableRoles.length === 0">
                  <ArrowRight :size="18" />
                  Отправить заявку
                </button>
              </form>
            </article>

            <article class="access-section">
              <div class="section-head">
                <ScrollText :size="20" />
                <h2>Мои заявки</h2>
              </div>
              <div v-if="myRoleRequests.length === 0" class="empty-cell">Заявок пока нет</div>
              <div v-else class="request-list">
                <div v-for="item in myRoleRequests" :key="item.id" class="request-card">
                  <div>
                    <strong>{{ displayRoleTitle(item.role) }}</strong>
                    <span>{{ formatDate(item.created_at) }}</span>
                  </div>
                  <small :class="['status-badge', item.status]">{{ displayRequestStatus(item.status) }}</small>
                </div>
              </div>
            </article>
          </div>
        </template>
      </section>
    </main>

    <main v-else class="workspace">
      <section class="system-panel">
        <span class="eyebrow">
          <ShieldCheck :size="16" />
          Intelligent Trading Strategies
        </span>
        <h1>ITS Platform</h1>
        <p class="hero-note">Рыночные данные, торговые стратегии и проверка гипотез в единой рабочей среде.</p>
        <div class="signal-grid" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="status-list">
          <div>
            <BadgeCheck :size="18" />
            <span>Рыночные данные</span>
          </div>
          <div>
            <BadgeCheck :size="18" />
            <span>Торговые стратегии</span>
          </div>
          <div>
            <BadgeCheck :size="18" />
            <span>Проверка гипотез</span>
          </div>
        </div>
      </section>

      <section class="auth-panel">
        <div v-if="isCheckingSession" class="loading-state">
          <Loader2 class="spin" :size="28" />
          <span>Проверка входа</span>
        </div>

        <div v-else-if="user" class="session-state">
          <div class="session-icon">
            <LockKeyhole :size="28" />
          </div>
          <span class="panel-kicker">Вы уже вошли</span>
          <h2>{{ user.email }}</h2>
          <p>Доступ к Launchpad подтвержден.</p>
          <div class="session-actions">
            <button class="primary-button" type="button" @click="continueToLaunchpad">
              <ArrowRight :size="18" />
              Открыть Launchpad
            </button>
            <button class="secondary-button" type="button" @click="openProfile">
              <UserRound :size="18" />
              Профиль
            </button>
            <button class="secondary-button" type="button" @click="signOut">
              <LogOut :size="18" />
              Выйти
            </button>
          </div>
        </div>

        <form v-else class="auth-form" @submit.prevent="submit">
          <div class="form-head">
            <span class="panel-kicker">Аккаунт ITS</span>
            <h2>{{ title }}</h2>
          </div>

          <div class="segmented" role="tablist" aria-label="Вход или регистрация">
            <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">
              <LogIn :size="16" />
              Вход
            </button>
            <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">
              <UserPlus :size="16" />
              Регистрация
            </button>
          </div>

          <label class="field">
            <span>Email</span>
            <div class="input-wrap">
              <Mail :size="18" />
              <input v-model.trim="email" type="email" autocomplete="email" required />
            </div>
          </label>

          <label class="field">
            <span>Пароль</span>
            <div class="input-wrap">
              <KeyRound :size="18" />
              <input
                v-model="password"
                type="password"
                :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
                :minlength="mode === 'register' ? 10 : 1"
                required
              />
            </div>
          </label>

          <p v-if="mode === 'register'" class="hint">Минимум 10 символов.</p>
          <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

          <button class="primary-button" type="submit" :disabled="isSubmitting">
            <Loader2 v-if="isSubmitting" class="spin" :size="18" />
            <LogIn v-else-if="mode === 'login'" :size="18" />
            <UserPlus v-else :size="18" />
            {{ actionText }}
          </button>

          <button class="link-button" type="button" @click="switchMode">{{ switchText }}</button>
        </form>
      </section>
    </main>
  </div>
</template>
