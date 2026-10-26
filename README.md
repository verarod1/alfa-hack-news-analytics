# Новостная аналитика — Alfa Hack 2026

Сервис подбирает новости для компании и роли CEO/CFO, сохраняет разбор рисков и возможностей, источники и чат. Реальный AI работает через `team_ml.adapter` и внешний LLM; банковские PDF подключаются через локальный RAG. Материалы не являются индивидуальной инвестиционной рекомендацией.

## Проверка из чистого checkout

Нужны Git, Docker с Linux containers, Compose v2 с `--wait`, интернет для сборки и свободные порты 3100/8100. Python и Node на компьютере не нужны. Сборка содержит тяжёлые ML-зависимости; закладывайте несколько ГБ диска и памяти.

```sh
git clone https://github.com/verarod1/alfa-hack-news-analytics.git
cd alfa-hack-news-analytics
docker compose -f compose.review.yml up --build --wait --wait-timeout 180
docker compose -f compose.review.yml --profile check run --rm smoke
```

Откройте http://localhost:3100/demo. Swagger: http://localhost:8100/docs. OpenAPI: http://localhost:8100/openapi.json.

**Это синтетический технический тест, а не оценка качества AI.** Отдельная БД содержит три искусственные компании, платежи, связи и новости. Тестовый адаптер явно помечает ответы; внешние LLM/RSS не вызываются. `.env`, закрытые CSV и ключи не нужны. Не объединяйте проверочный и обычный Compose. Публичный пароль проверочной БД пригоден только для этого локального окружения.

Учётные записи не нужны: выберите `U_44564`, `U_19717` или `U_9250`, затем CEO/CFO. Это демо-контекст, не пользовательская аутентификация.

Проверка: [ACCEPTANCE](docs/ACCEPTANCE.md). Остановка: `docker compose -f compose.review.yml down`. Данные сохраняются в volume. SQL выполняется только при первом создании БД; повторный запуск не мигрирует старую схему. Для нового чистого прогона остановите старый стек и используйте новое имя проекта `-p alfa-review-2` во всех командах.

## Реальные данные и ML

1. Скопируйте `.env.example` в `.env`, задайте `POSTGRES_PASSWORD`. В PowerShell: `Copy-Item .env.example .env`.
2. Положите разрешённые CSV в `data/raw/`. Формат: [BACKEND_MVP](docs/BACKEND_MVP.md).
3. Подготовьте **новую** БД и импортируйте данные:

```sh
docker compose up -d db
docker compose cp backend/db/schema.sql db:/tmp/schema.sql
docker compose cp backend/db/mvp.sql db:/tmp/mvp.sql
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /tmp/schema.sql -f /tmp/mvp.sql'
docker compose build backend
docker compose run --rm backend python scripts/import_csv.py
docker compose up --build -d
```

Для старой MVP-схемы изучите `backend/db/upgrade_mvp_v2.sql`. Импорт не заменяет заполненные таблицы без явного `--replace`. Не меняйте пароль существующей БД только в `.env`: это не обновляет пароль в PostgreSQL.

Интерфейс: http://localhost:3000/demo, Swagger: http://localhost:8000/docs. Обычный Compose запускает PostgreSQL, API, frontend, analysis-worker и news-collector. Сборщик зависит от доступности реальных RSS. Сохранённые снимки можно загрузить командой `docker compose exec backend python scripts/import_news_fixtures.py`.

Для настоящего AI задайте `ML_ADAPTER_MODULE=team_ml.adapter`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` и выполните `docker compose up -d`. Анализ и чат передают контекст провайдеру и могут расходовать бюджет. Без адаптера разбор остаётся queued, чат возвращает 503. Ranking-worker включается отдельно: `NEWS_RANK_ENABLED=true` и `docker compose --profile ranking up -d`.

PDF и подготовка RAG: [BANK_PDF_GUIDE](docs/BANK_PDF_GUIDE.md), [README_ML_CORE](docs/README_ML_CORE.md). Индексация также вызывается лениво при поиске; первый запрос может потребовать загрузки embedding-модели, а OCR сканов — внешнего API. Без подтверждённого банковского источника `bank_opinion=null`.

## Конфигурация и архитектура

Полный шаблон: [.env.example](.env.example), типы и ограничения: [settings.py](backend/app/settings.py).

- БД: `POSTGRES_*`, приоритетный `DATABASE_URL`; внутри Compose `db:5432`, отдельный URI — `DOCKER_DATABASE_URL`. Порт БД наружу не опубликован.
- Данные: `DATA_DIR`, `DOCKER_DATA_DIR`, `BANK_PDF_DIR`; кэши: `CHROMA_DB_DIR`, `OCR_CACHE_DIR`, `HF_HOME`.
- AI: `ML_ADAPTER_MODULE`, `LLM_*`, `EMBEDDING_MODEL`, `RAG_TOP_K`.
- Новости: `NEWS_SOURCES`, `NEWS_LIMIT`, `NEWS_POLL_SECONDS`, `NEWS_MAX_AGE_DAYS`, `NEWS_KEYWORDS`; синтетика скрыта при `FEED_INCLUDE_SYNTHETIC=false`.
- Демо и порты: `DEMO_COMPANY_IDS`, `CORS_ORIGINS`, `BACKEND_PORT`, `FRONTEND_PORT`. Обычный Compose фиксирует три ID компаний.

React/TypeScript/Vite → nginx → FastAPI → PostgreSQL. Analysis-worker обрабатывает очередь `queued → running → completed/failed`; адаптер ML запускается отдельным процессом с таймаутом. News-collector сохраняет новости, ranking-worker — оценки по компании/роли. Chroma — встроенная файловая БД.

[Архитектура и модель данных](docs/ARCHITECTURE.md), [API](docs/api/API_CONTRACT.md), [компоненты и имитации](THIRD_PARTY_NOTICES.md), [комплект сдачи](SUBMISSION.md).

Python 3.11 в Docker; зависимости закреплены `backend/requirements.txt` и `requirements.lock`. Frontend устанавливается `npm ci` по `frontend/package-lock.json`. Docker-образы используют изменяемые теги; побитовая воспроизводимость и revision embedding-модели пока не зафиксированы.

## Проверки

```sh
python -m pip install -r backend/requirements-dev.txt
python -B -m unittest discover -s backend/tests -v
```

Frontend: `npm ci` и `npm run build` из `frontend/`. PostgreSQL integration runner: `backend/scripts/run_integration_tests.py`, требует отдельного временного Unix-socket кластера и PostgreSQL binaries на Linux/macOS. Обычный unit-прогон пропускает эти тесты. CI: `.github/workflows/acceptance.yml`.

[Результаты проверки](docs/VALIDATION.md). Исторические датированные отчёты и планы в docs не заменяют этот README.
