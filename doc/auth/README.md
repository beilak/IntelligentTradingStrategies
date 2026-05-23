# Auth и управление доступом в tech_system

## Назначение

`tech_system` - отдельная подсистема ITS для технических функций платформы. Модуль `auth` отвечает за регистрацию, вход, выпуск токенов, профиль пользователя, роли, права доступа, заявки на расширение доступа и аудит изменений.

Контур состоит из двух сервисов:

- `tech-system-backend` - FastAPI backend с REST API `/api/tech/*`.
- `tech-system-ui` - Vue UI для входа, профиля и управления доступом.

Launchpad защищен проверкой текущей сессии: при открытии `/launchpad/` UI вызывает `GET /api/tech/auth/me`. Если валидной сессии нет, пользователь перенаправляется на `/tech/auth/?returnTo=/launchpad/`. Стартовая страница доступна новому пользователю, но рабочие модули внутри нее показываются только по назначенным правам.

## Пользовательский сценарий

- Новый пользователь регистрируется или входит через `/tech/auth/`.
- После входа пользователь попадает в Launchpad или в исходный `returnTo`.
- Новый пользователь по умолчанию видит в Launchpad только документацию и профиль.
- В профиле новый пользователь может посмотреть свои роли и отправить заявку на расширение доступа.
- В верхней панели Launchpad доступны профиль и выход.
- В профиле пользователь видит свои роли, права доступа и может отправить заявку на дополнительный доступ.
- Пользователи с административными правами видят раздел управления платформой: пользователи, роли, заявки и права доступа.
- Технические названия вроде алгоритмов хэширования, типа токенов или БД не выводятся на продуктовые экраны.

## Хранение данных

Учетные данные и ролевая модель хранятся в PostgreSQL.

Основные таблицы:

- `auth_users` - пользователи.
- `auth_roles` - роли.
- `auth_permissions` - атомарные права доступа.
- `auth_role_permissions` - связь ролей и прав.
- `auth_user_roles` - назначение ролей пользователям.
- `auth_role_requests` - заявки пользователей на роли.
- `auth_audit_log` - аудит входа, заявок и изменений доступа.

Основные миграции:

- `202605220001_add_auth_users.py` - базовая таблица пользователей.
- `202605230001_add_rbac.py` - RBAC-таблицы, seed ролей и прав.
- `202605230002_add_documentation_reader_role.py` - минимальная роль для новых аккаунтов.

SQLAlchemy-модели находятся в `its/db/models/auth.py`.

## Пароли

Пароли не сохраняются в открытом виде. Для хэширования используется `argon2-cffi`.

Поведение:

- регистрация сохраняет только Argon2-хэш;
- вход проверяет пароль через Argon2 verify;
- при входе выполняется `check_needs_rehash`, чтобы позже можно было прозрачно обновлять параметры хэширования;
- backend никогда не возвращает password hash в API-ответах.

## Токены

Используется `PyJWT` и симметричная подпись `HS256` по умолчанию.

Выпускаются два токена:

- `access_token` - короткоживущий токен для доступа к API, TTL по умолчанию 30 минут.
- `refresh_token` - токен обновления, TTL по умолчанию 7 дней.

Access token содержит identity и authorization claims:

- `sub` - UUID пользователя.
- `email` - email пользователя.
- `typ` - `access`.
- `role_version` - версия ролевого профиля пользователя.
- `roles` - список кодов ролей.
- `permissions` - раскрытый список прав доступа.
- `env_scopes` - задел под разделение research / paper / live контуров.
- `iss`, `iat`, `nbf`, `exp` - стандартные служебные claims.

Refresh token остается компактным и используется только для обновления пары токенов.

Если роли пользователя изменились, `auth_users.role_version` увеличивается. Уже выданный access token остается действительным до `exp`; новые роли и права попадут в токен после следующего входа или refresh. Для промышленного режима рекомендуется уменьшить TTL access token до 10 минут.

## Ролевая модель

Реализована модель RBAC + permission scopes:

- пользователь получает одну или несколько ролей;
- роль раскрывается в набор стабильных прав доступа;
- backend принимает окончательное решение по правам, UI только скрывает или блокирует недоступные действия;
- если права нет, действие запрещено по умолчанию.

Предустановленные роли:

- `documentation_reader` - первичный доступ к Launchpad, документации, профилю и заявкам на доступ.
- `viewer` - просмотр рабочих разделов и отчетов.
- `quant_researcher` - гипотезы, компоненты стратегий, тесты и GA-запуски.
- `data_manager` - загрузка и управление источниками рыночных данных.
- `strategy_releaser` - подготовка стратегии к production-заявке.
- `production_approver` - согласование production-заявок.
- `trading_operator` - paper/live операции без доступа к секретам.
- `risk_manager` - риск-лимиты, риск-согласования и emergency stop.
- `secret_manager` - управление ссылками на секреты без чтения значений.
- `role_admin` - пользователи, роли, заявки и аудит доступа.
- `system_admin` - техническое состояние системы, журналы и интеграции.
- `auditor` - чтение audit trail без изменения данных.

Каталог ролей и прав находится в `its/tech_system/auth/rbac.py`.

## Bootstrap-администратор

Для первичного назначения администратора используется переменная:

```dotenv
ITS_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
```

Если email вошедшего или зарегистрированного пользователя совпадает с этим значением, ему назначаются роли:

- `documentation_reader`
- `system_admin`
- `role_admin`

Обычные пользователи по умолчанию получают `documentation_reader`. Эта роль не содержит `data.*`, `strategy.*`, `ga.*` или административных прав.

## Backend API

