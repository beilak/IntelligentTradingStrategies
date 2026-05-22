# Auth в tech_system

## Назначение

`tech_system` - отдельная техническая подсистема платформы ITS. Первый реализованный модуль - `auth`, который отвечает за регистрацию, вход, выпуск JWT-токенов и проверку текущего пользователя.

Контур состоит из двух сервисов:

- `tech-system-backend` - FastAPI backend с REST API `/api/tech/auth/*`.
- `tech-system-ui` - Vue UI, доступный через `/tech/auth/`.

Launchpad теперь работает как защищенная точка входа: при открытии `/launchpad/` UI проверяет JWT через `GET /api/tech/auth/me`. Если валидной сессии нет, пользователь перенаправляется на `/tech/auth/?returnTo=/launchpad/`.

## Хранение пользователей

Учетные данные хранятся в PostgreSQL в таблице `auth_users`.

Основные поля:

- `id` - UUID пользователя, используется как `sub` в JWT.
- `email` - нормализованный email в нижнем регистре, уникальный.
- `password_hash` - Argon2-хэш пароля.
- `is_active` - флаг блокировки пользователя.
- `is_verified` - задел под подтверждение email.
- `role_version` - задел под будущую ролевую модель и инвалидирование claims при изменении ролей.
- `created_at`, `updated_at`, `last_login_at` - технические временные поля.

Миграция: `its/db/migrations/versions/202605220001_add_auth_users.py`.

SQLAlchemy-модель: `its/db/models/auth.py`.

## Пароли

Пароли не сохраняются в открытом виде. Для хэширования используется `argon2-cffi`:

- регистрация сохраняет только Argon2-хэш;
- вход проверяет пароль через Argon2 verify;
- при входе выполняется проверка `check_needs_rehash`, чтобы в будущем можно было прозрачно обновлять параметры Argon2.

Backend не возвращает password hash ни в одном API-ответе.

## JWT

Используется `PyJWT` и симметричная подпись `HS256` по умолчанию.

Выпускаются два токена:

- `access_token` - короткоживущий токен для доступа к API, TTL по умолчанию 30 минут.
- `refresh_token` - токен обновления, TTL по умолчанию 7 дней.

Основные claims:

- `sub` - UUID пользователя.
- `email` - email пользователя.
- `typ` - тип токена: `access` или `refresh`.
- `role_version` - версия будущего ролевого профиля.
- `iss`, `iat`, `nbf`, `exp` - стандартные служебные claims.

Сейчас refresh-токены stateless: сервер проверяет подпись, срок действия и активность пользователя. Отзыв конкретного refresh-токена и хранение `jti` можно добавить отдельной таблицей, когда появятся требования к управлению сессиями.

## API

Базовый публичный путь через gateway: `/api/tech`.

Backend внутри контейнера использует prefix `/api/v1`.

Endpoints:

- `GET /api/tech/health` - healthcheck.
- `POST /api/tech/auth/register` - регистрация пользователя.
- `POST /api/tech/auth/login` - вход пользователя.
- `POST /api/tech/auth/refresh` - обновление пары токенов по refresh token.
- `GET /api/tech/auth/me` - текущий пользователь, требует `Authorization: Bearer <access_token>`.
- `POST /api/tech/auth/logout` - подтверждает logout; клиент удаляет локальные токены.

Пример регистрации:

```bash
curl -sS -X POST http://localhost:8080/api/tech/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"long-password"}'
```

Пример проверки сессии:

```bash
curl -sS http://localhost:8080/api/tech/auth/me \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
```

## UI-поведение

`tech-system-ui` хранит токены в `localStorage`:

- `its-auth-access-token`
- `its-auth-refresh-token`

После успешного входа или регистрации UI возвращает пользователя на `returnTo`. Для Launchpad это `/launchpad/`.

Если access token истек, Launchpad пробует обновить его через refresh token. Если обновление не удалось, токены удаляются и пользователь возвращается на `/tech/auth/`.

Профиль пользователя доступен по `/tech/profile/`. В Launchpad в верхней панели есть переход в профиль и кнопка выхода; при выходе клиент вызывает `/api/tech/auth/logout`, удаляет локальные токены и возвращает пользователя на страницу входа.

## Конфигурация

Переменные окружения:

```dotenv
AUTH_JWT_SECRET_KEY=change_me_to_a_long_random_secret
AUTH_JWT_ALGORITHM=HS256
AUTH_JWT_ISSUER=its-tech-system
AUTH_ACCESS_TOKEN_TTL_MINUTES=30
AUTH_REFRESH_TOKEN_TTL_DAYS=7
```

Для production `AUTH_JWT_SECRET_KEY` должен быть длинным случайным секретом и не должен совпадать с dev-значением из `docker-compose.yml`.

## Ролевая модель

Роли пока не реализованы по требованию текущего этапа. Подготовлены точки расширения:

- стабильный `auth_users.id` как внешний ключ для будущих таблиц ролей;
- `role_version` в таблице пользователя и JWT claims;
- единая dependency-функция `get_current_user`, через которую позже можно добавить проверку ролей и permission scopes.

Ожидаемое развитие:

- таблицы `auth_roles`, `auth_permissions`, `auth_user_roles`;
- claims или server-side lookup ролей в protected endpoints;
- bump `role_version` при изменении ролей пользователя.

## Ограничения текущего этапа

- Gateway не валидирует JWT на уровне nginx; проверку выполняют UI и backend endpoints.
- Refresh token не хранится в БД и не отзывается индивидуально.
- Email verification и password reset не реализованы.
- Ролевая модель не применяется к бизнес-сервисам.
