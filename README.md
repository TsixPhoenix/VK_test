# Botfarm Service

## Что делает сервис

- создает нового пользователя ботофермы;
- выдает список существующих пользователей;
- блокирует первого свободного пользователя (`locktime = now + TTL`) и возвращает креды;
- снимает блокировки в заданном контексте (`project_id`/`env`/`domain`) или глобально по явному подтверждению;
- защищает бизнес-endpoint-ы через OAuth2 Password + JWT scopes;
- отдает startup/liveness/readiness пробы.

## Технологии

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2 (async) + asyncpg
- PostgreSQL 14+
- Alembic
- Pytest + Coverage
- Ruff + Mypy + pre-commit
- Docker Compose
- Helm (Minikube)

## Архитектура

- `app/api` — HTTP-слой и DI
- `app/schemas` — валидация и API-контракты
- `app/services` — бизнес-логика
- `app/repositories` — CRUD и SQLAlchemy-запросы
- `app/models` — ORM-модели
- `app/db` — engine/session
- `alembic` — миграции

## Требования к окружению

Создайте `.env` на основе `.env.example`.

В `.env` хранятся только чувствительные параметры:

- `POSTGRES_PASSWORD` — пароль postgres-контейнера в docker-compose.
- `DATABASE_URL` — строка подключения к PostgreSQL.
- `BOTFARM_ENCRYPTION_KEY` — Fernet-ключ для шифрования паролей пользователей.
- `BOTFARM_ENCRYPTION_FALLBACK_KEYS` — опциональный список старых Fernet-ключей через запятую для ротации.
- `JWT_SECRET_KEY` — секрет подписи JWT.
- `AUTH_PASSWORD` — пароль сервисного аккаунта OAuth2.

Нечувствительные параметры (`APP_NAME`, `AUTH_USERNAME`, `LOCK_TTL_SECONDS`, probe timeouts и т.д.)
зафиксированы в коде и chart values.

Сгенерировать Fernet-ключ:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Ротация ключа шифрования:

1. Сгенерировать новый `BOTFARM_ENCRYPTION_KEY`.
2. Текущий старый ключ добавить в `BOTFARM_ENCRYPTION_FALLBACK_KEYS`.
3. После пере-шифрования/обновления всех пользовательских паролей удалить старый ключ из fallback-списка.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.lock
pip install -e . --no-deps
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Runtime-only профиль (например, для контейнеров) ставится из `requirements.lock`:

```bash
pip install -r requirements.lock
```

Swaggers: `http://localhost:8000/docs`

## Аутентификация

Получить токен:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=botfarm_admin&password=<AUTH_PASSWORD_FROM_ENV>&scope=botfarm:read botfarm:write"
```

## API примеры

Создать пользователя:

```bash
curl -X POST "http://localhost:8000/api/v1/users" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "login": "petbuyer@example.com",
    "password": "VeryStrong1!",
    "project_id": "11111111-1111-1111-1111-111111111111",
    "env": "stage",
    "domain": "regular"
  }'
```

Получить список пользователей:

```bash
curl "http://localhost:8000/api/v1/users?env=stage&domain=regular&limit=50&offset=0" \
  -H "Authorization: Bearer <TOKEN>"
```

Заблокировать пользователя:

```bash
curl -X POST "http://localhost:8000/api/v1/users/locks" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"env":"stage","domain":"regular"}'
```

Снять блокировки по контексту:

```bash
curl -X DELETE "http://localhost:8000/api/v1/users/locks?project_id=11111111-1111-1111-1111-111111111111&env=stage&domain=regular" \
  -H "Authorization: Bearer <TOKEN>"
```

Глобальное снятие блокировок (явно):

```bash
curl -X DELETE "http://localhost:8000/api/v1/users/locks?release_all=true" \
  -H "Authorization: Bearer <TOKEN>"
```

## Пробы

- `GET /api/v1/health/live` — проверка живости процесса (без внешних зависимостей).
- `GET /api/v1/health/ready` — проверка готовности (пинг БД).
- `GET /api/v1/health/startup` — сервис завершил startup-последовательность.

## Тесты

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Coverage порог: `>= 75%`.

## Docker Compose

```bash
docker compose up --build
```

Сервис: `http://localhost:8000`, PostgreSQL: `localhost:5432`.

Если меняли `POSTGRES_PASSWORD` в `.env` на уже существующем volume, пересоздайте его:

```bash
docker compose down -v
docker compose up --build
```

## Helm и Minikube

```bash
minikube start
eval $(minikube docker-env)
docker build -t botfarm-service:latest .
helm upgrade --install botfarm ./helm/botfarm
kubectl port-forward svc/botfarm-botfarm 8000:8000
```

По умолчанию Helm chart поднимает **и приложение, и PostgreSQL** (внутренний инстанс).
Для внешней БД:

- установить `postgres.enabled=false`;
- передать `database.url=<ваш_postgresql+asyncpg_url>`.

Перед установкой chart задайте обязательные секреты:

```bash
helm upgrade --install botfarm ./helm/botfarm \
  --set secrets.botfarmEncryptionKey="$BOTFARM_ENCRYPTION_KEY" \
  --set secrets.jwtSecretKey="$JWT_SECRET_KEY" \
  --set secrets.authPassword="$AUTH_PASSWORD" \
  --set postgres.auth.password="$POSTGRES_PASSWORD"
```

## Runbook / Smoke checklist

1. Получить OAuth2 токен.
2. Создать 2 тестовых пользователей.
3. Вызвать `lock` дважды — должны прийти разные пользователи.
4. Третий `lock` должен вернуть `409`.
5. Вызвать `DELETE /users/locks` c фильтрами и убедиться, что `freed_count >= 1`.
6. Проверить `health/live`, `health/ready`, `health/startup`.

## Важные детали реализации

- `password` пользователя хранится в БД в зашифрованном виде (Fernet).
- ротация ключей поддерживается через `BOTFARM_ENCRYPTION_FALLBACK_KEYS` (MultiFernet).
- `get_users` не возвращает пароль.
- `lock_user` возвращает расшифрованный пароль только авторизованному клиенту со scope `botfarm:write`.
- выбор пользователя для lock реализован через `SELECT ... FOR UPDATE SKIP LOCKED` на PostgreSQL.
- TTL блокировки рассчитывается от времени БД, а не от локальных часов инстанса приложения.
- правило уникальности: `login` уникален глобально во всей системе.
