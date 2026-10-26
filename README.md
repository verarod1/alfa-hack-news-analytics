# 🚀 Новостная аналитика Альфа-Банка (Alfa Hack 2026)

В репозитории есть frontend, backend и ML-адаптер. Docker Compose запускает PostgreSQL, API, frontend и обработчик очереди анализов. Доступность источников и проверки сборщика описаны в [инструкции](docs/NEWS_COLLECTOR.md).

## 🛠 Как запустить проект у себя

1. **Склонируйте репозиторий:**
   ```bash
   git clone https://github.com/verarod1/alfa-hack-news-analytics.git
   cd alfa-hack-news-analytics
    ```

2. **Настройте переменные окружения:**
Никогда не пушьте ключи в GitHub! Скопируйте шаблон:
    ```bash
    cp .env.example .env
    ```


Откройте `.env` и задайте непустой `POSTGRES_PASSWORD`. ML пока отключён: ключ и Base URL заполняются только при подключении адаптера. Не добавляйте `.env` и исходные CSV в Git.
3. **Запустите всё одной командой:**
Убедитесь, что Docker Desktop запущен, и выполните:
```bash
docker compose up --build -d

```

Откройте **http://localhost:3000/demo** (или `http://10.6.7.1:3000/demo` в используемой локальной сети). Адрес с портом 5173 работает только при отдельном запуске Vite. В Compose фиксированы три демо-компании `U_44564`, `U_19717`, `U_9250`, каждая с двумя ролями. PostgreSQL доступна сервисам Compose по `db:5432` и не публикует порт на компьютере; для команд к БД используйте `docker compose exec db psql`.

При открытии новости API ставит анализ в очередь, а `analysis-worker` выполняет его автоматически, если настроены `ML_ADAPTER_MODULE`, `LLM_BASE_URL` и `LLM_API_KEY`. Реальный запрос к ML может расходовать бюджет. Неуспешный разбор можно повторить кнопкой на экране; автоматических повторов нет. Сбор новостей и предварительное ранжирование остаются отдельными командами. Проверить запуск: `docker compose ps` и `docker compose logs --tail=30 backend analysis-worker`.

Проверенные PDF банка подключаются по [пошаговому гайду](docs/BANK_PDF_GUIDE.md); после их добавления нужные новости пересчитываются кнопкой в интерфейсе.



## 🐍 Настройка локального окружения

Docker запускает код внутри контейнеров, поэтому ваш редактор (VS Code/PyCharm) локально не видит установленные библиотеки и может подчеркивать импорты (например, `fastapi`) желтым цветом.

Чтобы включить автодополнение и убрать ошибки в редакторе, настройте виртуальное окружение на своем компьютере:

1. **Откройте терминал в корне проекта и создайте окружение:**
```bash
python -m venv .venv

```


2. **Активируйте его:**
* Windows: `.\.venv\Scripts\activate`
* Mac/Linux: `source .venv/bin/activate`


3. **Установите зависимости бэкенда локально:**
```bash
(cd backend && python -m pip install -r requirements.txt)

```


4. В VS Code нажмите `Ctrl+Shift+P` (или `Cmd+Shift+P`), введите `Python: Select Interpreter` и выберите созданное окружение (`'.venv': venv`).

## Импорт CSV в PostgreSQL

Импортёр проверяет три CSV и загружает их в `raw_companies`, `raw_payments`
и `raw_person_links`. Без аргументов запуск разрешён только при пустых таблицах:
повторный импорт останавливается без удаления данных и добавления дубликатов.
При ошибке загрузки изменения откатываются. Схема БД должна быть подготовлена заранее.

Для базы, запущенной текущим Compose, выполняйте импорт внутри backend-контейнера:

В актуальном `.env.example` указан `DATA_DIR=data/raw`: разместите исходные CSV
в этой папке вручную. Существующие файлы автоматически не перемещаются.
В Docker путь задаёт `DOCKER_DATA_DIR` (по умолчанию `/app/data/raw`). Если ваш
набор пока лежит непосредственно в `data/`, сохраните локальный `DATA_DIR=data`,
а для контейнера задайте `DOCKER_DATA_DIR=/app/data`; `.env` не публикуйте.

```sh
docker compose exec backend python scripts/import_csv.py
```

`--replace` нужен для полной перезагрузки: добавьте его к команде запуска.
**Он заменяет существующие данные трёх таблиц и может временно блокировать чтение.**
Проверьте целевую базу и сохраните резервную копию перед использованием.

Настройки берутся из окружения или корневого `.env` (окружение имеет приоритет):

