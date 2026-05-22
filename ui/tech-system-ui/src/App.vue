<script setup lang="ts">
import {
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Home,
  KeyRound,
  Loader2,
  LockKeyhole,
  LogIn,
  LogOut,
  Mail,
  ShieldCheck,
  UserRound,
  UserPlus,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import {
  ApiError,
  clearAuthSession,
  fetchCurrentUser,
  login,
  logout,
  register,
  saveAuthSession,
  type User,
} from "./api";

type Mode = "login" | "register";

const mode = ref<Mode>("login");
const email = ref("");
const password = ref("");
const user = ref<User | null>(null);
const isCheckingSession = ref(true);
const isSubmitting = ref(false);
const errorMessage = ref("");
const currentPath = ref(window.location.pathname);

const query = new URLSearchParams(window.location.search);
const requestedReturnTo = query.get("returnTo");
const profileHref = "/tech/profile/";
const launchpadHref = "/launchpad/";
const authProfileHref = `/tech/auth/?returnTo=${profileHref}`;

const isProfilePage = computed(() => currentPath.value.startsWith(profileHref));

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
  if (isProfilePage.value) {
    window.location.replace("/tech/auth/");
  }
}

onMounted(async () => {
  try {
    user.value = await fetchCurrentUser();
    if (requestedReturnTo && !isProfilePage.value) {
      continueToLaunchpad();
    }
  } catch {
    clearAuthSession();
    if (isProfilePage.value) {
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

    <main v-if="isProfilePage" class="profile-workspace">
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
