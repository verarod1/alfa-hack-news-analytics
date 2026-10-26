# Docker на чистой машине

Это проверка воспроизводимости из кода, без вашей старой БД, `.env`, Chroma и OCR-кэша.
Физически пустой Mac и новый изолированный Compose-проект на текущем Mac — разные
проверки: второй вариант не доказывает отсутствие зависимости от кэша образов.

## 1. Что потребуется

- Docker Desktop для Apple Silicon, Git и доступ к приватному GitHub-репозиторию.
- Интернет для загрузки образов/зависимостей и реальных RSS.
- Python, Node и PostgreSQL на самой машине для Docker-варианта не обязательны.
- Исходные CSV нужны для трёх компаний. Они не входят в чистый checkout.
- PDF/LLM-ключ не нужны для проверки инфраструктуры; без них не обещаем AI-результат.

## 2. Новый checkout и безопасная конфигурация

На **другой, пустой машине**:

```bash
git clone --depth 1 --branch main https://github.com/verarod1/alfa-hack-news-analytics.git alfa-mvp-clean
cd alfa-mvp-clean
cp .env.example .env
```

Заполните только локальный `POSTGRES_PASSWORD` в `.env`. Для бесплатного прогона
оставьте `DATABASE_URL`, `DOCKER_DATABASE_URL`, `LLM_API_KEY`, `LLM_BASE_URL` и
`ML_ADAPTER_MODULE` пустыми. Не копируйте старый `.env` с рабочими адресами/ключами.

В этом терминале:

```bash
export BACKEND_PORT=8001
export FRONTEND_PORT=3000
export ML_ADAPTER_MODULE=
export LLM_API_KEY=
export LLM_BASE_URL=
export DOCKER_DATABASE_URL=
export NEWS_SOURCES=cbr,government
```

Настройки БД внутри контейнеров должны указывать на `db:5432`, а не удалённый сервер.
Пароль не показывайте в логах/скриншотах и не добавляйте `.env` в Git.

## 3. Проверка и одна сборка

```bash
docker info --format '{{.ServerVersion}} {{.Architecture}}'
docker compose config --quiet
docker compose build --pull backend frontend
```

Ожидается ARM/aarch64 и успешная сборка. `--pull` проверяет доступность базовых образов;
на действительно чистой машине нет старых слоёв/зависимостей. ML-библиотеки большие,
первая загрузка может быть долгой. Не отключайте TLS ради ошибки Docker Hub.
Backend, analysis-worker и news-collector используют один образ Backend.

## 4. Создание только новой локальной БД

```bash
docker compose up -d --no-build db
docker compose ps db
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database();" -c "\dt"'
```

Ожидается healthy и новая база (по шаблону alfa_news), пока без таблиц приложения.
Healthy проверяет доступность PostgreSQL, а не наличие схемы.

```bash
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backend/db/schema.sql
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backend/db/mvp.sql
```

Ожидаются таблицы raw_* и MVP. Схемы не создаются неявно при запуске API.
Не направляйте эти команды в чужую рабочую БД.

## 5. Backend, интерфейс и бесплатные новости

```bash
docker compose up -d --no-build backend frontend analysis-worker news-collector
docker compose ps
curl -f http://localhost:8001/health
curl -f http://localhost:8001/openapi.json
curl -f http://localhost:3000/api/v1/roles
curl -f http://localhost:3000/api/v1/demo-profiles
```

Ожидается: Backend отвечает, запрос через frontend/nginx возвращает роли CEO/CFO.
Без CSV demo-profiles.items будет `[]` — это отсутствие данных, не ошибка Docker.
Откройте http://localhost:3000/demo и http://localhost:8001/docs.

```bash
docker compose exec backend python scripts/import_news_fixtures.py
docker compose exec backend python scripts/import_news_fixtures.py
docker compose exec backend python scripts/collect_news.py --source government --limit 3
```