- `DATABASE_URL` — строка подключения; имеет приоритет над отдельными параметрами.
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` — в Compose
  используются `db`, `5432` и значения из `.env`; `POSTGRES_PASSWORD` — обязательный пароль.
- `DATA_DIR` — каталог CSV: по умолчанию `data/`, в Docker — `/app/data`.
- `DOCKER_DATABASE_URL` — переопределение подключения backend в Compose.
  Используйте адрес `db:5432` и URL-кодирование специальных символов пароля.

Тесты не подключаются к рабочей PostgreSQL:

```sh
python -B -m unittest discover -s backend/tests -v
```

Подробности серверного MVP, проверки API и подключение ML: [инструкция backend](docs/BACKEND_MVP.md).

## Ручной сбор реальных новостей

Проверка без подключения к PostgreSQL и без вызовов ML:

```sh
python backend/scripts/collect_news.py --source cbr --limit 3 --dry-run
```

Для сохранения в заранее подготовленную целевую БД уберите `--dry-run`.
Доступны `--source cbr|minfin|fns|all`, тематический отбор и ограничение давности.
Сборщик не запускается вместе с FastAPI и не запускает платный AI-анализ.
Команды Docker, настройки, проверенные ограничения и стыковка с ML:
[NEWS_COLLECTOR.md](docs/NEWS_COLLECTOR.md).

## Интегрированный сценарий MVP

После загрузки новостей и настройки `ML_ADAPTER_MODULE=team_ml.adapter`:

```sh
# Ограниченный запуск; с настоящим LLM-ключом расходует бюджет.
python backend/scripts/rank_news.py --company-id U_81 --role cfo --limit 3
# При запуске через Compose очередь обрабатывает analysis-worker.
# Для запуска backend вне Compose доступна ручная команда:
python backend/scripts/process_analyses.py --limit 3
```

Ранкер сохраняет оценки отдельно для каждой компании/роли; ошибки не заменяются
выдуманными числами. RAG и OCR запускаются отдельно, постоянные каталоги состояния
монтируются для записи, исходные CSV/PDF — только для чтения.
Команды индексации, конфигурация и ограничения: [Backend + ML](docs/README_ML_CORE.md).

## Backend с нуля и интеграция ML

Нужны Python 3.11, Docker Compose и разрешённые локальные CSV. Приватность
репозитория и доступ жюри проверяются отдельно; CSV нельзя публиковать в публичном
репозитории. Их фактические пути защищены .gitignore.

После настройки .env установите зависимости в активированное окружение:

```sh
python -m pip install -r backend/requirements-dev.txt
```

Версии зафиксированы в requirements.txt/requirements.lock. Используются существующие
POSTGRES_HOST/PORT/DB/USER/PASSWORD либо приоритетный DATABASE_URL. В Docker backend
получает host=db, port=5432 и отдельный DOCKER_DATABASE_URL, если он задан. Локальный
DATABASE_URL намеренно не переносится в контейнер. Пользователь/база/внешний порт db
настраиваются через env. Не меняйте пароль уже созданного volume одним редактированием env:
это не меняет пароль самой существующей БД.

**Следующие команды создают таблицы и загружают данные. Они приведены как инструкция;
для рабочей БД нужны отдельное разрешение и резервная копия. Схемы не применяются при старте API.**

```sh
# Запуск PostgreSQL (не удаляет volumes).
docker compose up -d db
# Первый запуск схем в выбранной базе:
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < backend/db/schema.sql
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < backend/db/mvp.sql
# Если прежняя MVP-схема уже создавалась: сначала upgrade_mvp_v2.sql, затем текущий mvp.sql.
# Старые completed-результаты отдельно проверить на новый DTO statements/sources.
```

CSV поместите в `data/raw/` согласно `DATA_DIR` с именами из раздела импорта.
Для локальной загрузки используйте `python backend/scripts/import_csv.py`. По умолчанию
заполненные таблицы не очищаются; --replace явно заменяет три исходные таблицы.
Демонстрационные новости: `python backend/scripts/seed_demo_news.py`; скрипт пишет
только синтетические данные, повторный запуск не создаёт копии. Для рабочей БД его
запуск также требует разрешения. После замены raw-данных старые анализы не удаляются;
их актуальность нужно проверить отдельно.

```sh
# Локальный API:
python -m uvicorn app.api.main:app --app-dir backend --reload
# Либо весь стек после подготовки базы:
docker compose up --build -d
```

Актуальный демо-набор Compose: `U_44564,U_19717,U_9250`, роли `ceo/cfo`.
Compose фиксирует эти ID независимо от переменных текущего терминала. Для запросов
передавайте `X-Company-ID` выбранной компании; старые примеры U_81 ниже относятся
к прежней конфигурации.

Swagger: http://localhost:8000/docs. Без данных работает roles; остальные сценарии
требуют подготовленной БД. По умолчанию доступны CLIENT U_44564, U_19717, U_9250; ранее был выбран U_81, он подтверждён в исходных
данных; разрешённые CLIENT-ID перечисляются в DEMO_COMPANY_IDS. Заголовок X-Company-ID
выбирает компанию из этого списка. Это демо-контекст, не авторизация пользователя.

```sh
curl 'http://localhost:8000/api/v1/companies/U_81'
curl 'http://localhost:8000/api/v1/demo-profiles'
curl 'http://localhost:8000/api/v1/feed?company_id=U_81&role=cfo&limit=20&offset=0'
curl 'http://localhost:8000/api/v1/my-analyses?company_id=U_81&role=cfo&tab=attention&status=completed'
```

Вкладки сохранённых разборов: all=«Все», ready=«Готовые», processing=«В обработке»,
attention=«Требуют внимания». Последняя фильтрует importance important/critical,
не status failed. Это соглашение ожидает подтверждения команды. Status и importance
можно комбинировать, повторяя параметры в query. null не считается важным.

POST /api/v1/analyses принимает company_id/role/news_id, создаёт запись и возвращает
202/queued. После подключения ML конечный обработчик запускается отдельно:

```sh
python backend/scripts/process_analyses.py --limit 5
```

Жизненный цикл: queued → running → completed/failed. Без ML задача остаётся queued,
result=null; фиктивных успешных результатов нет. GET /analyses/{id} отдаёт безопасный
error_code при failed. Повтор: --analysis-id ID --retry --company-id U_81, только
failed/просроченная running в пределах лимита. См. [интерфейс ML](docs/ML_INTEGRATION.md).
Автоматической бесконечной очереди при запуске API нет.

Feed принимает готовые оценки ML и сортирует их до пагинации. Пока их нет,
ranking_mode=chronological и relevance_score=null — это ещё не персональное ранжирование.
Материалы содержат дисклеймер об отсутствии индивидуальной инвестрекомендации.
Чат без ML сохраняет вопрос и отвечает 503; передавайте Idempotency-Key, чтобы
повтор с тем же текстом не дублировал сообщение. Без ключа повторы не объединяются.

```sh
# Unit/mock без рабочей базы:
python -B -m unittest discover -s backend/tests -v
# Интеграционные сценарии в отдельном временном PostgreSQL без TCP/volumes:
POSTGRES_TEST_BIN=/opt/homebrew/opt/postgresql@16/bin python -B backend/scripts/run_integration_tests.py
```

Для Linux задайте каталог PostgreSQL 16 с initdb/pg_ctl или добавьте его в PATH.
Тестовый runner печатает отдельную цель, проверяет data_directory/имя базы и удаляет
только свои временные ресурсы после остановки. Не указывайте рабочую БД для тестов.
Подробности и ограничения: [Backend MVP](docs/BACKEND_MVP.md).

## 🌍 Доступные сервисы

После успешного запуска всё крутится локально:

* **Frontend (React/Vite):** http://localhost:3000
* **Backend API (FastAPI):** http://localhost:8000
* **Документация API (Swagger):** http://localhost:8000/docs (используйте для тестирования эндпоинтов)

## 📁 Где мы пишем код (Структура проекта)

Ориентируемся на следующую структуру папок, чтобы не блокировать друг друга:

* `backend/app/parsers/` — сбор внешних новостей и парсинг данных.
* `backend/app/agents/` — многошаговая логика AI, вызовы LLM и RAG-поиск.
* `backend/app/services/` — вспомогательная логика, графы, обработка данных.
* `backend/api/` — эндпоинты FastAPI и точка входа `main.py`.
* `frontend/src/` — UI/UX и взаимодействие с бэкендом (React/Vite).
* `docs/` — документация по проекту (например, архитектура).

> **Важно:** Сырые тяжелые данные и выборки (в папках `data/raw/` и `data/synthetic_samples/`) лежат локально и в гит не отправляются.

## 🛡 Правила работы с Git

Прямые пуши в ветку `main` **не рекомендуются** без предварительного согласования с командой. Старайтесь придерживаться следующего workflow:

1. Возьмите задачу и создайте свою ветку от `main`:
```bash
git checkout -b feat/your-feature-name

```


2. Пишите код, делайте коммиты:
```bash
git commit -m "feat: add news parser"

```


3. Пушьте ветку:
```bash
git push origin feat/your-feature-name

```


4. Заходите на GitHub и создавайте Pull Request. Это поможет избежать конфликтов и держать код в порядке.
