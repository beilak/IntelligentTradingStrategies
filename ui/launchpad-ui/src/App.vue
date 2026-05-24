<script setup lang="ts">
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Boxes,
  CandlestickChart,
  CircleHelp,
  DatabaseZap,
  Dna,
  Globe2,
  Landmark,
  Layers3,
  LineChart,
  Loader2,
  LogOut,
  Play,
  ShieldCheck,
  UserCircle,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";

type Locale = "ru" | "en";
type User = {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  role_version: number;
  created_at: string;
  last_login_at: string | null;
  roles: Array<{ code: string; title: string; description: string | null }>;
  permissions: string[];
};

const savedLocale = localStorage.getItem("its-launchpad-locale") as Locale | null;
const locale = ref<Locale>(savedLocale === "en" ? "en" : "ru");
const isCheckingAuth = ref(true);
const currentUser = ref<User | null>(null);

const ACCESS_TOKEN_KEY = "its-auth-access-token";
const REFRESH_TOKEN_KEY = "its-auth-refresh-token";
const authHref = "/tech/auth/?returnTo=/launchpad/";

const messages = {
  ru: {
    appTitle: "ITS Launchpad",
    appSubtitle: "Единая точка запуска рабочих интерфейсов",
    documentation: "Документация",
    language: "Язык",
    profile: "Профиль",
    logout: "Выйти",
    checkingAuth: "Проверка входа",
    open: "Открыть",
    ready: "Готово",
    documentationTitle: "Документация",
    documentationSubtitle: "Руководства и описание платформы",
    documentationBody: "Базовая информация по рабочим разделам ITS, данным, стратегиям и процессу запроса доступа.",
    profileTitle: "Профиль",
    profileSubtitle: "Аккаунт и доступы",
    profileBody: "Просмотр назначенных ролей, доступных прав и отправка заявки на расширение доступа.",
    dataTitle: "Данные рынка",
    dataSubtitle: "Котировки, инструменты, дивиденды и источники данных",
    dataBody: "Быстрый просмотр T-Invest/MOEX данных, свечей, объемов и справочников бумаг.",
    strategyTitle: "Торговая стратегия",
    strategySubtitle: "Компоненты моделей, CPCV, WalkForward и Backtesting",
    strategyBody: "Рабочая зона модельера: registry компонентов, состав стратегии и отчеты тестирования.",
    gaTitle: "GA генератор",
    gaSubtitle: "Генетические алгоритмы для поиска стратегий",
    gaBody: "Алфавиты компонентов, эволюционный запуск, визуализация поколений и материализация TOP-3 стратегий.",
    executionTitle: "Execution",
    executionSubtitle: "Брокерские счета и исполнение",
    executionBody: "Личный кабинет T-Invest: состояние счетов, портфель, операции, заявки и безопасные заглушки приказов.",
    techTitle: "Управление платформой",
    techSubtitle: "Доступы и аудит",
    techBody: "Просмотр событий, заявок на доступ и технических операций платформы.",
    observabilityTitle: "Состояние платформы",
    observabilitySubtitle: "Проверка доступности",
    observabilityBody: "Быстрый контроль доступности рабочих разделов и основных сервисов.",
    roadmapTitle: "Следующие интерфейсы",
    roadmapSubtitle: "Место для новых UI",
    roadmapBody: "Сюда можно добавить риск-панель, execution, portfolio monitor или research notebooks.",
    statusData: "Сервис данных",
    statusStrategy: "Сервис стратегий",
    stack: "Единая рабочая среда",
  },
  en: {
    appTitle: "ITS Launchpad",
    appSubtitle: "One place to open every working interface",
    documentation: "Documentation",
    language: "Language",
    profile: "Profile",
    logout: "Sign out",
    checkingAuth: "Checking sign-in",
    open: "Open",
    ready: "Ready",
    documentationTitle: "Documentation",
    documentationSubtitle: "Guides and platform overview",
    documentationBody: "Core information about ITS workspaces, data, strategies, and access request workflow.",
    profileTitle: "Profile",
    profileSubtitle: "Account and access",
    profileBody: "Review assigned roles, available permissions, and request additional access.",
    dataTitle: "Market Data",
    dataSubtitle: "Quotes, instruments, dividends, and data sources",
    dataBody: "Fast access to T-Invest/MOEX candles, volumes, instruments, and reference data.",
    strategyTitle: "Trading Strategy",
    strategySubtitle: "Model components, CPCV, WalkForward, and Backtesting",
    strategyBody: "Modeler workspace: component registry, strategy composition, and testing reports.",
    gaTitle: "GA Generator",
    gaSubtitle: "Genetic algorithms for strategy search",
    gaBody: "Component alphabets, evolutionary runs, generation visualization, and TOP-3 materialization.",
    executionTitle: "Execution",
    executionSubtitle: "Broker accounts and order flow",
    executionBody: "T-Invest cabinet: account state, portfolio, operations, orders, and safe order-ticket stubs.",
    techTitle: "Platform Management",
    techSubtitle: "Access and audit",
    techBody: "Review audit events, access requests, and platform operations.",
    observabilityTitle: "Platform Status",
    observabilitySubtitle: "Availability check",
    observabilityBody: "Quick access to the availability state of key platform services.",
    roadmapTitle: "Next Interfaces",
    roadmapSubtitle: "Space for upcoming UI modules",
    roadmapBody: "Add risk dashboards, execution, portfolio monitoring, or research notebooks here.",
    statusData: "Data service",
    statusStrategy: "Strategy service",
    stack: "Unified workspace",
  },
} satisfies Record<Locale, Record<string, string>>;