Две фикстуры ФНС должны импортироваться без сети и повторных записей. Сборщик
Правительства получает RSS и текст, сохраняет данные; при проблеме сети показывает
ошибку без вымышленных новостей. Автоматический news-collector повторяет ограниченный
сбор через NEWS_POLL_SECONDS (1800 по умолчанию). Он не вызывает ML/OCR.

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT source_id,count(*),count(DISTINCT content_hash) FROM news GROUP BY source_id;"'
curl -f http://localhost:3000/api/v1/news/news_fns_5626c2076b90788cc5caeadd5df76bcc
```

Ожидается: новость доступна через frontend → nginx → Backend → новую БД.
Количество строк и уникальных хешей совпадает. Конкретное число сетевых новостей
зависит от даты RSS, доступности и фильтра давности.

## 6. Полный прогон с тремя компаниями

Получите CSV по разрешённому командному каналу, вручную положите в `data/raw/`:
`df_Uid_data_hack.csv`, `df_Uid_payment_hack.csv`, `df_Fid_Uid_link_hack.csv`.
Не загружайте их в публичный GitHub.

```bash
docker compose exec backend python scripts/import_csv.py
curl -f http://localhost:3000/api/v1/demo-profiles
curl -f -H 'X-Company-ID: U_44564' 'http://localhost:3000/api/v1/feed?company_id=U_44564&role=cfo'
```

Ожидается 6 профилей (3 × CEO/CFO), карточки и лента. На интерфейсе выберите
U_44564, U_19717, U_9250, обе роли; откройте новость и проверьте источник/дату/текст.
До импорта CSV эти сценарии недоступны — не создавайте вымышленные компании.
`--replace` не нужен для первого импорта и не используется этой проверкой.

При выключенном ML анализ остаётся queued, чат не придумывает ответ. Полный
цикл completed/чат проверяется безопасными тестовыми ответами, а реальное качество
LLM и банковских PDF — отдельно, с разрешёнными материалами и решением о расходах.

## 7. Ошибки и сохранение состояния

```bash
docker compose logs --tail=80 backend frontend analysis-worker news-collector db
docker compose exec backend python -B -m unittest discover -s tests -v
docker compose restart backend frontend
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM news;"'
```

Данные после restart должны сохраниться. PostgreSQL-тесты в общем Docker-наборе
намеренно пропущены: их отдельно запускает `backend/scripts/run_integration_tests.py`
на временном кластере. Chroma/OCR проверяются без платных моделей.

Типовые причины:

- 500/UndefinedTable — схемы не применены, см. шаг 4.
- Пустые демо-профили/404 компании — CSV ещё не импортированы.
- 502 nginx — Backend не запущен/не готов, проверьте backend:8000.
- 403 — несовпадение X-Company-ID с выбранной компанией.
- Ошибка пароля — `.env` не меняет пароль уже существующего volume.
- RSS timeout — сеть/источник недоступен; это не повод менять даты или обходить robots.
- Отсутствие банковского мнения — нет PDF/подготовленного индекса, подходящего фрагмента
  или разрешённого реального ML-вызова. Это не проверяется одним HTTP 200 приложения.

Остановить, сохранив данные:

```bash
docker compose stop
```

## 8. Если проверять на вашем текущем Mac

Не запускайте этот checkout рядом с рабочим простым `docker compose up`: в Compose
есть фиксированные container_name. Одного `-p` недостаточно. Кроме нового project name
нужны другие container_name, свободные порты и **другие bind-каталоги данных**, а также
отдельный `.env` без настоящих ключей. Старые PostgreSQL volumes подключать нельзя.

26.10.2026 такая проверка прошла отдельно с новым Compose-проектом и новой БД:
nginx → API работает, повторный импорт даёт 2 строки/2 уникальных хеша, после
пересоздания Backend новости сохраняются. Пользовательские данные и .env не
подключались, платных вызовов не было. Уже построенные образы переиспользованы.
Это проверка чистого состояния данных на текущем Mac, **не испытание на физически
пустом устройстве** и не проверка загрузки всех образов из интернета с нуля.
Не используйте docker system prune, удаление всех volumes или down -v рабочего проекта.
