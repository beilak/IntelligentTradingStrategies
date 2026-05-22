<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Filter,
  Grid2X2,
  Home,
  KeyRound,
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
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiError,
  clearAuthSession,
  fetchEventLogFilterOptions,
  fetchEventLogs,
  fetchCurrentUser,
  login,
  logout,
  register,
  saveAuthSession,
  type EventLogEntry,
  type EventLogFilters,
  type User,
} from "./api";

type Mode = "login" | "register";
type SystemView = "home" | "event_logs";

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

function openSystem() {
  window.location.assign(systemHref);
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

function closeEventLogs() {
  activeSystemView.value = "home";
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
      <a class="ghost-link" href="/docs/" target="_blank" rel="noreferrer">
        Документация
        <ArrowRight :size="16" />
      </a>
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
                Tech System
              </span>
              <h1>Tech System</h1>
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
            <button class="system-module-card primary-module" type="button" @click="openEventLogs">
              <span class="module-icon">
                <ScrollText :size="24" />
              </span>
              <span class="panel-kicker">event_logs</span>
              <strong>Event Logs</strong>
              <p>Append-only журнал HTTP-действий пользователей по всем backend-сервисам.</p>
            </button>
            <button class="system-module-card" type="button" disabled>
              <span class="module-icon muted">
                <Settings :size="24" />
              </span>
              <span class="panel-kicker">planned</span>
              <strong>System Settings</strong>
              <p>Будущий раздел для технических параметров платформы.</p>
            </button>
            <button class="system-module-card" type="button" disabled>
              <span class="module-icon muted">
                <Grid2X2 :size="24" />
              </span>
              <span class="panel-kicker">planned</span>
              <strong>Service Registry</strong>
              <p>Будущий раздел для статусов и конфигурации сервисов.</p>
            </button>
          </div>
        </template>
      </section>

      <section v-else class="event-log-page">
        <div v-if="isCheckingSession" class="loading-state">
          <Loader2 class="spin" :size="28" />
          <span>Проверка входа</span>
        </div>

        <template v-else-if="user">
          <div class="event-toolbar">
            <div>
              <span class="eyebrow">
                <ScrollText :size="16" />
                Tech System
              </span>
              <h1>Event Logs</h1>
            </div>
            <div class="event-toolbar-actions">
              <span>{{ eventLogRange }}</span>
              <button class="secondary-button" type="button" @click="closeEventLogs">
                <ArrowLeft :size="18" />
                Tech System
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
              <button class="secondary-button" type="button" @click="openSystem">
                <ShieldCheck :size="18" />
                Tech System
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
        </template>
      </section>
    </main>

    <main v-else class="workspace">
      <section class="system-panel">
        <span class="eyebrow">
          <ShieldCheck :size="16" />
          Защищенный доступ
        </span>
        <h1>Добро пожаловать в ITS</h1>
        <p class="hero-note">Войдите, чтобы перейти к рабочим инструментам платформы.</p>
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