const t = computed(() => messages[locale.value]);
const docsHref = computed(() => `/docs/?lang=${locale.value}`);
const canOpenTechSystem = computed(() =>
  ["user.read", "role.read", "permission.read", "role.request.read", "audit.role.read"].some(
    (permission) => currentUser.value?.permissions.includes(permission),
  ),
);

const tiles = computed(() => {
  const items = [] as Array<{
    id: string;
    title: string;
    subtitle: string;
    body: string;
    href: string;
    icon: typeof CandlestickChart;
    accent: string;
    metrics: string[];
  }>;

  if (hasPermission("app.docs.read")) {
    items.push({
      id: "docs",
      title: t.value.documentationTitle,
      subtitle: t.value.documentationSubtitle,
      body: t.value.documentationBody,
      href: docsHref.value,
      icon: CircleHelp,
      accent: "#aee9d1",
      metrics: locale.value === "ru" ? ["Руководства", "Процессы"] : ["Guides", "Workflow"],
    });
  }

  if (hasPermission("profile.self.read")) {
    items.push({
      id: "profile",
      title: t.value.profileTitle,
      subtitle: t.value.profileSubtitle,
      body: t.value.profileBody,
      href: "/tech/profile/",
      icon: UserCircle,
      accent: "#ffcc66",
      metrics: locale.value === "ru" ? ["Роли", "Заявки"] : ["Roles", "Requests"],
    });
  }

  if (hasPermission("data.sources.read") || hasPermission("data.instruments.read")) {
    items.push({
      id: "data",
      title: t.value.dataTitle,
      subtitle: t.value.dataSubtitle,
      body: t.value.dataBody,
      href: "/data/",
      icon: CandlestickChart,
      accent: "#66d9ef",
      metrics: ["Stocks", "Candles", "Dividends"],
    });
  }

  if (hasPermission("strategy.model.read") || hasPermission("strategy.component.read")) {
    items.push({
      id: "strategies",
      title: t.value.strategyTitle,
      subtitle: t.value.strategySubtitle,
      body: t.value.strategyBody,
      href: "/strategies/",
      icon: Boxes,
      accent: "#ffcc66",
      metrics: ["Registry", "CPCV", "Backtest"],
    });
  }

  if (hasPermission("ga.alphabet.read") || hasPermission("ga.run.read")) {
    items.push({
      id: "ga",
      title: t.value.gaTitle,
      subtitle: t.value.gaSubtitle,
      body: t.value.gaBody,
      href: "/ga/",
      icon: Dna,
      accent: "#aee9d1",
      metrics: ["Alphabets", "PyGAD", "TOP-3"],
    });
  }

  items.push({
    id: "execution",
    title: t.value.executionTitle,
    subtitle: t.value.executionSubtitle,
    body: t.value.executionBody,
    href: "/execution/",
    icon: Landmark,
    accent: "#ff8f70",
    metrics: locale.value === "ru" ? ["Счета", "Портфель", "Заявки"] : ["Accounts", "Portfolio", "Orders"],
  });

  if (canOpenTechSystem.value) {
    items.push({
      id: "tech-system",
      title: t.value.techTitle,
      subtitle: t.value.techSubtitle,
      body: t.value.techBody,
      href: "/tech/system/",
      icon: ShieldCheck,
      accent: "#66d9ef",
      metrics: locale.value === "ru" ? ["Доступы", "Аудит", "Пользователи"] : ["Access", "Audit", "Users"],
    });
  }

  if (hasPermission("system.health.read")) {
    items.push({
      id: "system",
      title: t.value.observabilityTitle,
      subtitle: t.value.observabilitySubtitle,
      body: t.value.observabilityBody,
      href: "/health",
      icon: Activity,
      accent: "#aee9d1",
      metrics: [t.value.statusData, t.value.statusStrategy],
    });
  }

  if (items.length === 0) {
    items.push({
      id: "roadmap",
      title: t.value.roadmapTitle,
      subtitle: t.value.roadmapSubtitle,
      body: t.value.roadmapBody,
      href: "#",
      icon: Layers3,
      accent: "#b48cf2",
      metrics: ["Risk", "Execution", "Monitor"],
    });
  }

  return items;
});

