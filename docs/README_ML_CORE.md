# Backend + ML: запуск MVP

Рабочая интеграция находится в `integration/backend-ml-mvp`. Backend и ML исходных
веток сохранены в истории. `main` автоматически не обновляется.

## Конфигурация

Скопируйте `.env.example` в `.env`, задайте пароль локальной PostgreSQL.
Для реального ML задайте `ML_ADAPTER_MODULE=team_ml.adapter`, `LLM_BASE_URL`,
`LLM_API_KEY`, `LLM_MODEL` из согласованного списка. Ключ не публикуйте.
`LLM_RANK_MODEL` и `LLM_CHAT_MODEL` необязательны: пустое значение использует
`LLM_MODEL`. Таймаут и лимит ответа: `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS`.
Модели передаются провайдеру через mapping в `llm_client.py`; доступность конкретного
идентификатора у выданного провайдера нужно проверить с ML-разработчицей.

Для CPU сохраняется индекс PyTorch CPU в requirements. Итоговые версии фиксируются
в `backend/requirements.lock`; установка: `cd backend && python -m pip install -r requirements.txt`.

## Запуск и новости

Из корня проекта:

```bash
docker compose config --quiet
docker compose build backend
docker compose up -d db backend
# Один раз, только после проверки целевой локальной БД:
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backend/db/mvp.sql
# Сначала посмотреть, затем сохранить не более трёх реальных новостей:
docker compose exec backend python scripts/collect_news.py --source cbr --limit 3 --dry-run
docker compose exec backend python scripts/collect_news.py --source cbr --limit 3
```

Для существующей старой MVP-схемы предварительно изучите
`backend/db/upgrade_mvp_v2.sql`; миграции не выполняются при старте API.
Исходные CSV загружаются существующим импортёром отдельно, не автоматически.
Swagger: `http://localhost:8000/docs`, схема: `/openapi.json`.
Если порт 8000 занят, используйте `BACKEND_PORT=8001 docker compose up -d db backend`;
тогда Swagger доступен на `http://localhost:8001/docs`. `.env` менять необязательно.

## Ранжирование, анализ и чат

Следующие команды с реальным ключом могут расходовать бюджет. Они не запускаются
автоматически ни при сборке, ни при старте приложения.

```bash
docker compose exec backend python scripts/rank_news.py --company-id U_44564 --role cfo --limit 3
# POST /api/v1/analyses возвращает analysis_id и queued. Затем:
docker compose exec backend python scripts/process_analyses.py --limit 3
```

`GET /api/v1/feed?company_id=U_44564&role=cfo` показывает сохранённые оценки.
Без оценок лента честно возвращает `ranking_mode=chronological` и `null`.
Фильтр `impact_type` использует завершённый анализ: оценка релевантности сама по
себе не доказывает наличие риска или возможности.

Статусы анализа: `queued → running → completed/failed`. Это не `importance`.
После завершения используйте `POST /api/v1/chat/messages` с `analysis_id` и
`message`; история: `GET /api/v1/analyses/{analysis_id}/messages`.
Передавайте `X-Company-ID` выбранной компании. Это демо-контекст, не авторизация.
Ошибки LLM не заменяются успешным фиктивным анализом или оценкой `0.5`.

## PDF и постоянное состояние

- `data/raw/` — исходные CSV, `data/raw/bank_analytics/` — только проверенные PDF банка.
- `data/chroma_db/` — индекс, `data/ocr_cache/` — постраничный кэш и манифест.
- `data/model_cache/` — скачанная модель эмбеддингов.

Compose монтирует исходники только для чтения, три каталога состояния — для записи.
Они сохраняются при пересоздании контейнера и исключены из Git. В GitHub передаётся
код; заполненную ChromaDB и документы команда получает отдельно по разрешённому каналу.

```bash
# Текстовые PDF или уже распознанные страницы; платный OCR запрещён по умолчанию.
docker compose exec backend python -m app.services.rag --limit 5
# Только после отдельного решения команды о расходовании бюджета:
# docker compose exec backend python -m app.services.rag --limit 5 --allow-ocr
```

Первичная индексация скачивает embedding-модель. Запросы анализа работают с локальным
кэшем, не запускают индексацию/OCR и не скачивают модель из Hugging Face.
Новый PDF определяется по SHA-256; успешно распознанная страница записывается на диск
до индексации. Повторный запуск не распознаёт её заново. Новые PDF добавляются даже
при заполненной базе. Номера страниц настоящие, а не всегда `1`.
Кэш старого формата `/tmp/extracted_text_cache.json` не переносится автоматически:
без проверки содержания нельзя восстановить достоверные страницы и хеши PDF.
Старые коллекции Chroma не удаляются; новый индекс отделён по embedding-модели.

Манифест `data/ocr_cache/bank_materials.json` создаётся индексатором; обычно
`BANK_MATERIALS_PATH` оставляют пустым. Для своего манифеста задайте путь явно,
в Docker — через `DOCKER_BANK_MATERIALS_PATH`. Backend независимо проверяет
`document_id`, страницу и цитату. Сообщения ЦБ/Минфина/ФНС не являются позицией
Альфа-Банка. Без подтверждённых документов `bank_opinion=null`.

## Безопасные проверки

```bash
PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -B -m unittest discover -s backend/tests -v
PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -B backend/scripts/run_integration_tests.py
```

Вторая команда создаёт отдельный временный PostgreSQL без TCP (нужны локальные
`initdb` и `pg_ctl`, путь можно задать через `POSTGRES_TEST_BIN`). Рабочая БД не
меняется. Интеграционные ответы LLM явно заменены тестовыми: эти проверки подтверждают
связность системы, но не качество реальных инсайтов, ранжирования или OCR.