Базовый публичный путь через gateway: `/api/tech`.

Основные endpoints:

- `GET /api/tech/health` - healthcheck.
- `POST /api/tech/auth/register` - регистрация.
- `POST /api/tech/auth/login` - вход.
- `POST /api/tech/auth/refresh` - обновление токенов.
- `GET /api/tech/auth/me` - текущий пользователь.
- `POST /api/tech/auth/logout` - выход на стороне клиента.
- `GET /api/tech/profile/me` - профиль текущего пользователя.
- `GET /api/tech/profile/me/roles` - роли текущего пользователя.
- `GET /api/tech/profile/me/permissions` - права текущего пользователя.
- `GET /api/tech/profile/me/role-requests` - свои заявки.
- `POST /api/tech/profile/me/role-requests` - создать заявку на роль.
- `POST /api/tech/profile/me/role-requests/{request_id}/cancel` - отменить свою заявку.
- `GET /api/tech/roles/requestable` - роли, которые можно запросить.
- `GET /api/tech/roles` - список ролей.
- `POST /api/tech/roles` - создать роль.
- `PATCH /api/tech/roles/{role_code}` - обновить роль.
- `DELETE /api/tech/roles/{role_code}` - удалить роль.
- `GET /api/tech/permissions` - список прав доступа.
- `GET /api/tech/permissions/grouped` - права, сгруппированные по доменам.
- `GET /api/tech/users` - пользователи.
- `GET /api/tech/users/{user_id}` - карточка пользователя.
- `PATCH /api/tech/users/{user_id}` - обновить статус пользователя.
- `POST /api/tech/users/{user_id}/roles` - назначить роль.
- `DELETE /api/tech/users/{user_id}/roles/{role_code}` - отозвать роль.
- `GET /api/tech/role-requests` - заявки на доступ.
- `POST /api/tech/role-requests/{request_id}/approve` - одобрить заявку.
- `POST /api/tech/role-requests/{request_id}/reject` - отклонить заявку.
- `GET /api/tech/audit/auth` - аудит входа и регистрации.
- `GET /api/tech/audit/roles` - аудит изменений доступа.

## UI

`tech-system-ui` хранит токены в `localStorage`:

- `its-auth-access-token`
- `its-auth-refresh-token`

Если access token истек, Launchpad и Tech System пробуют обновить его через refresh token. Если обновление не удалось, токены удаляются и пользователь возвращается на страницу входа.

Основные экраны:

- `/tech/auth/` - вход и регистрация.
- `/tech/profile/` - профиль, роли, права доступа, заявки пользователя.
- `/tech/system/` - управление платформой для пользователей с административными правами.

В Launchpad плитки рабочих разделов показываются только при наличии соответствующих прав:

- Документация - `app.docs.read`.
- Профиль - `profile.self.read`.
- Data Hub - `data.sources.read` или `data.instruments.read`.
- Strategy Lab - `strategy.model.read` или `strategy.component.read`.
- GA Lab - `ga.alphabet.read` или `ga.run.read`.
- Управление платформой - права на пользователей, роли, заявки, права доступа или аудит доступа.
- Состояние платформы - `system.health.read`.

## Общие зависимости для бизнес-сервисов

Для защиты backend-сервисов добавлен общий пакет `its/authz`:

- `decode_access_context` - проверка access token и сбор контекста пользователя.
- `AuthContext` - user id, email, роли, права и env scopes.
- `require_permissions` - dependency для обязательного набора прав.
- `require_any_permission` - dependency для любого права из набора.
- `require_roles` / `require_any_role` - dependency для проверок ролей.
- `Permissions` - централизованные константы кодов прав.

Подключение enforcement:

- Tech System endpoints используют server-side проверки ролей и прав в `its/tech_system/auth/router.py`.
- Data backend endpoints требуют data permissions на уровне FastAPI dependencies.
- Strategy backend endpoints требуют strategy permissions; операции запуска дополнительно требуют data-read права, потому что читают данные через Data backend.
- GA backend endpoints требуют GA permissions; запуск дополнительно требует data-read права.
- Event Log backend требует `system.logs.read`.

UI не является источником истины: он только скрывает или блокирует элементы, а окончательное решение принимает backend endpoint.

## Конфигурация

Переменные окружения:

```dotenv
AUTH_JWT_SECRET_KEY=change_me_to_a_long_random_secret
AUTH_JWT_ALGORITHM=HS256
AUTH_JWT_ISSUER=its-tech-system
AUTH_ACCESS_TOKEN_TTL_MINUTES=30
AUTH_REFRESH_TOKEN_TTL_DAYS=7
ITS_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
```

Для production:

- `AUTH_JWT_SECRET_KEY` должен быть длинным случайным секретом и не должен совпадать с dev-значением;
- рекомендуется `AUTH_ACCESS_TOKEN_TTL_MINUTES=10`;
- рекомендуется `AUTH_REFRESH_TOKEN_TTL_DAYS=1`;
- брокерские токены должны храниться в secret vault, а не в `.env`.

## Текущие ограничения

- Refresh token пока stateless: сервер проверяет подпись, срок действия и активность пользователя, но не хранит и не отзывает конкретный `jti`.
- Email verification, password reset и MFA пока не реализованы.
- Production/trading/secret workflows заложены в каталоге прав, но их прикладные API и UI будут разворачиваться отдельными этапами.
- Legacy FastAPI endpoints вне актуальных Data/Strategy/GA/Tech/Event Log сервисов нужно отдельно ревизовать перед публикацией наружу.
- Gateway не валидирует JWT на уровне nginx; проверка выполняется backend-сервисами.