watch(locale, (value) => localStorage.setItem("its-launchpad-locale", value));

function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function hasPermission(permission: string): boolean {
  return currentUser.value?.permissions.includes(permission) ?? false;
}

function finishAuth(user: User) {
  currentUser.value = user;
  isCheckingAuth.value = false;
}

async function fetchCurrentUser(accessToken: string): Promise<User | null> {
  const response = await fetch("/api/tech/auth/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
  if (!response.ok) return null;
  return (await response.json()) as User;
}

async function refreshAccessToken(): Promise<User | null> {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) return null;

  const response = await fetch("/api/tech/auth/refresh", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return null;

  const payload = (await response.json()) as {
    access_token: string;
    refresh_token: string;
    user: User;
  };
  localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  return payload.user;
}

async function requireAuth() {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  try {
    const user = accessToken ? await fetchCurrentUser(accessToken) : null;
    if (user) {
      finishAuth(user);
      return;
    }

    const refreshedUser = await refreshAccessToken();
    if (refreshedUser) {
      finishAuth(refreshedUser);
      return;
    }
  } catch {
    clearAuthTokens();
  }

  clearAuthTokens();
  window.location.replace(authHref);
}

async function signOut() {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (accessToken) {
    await fetch("/api/tech/auth/logout", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    }).catch(() => undefined);
  }
  clearAuthTokens();
  window.location.replace(authHref);
}

onMounted(() => {
  void requireAuth();
});
</script>

<template>
  <div v-if="isCheckingAuth" class="auth-check-shell">
    <Loader2 class="spin" :size="28" />
    <span>{{ t.checkingAuth }}</span>
  </div>

  <div v-else class="app-shell">
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
        <a
          class="user-pill"
          href="/tech/profile/"
          :title="currentUser?.email || t.profile"
          :aria-label="t.profile"
        >
          <UserCircle :size="18" />
          <span>{{ currentUser?.email || t.profile }}</span>
        </a>
        <button class="icon-button" type="button" :title="t.logout" :aria-label="t.logout" @click="signOut">
          <LogOut :size="18" />
        </button>
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
