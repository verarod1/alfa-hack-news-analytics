# Запуск и ручная проверка MVP

Проверено 25 октября 2026 года на macOS Apple Silicon. Полный Backend + ML запускайте
из **main** либо **integration/backend-ml-mvp**. В `feature/backend-mvp` сохраняются
серверные изменения без ML-коммитов; это не ветка для демонстрации полного стека.

Рабочие адреса этой инструкции:

- Backend/Swagger: **http://localhost:8001/docs**.
- OpenAPI: http://localhost:8001/openapi.json.
- PostgreSQL внутри Compose: `db:5432`; актуальный main не публикует порт БД на компьютер.
- Существующий frontend: **http://localhost:3000**.

**Про визуал:** в актуальном main есть интерфейс выбора компании, ролей, ленты,
разбора и чата. Открой http://localhost:3000/demo, выбери профиль и роль,
затем «Открыть Альфа-Бизнес» → «Перейти к новостям». По умолчанию используется
реальный API через nginx `/api/`; моки включаются только явно. Баланс/операции
на банковском домашнем экране демонстрационные, не данные PostgreSQL.

## 1. Программы и правильная папка

**Действие:** запустить Docker Desktop для Apple Silicon и открыть проект в VS Code.
Git и Docker Compose необходимы; Node/npm на компьютере для Docker-варианта не нужны.
Python 3.11 и PostgreSQL 16 binaries нужны только для локальных интеграционных тестов.

**Команды:**

```bash
open -a Docker
cd "/Users/mac/Desktop/проекты/Альфа-бизнес/alfa-hack-news-analytics"
pwd
git status --short
git branch --show-current
docker info --format '{{.ServerVersion}} {{.Architecture}}'
```

**Ожидается:** правильная папка, Docker отвечает и сообщает ARM/aarch64.
**При ошибке:** дождись запуска Docker Desktop. Если есть несохранённые изменения Git,
сначала сохрани их отдельно; не используй reset/clean/stash автоматически.

Для чистой рабочей папки:

```bash
git fetch origin
git switch main
git merge --ff-only origin/main
```

**Ожидается:** актуальный main. **При ошибке:** если fast-forward невозможен, не делай
принудительный reset — нужно отдельно разобраться с локальной историей.

## 2. Конфигурация без раскрытия секретов

**Действие:** создать `.env` только если его ещё нет.

```bash
[ -f .env ] || cp .env.example .env
```

Открой `.env` в редакторе и проверь:

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=alfa_news
POSTGRES_USER=alfa_user
POSTGRES_PASSWORD=
DATABASE_URL=
DOCKER_DATABASE_URL=
DEMO_COMPANY_IDS=U_44564,U_19717,U_9250
DATA_DIR=data/raw
DOCKER_DATA_DIR=/app/data/raw
NEWS_SOURCES=cbr,interfax,finmarket
ML_ADAPTER_MODULE=
LLM_API_KEY=
LLM_BASE_URL=
```

**Ожидается:** в POSTGRES_PASSWORD указан твой действующий локальный пароль; ключи
LLM для первого безопасного прогона не нужны. Пустые DATABASE_URL/DOCKER_DATABASE_URL
означают использование отдельных параметров подключения. Docker сам задаёт `db:5432`.

**При ошибке:** не меняй пароль существующего PostgreSQL volume только правкой `.env`:
это не меняет пароль в самой БД. Не публикуй `.env`, пароли и ключи в Git/скриншотах.
Существующий `.env` не перезаписывается шаблоном.

В каждом новом терминале для этой инструкции задай:

```bash
export BACKEND_PORT=8001
export FRONTEND_PORT=3000
export DEMO_COMPANY_IDS=U_44564,U_19717,U_9250
export ML_ADAPTER_MODULE=
```

Порт 8001 выбран потому, что 8000 может быть занят локальным Uvicorn. Последняя
строка явно отключает реальные ML-вызовы в первом прогоне, даже если старый `.env`
содержит другое значение. Три компании заменяют прежний демо-набор U_81 только
в настройках доступа: исходные записи U_81 из БД не удаляются.

## 3. Docker, PostgreSQL и Backend

**Команды:**

```bash
docker compose config --quiet
docker compose build backend frontend
docker compose up -d db backend frontend analysis-worker news-collector
docker compose ps
curl -f http://localhost:8001/openapi.json
```

**Ожидается:** db healthy, backend запущен, OpenAPI возвращает JSON. CPU PyTorch
сохранён; первая загрузка ML-библиотек может занять десятки минут, следующие сборки
используют кэш. Swagger: http://localhost:8001/docs.

**При ошибке:**

```bash
docker compose logs --tail=80 backend db
```

Не публикуй логи без проверки. При ошибке Docker Hub повторно проверь сеть/Docker
Desktop; не отключай TLS. Если уже есть проверенный локальный образ с зависимостями
`alfa-mvp-deps:local`, проверен и такой вариант сборки:

```bash
docker image inspect alfa-mvp-deps:local --format '{{.Id}}'
docker compose build --build-arg PYTHON_IMAGE=alfa-mvp-deps:local backend
```

Если образ отсутствует, используй обычную сборку, а не случайный сторонний образ.

## 4. Таблицы и CSV — только если база ещё не подготовлена

**Действие:** посмотреть текущую базу и таблицы.

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database();" -c "\dt"'
```

**Ожидается:** `alfa_news`, raw_companies/raw_payments/raw_person_links и таблицы MVP.
На проверенной локальной базе они уже созданы — повторная подготовка не нужна.

**Только для новой локальной БД без этих таблиц:**

```bash
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backend/db/schema.sql
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backend/db/mvp.sql
```

**При ошибке старой MVP-схемы:** изучи `backend/db/upgrade_mvp_v2.sql` и текущую схему;
не удаляй таблицы/volume ради исправления. Удалённую рабочую БД эти команды не обслуживают.

**Действие:** при необходимости разместить разрешённые командные CSV вручную в
`data/raw/` с именами:

- `df_Uid_data_hack.csv`;
- `df_Uid_payment_hack.csv`;
- `df_Fid_Uid_link_hack.csv`.

Если твои файлы уже лежат непосредственно в `data/`, не перемещай их автоматически:
в локальном `.env` используй `DATA_DIR=data`, `DOCKER_DATA_DIR=/app/data` и пересоздай
backend через `docker compose up -d backend`. Это только пути чтения.

**Команды проверки и первого импорта:**

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT (SELECT count(*) FROM raw_companies) AS companies, (SELECT count(*) FROM raw_payments) AS payments, (SELECT count(*) FROM raw_person_links) AS person_links;"'
# Запускай только если все три таблицы пусты:
docker compose exec backend python scripts/import_csv.py
```

**Ожидается:** первый импорт заполняет raw-таблицы. Повторный отказывается изменять
заполненные данные. В проверенной базе уже 85 525 / 1 380 585 / 12 514 строк.
**При ошибке:** проверь пути/имена/подключение. Не добавляй `--replace` ради устранения
ошибки: он заменяет данные трёх таблиц и может временно блокировать чтение.

## 5. Сбор доступных новостей

**Действие:** сначала проверить ЦБ без записи, затем сохранить ограниченную порцию.

```bash
docker compose exec backend python scripts/collect_news.py --source cbr --limit 3 --dry-run
docker compose exec backend python scripts/collect_news.py --source cbr --limit 3
```

**Ожидается:** реальные заголовки, даты, URL и текст, errors=[]; повторный запуск не
создаёт копий. Сейчас в демонстрационной БД 3 новости ЦБ.
**При ошибке:** смотри код в JSON. Недоступность источника не исправляется отключением
robots/TLS или обходом ограничений.

Дополнительный подтверждённый официальный источник — Правительство России:

```bash
docker compose exec backend python scripts/collect_news.py --source government --limit 3
docker compose exec backend python scripts/collect_news.py --source all --limit 3
```

**Ожидается:** сохранение/возврат существующих ID без дубликатов. NEWS_SOURCES по
умолчанию `cbr,government`. Сервис `news-collector` повторяет ограниченный сбор
каждые NEWS_POLL_SECONDS (по умолчанию 1800 секунд), максимум 5 записей на источник
за цикл; ML не запускает. Правительство предоставляет официальный канал по HTTP;
это явно ограниченное исключение для government.ru, HTTPS других источников сохранён.
Интерфакс/Финмаркет остаются заблокированными до подтверждения прав и по умолчанию
не опрашиваются. Статус источников и реальные проверки — в INTEGRATION_2026_10_26.md.

## 6. Локальные официальные фикстуры

**Команды:**

```bash
docker compose exec backend python scripts/import_news_fixtures.py --dry-run
docker compose exec backend python scripts/import_news_fixtures.py
docker compose exec backend python scripts/import_news_fixtures.py
```

**Ожидается:** проверка без сети, затем те же два ID при обоих импортах, failed=[].
Файл `backend/fixtures/official_news.json` содержит 2 реальные публикации ФНС от
23.10.2026 с исходными ссылками и текстами. Они не синтетические и не выдаются за
свежие публикации сегодняшнего дня. Минфин пока содержит **0** фикстур: без проверенного
текста публикации не создавались. Его RSS повторно восстанавливать не нужно.

**При ошибке:** проверь JSON, заполненность текста, timezone, официальный URL и
состояние БД. Конфликт содержимого не перезаписывает старую новость.
Подробности происхождения — `docs/NEWS_MVP_STATUS.md`.

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT source_id, count(*), count(DISTINCT content_hash) FROM news GROUP BY source_id ORDER BY source_id;"'
```

**Ожидается на текущей базе:** cbr=3, fns=2, число уникальных хешей равно числу записей.

## 7. Запуск интерфейса вместе с Backend

```bash
docker compose up -d --no-deps frontend
curl -f http://localhost:3000/api/v1/roles
```

**Ожидается:** http://localhost:3000/demo показывает три компании и две роли;
HTTP-запрос через frontend/nginx возвращает роли Backend. Для компаний нужны
реальные CSV в PostgreSQL; на пустой базе список будет пустым.
**При ошибке:** `docker compose logs --tail=80 frontend backend`; проверь свободный
порт 3000 и upstream backend:8000. Frontend-исходники менять для запуска не нужно.
Подробный прогон с новой БД и без локальных кэшей — `docs/DOCKER_CLEAN_MACHINE.md`.

## 8. Компании, роли, карточки и связи

**Действие:** в Swagger выбери endpoint → Try it out → заполни параметры → Execute.

**Команды альтернативной проверки:**

```bash
curl -fsS http://localhost:8001/api/v1/demo-profiles
curl -fsS http://localhost:8001/api/v1/roles
curl -fsS -H 'X-Company-ID: U_44564' http://localhost:8001/api/v1/companies/U_44564
curl -fsS -H 'X-Company-ID: U_19717' http://localhost:8001/api/v1/companies/U_19717
curl -fsS -H 'X-Company-ID: U_9250' http://localhost:8001/api/v1/companies/U_9250
curl -fsS -H 'X-Company-ID: U_44564' http://localhost:8001/api/v1/companies/U_44564/relations
```

**Ожидается:** 6 демо-профилей — три компании × ceo/cfo; карточки и связи возвращают
200. Аналогично проверь `/relations` для двух других компаний. Названия компаний
условные, отрасли и показатели взяты из данных, неизвестные значения остаются null.
Связи платежей не означают автоматически владение или договор конкретного типа.

**При ошибке:** 403 — проверь DEMO_COMPANY_IDS и совпадение X-Company-ID с company_id;
404 — проверь импорт CSV; 409 — неоднозначные исходные записи нельзя объединять наугад.

## 9. Лента и открытие новости

```bash
curl -fsS -H 'X-Company-ID: U_44564' 'http://localhost:8001/api/v1/feed?company_id=U_44564&role=cfo&limit=20&offset=0'
curl -fsS -H 'X-Company-ID: U_19717' 'http://localhost:8001/api/v1/feed?company_id=U_19717&role=ceo&limit=20&offset=0'
curl -fsS http://localhost:8001/api/v1/news/news_fns_5626c2076b90788cc5caeadd5df76bcc
```

**Ожидается:** общая база новостей, корректные источники/даты/текст. Последний ID
берётся из первой официальной фикстуры и доступен после её импорта. Списка GET `/news`
в контракте нет: список — `/feed`, отдельная публикация — `/news/{news_id}`.
Пока реальное ML-ранжирование не запускалось: ranking_mode=chronological, score=null.
Это корректное отсутствие оценки, а не персонализированное ранжирование.

**При ошибке:** проверь импорт фикстур и X-Company-ID. Для переключения роли поменяй
role на ceo/cfo; для компании поменяй и company_id, и заголовок. Фильтр impact_type
использует завершённый анализ, поэтому до анализов фильтр risk может дать пустой список.

## 10. Анализ, результат и чат без платных вызовов

**Действие:** создать задачу. Эти команды сами по себе не запускают LLM.

```bash
BASE=http://localhost:8001
COMPANY_ID=U_44564
ROLE=cfo
NEWS_ID=news_fns_5626c2076b90788cc5caeadd5df76bcc
ANALYSIS_ID=$(curl -fsS -X POST "$BASE/api/v1/analyses" -H 'Content-Type: application/json' -H "X-Company-ID: $COMPANY_ID" -H "Idempotency-Key: guide-$COMPANY_ID-$ROLE-$NEWS_ID" -d "{\"company_id\":\"$COMPANY_ID\",\"role\":\"$ROLE\",\"news_id\":\"$NEWS_ID\"}" | docker compose exec -T backend python -c 'import json,sys; print(json.load(sys.stdin)["analysis_id"])')
curl -fsS -H "X-Company-ID: $COMPANY_ID" "$BASE/api/v1/analyses/$ANALYSIS_ID"
curl -fsS -H "X-Company-ID: $COMPANY_ID" "$BASE/api/v1/analyses/$ANALYSIS_ID/trace"
```

**Ожидается:** POST вернул 202 и analysis_id; при отключённом ML статус queued и
result=null. Анализ не обрабатывается автоматически при старте API. Idempotency-Key
защищает повторный запрос с теми же параметрами от создания копии.
**При ошибке:** 422 — проверь JSON и ID новости; 403 — company scope; 404 — данные БД.

**Проверка чата/истории:**

```bash
curl -sS -X POST "$BASE/api/v1/chat/messages" -H 'Content-Type: application/json' -H "X-Company-ID: $COMPANY_ID" -H "Idempotency-Key: guide-chat-$ANALYSIS_ID" -d "{\"analysis_id\":\"$ANALYSIS_ID\",\"message\":\"Какие факты подтверждают вывод?\"}"
curl -fsS -H "X-Company-ID: $COMPANY_ID" "$BASE/api/v1/analyses/$ANALYSIS_ID/messages"
curl -fsS -H "X-Company-ID: $COMPANY_ID" "$BASE/api/v1/my-analyses?company_id=$COMPANY_ID&role=$ROLE&limit=20"
```

**Ожидается без ML:** вопрос сохраняется, чат отвечает 503 ML_UNAVAILABLE; готового
ответа/анализа не подделывает. При включённом ML и незавершённом анализе возможен 409.
История доступна. Чтобы увидеть completed и ответ ассистента без оплаты, запускай
изолированные тесты ниже — тестовый адаптер в рабочую демо-БД не подключай.

## 11. Подключение реального ML и RAG — отдельное решение о расходах

**Не выполнялось автоматически.** Только если команда решила использовать настоящий
сервис, заполни локальные LLM_BASE_URL/LLM_API_KEY и согласованные названия моделей.
Например, уже поддерживаемые имена: GLM-5.3-Flash, Gemma-4-26B-A4B, Qwen3.6-35B-A3B.
Точные доступные provider IDs и бюджет подтверждает ML-разработчица.
LLM_RANK_MODEL/LLM_CHAT_MODEL необязательны; пустые используют LLM_MODEL.
Таймаут и размер ответа — LLM_TIMEOUT_SECONDS и LLM_MAX_TOKENS.

```bash
export ML_ADAPTER_MODULE=team_ml.adapter
docker compose up -d --no-deps --force-recreate backend
```

**Ожидается:** API подключает существующий адаптер; старт не запускает массовые
LLM/OCR. **При ошибке:** проверь конфигурацию и безопасный error_code, не печатай ключ.

Разрешённые PDF банка размещаются вручную в `data/raw/bank_analytics/`, не в Git.
Chroma — `data/chroma_db/`, OCR — `data/ocr_cache/`, embedding-кэш — `data/model_cache/`.
Старый `data/cache/` также исключён из Git. Compose сохраняет состояние при пересоздании;
CSV/PDF read-only, каталоги состояния writable.

```bash
# Текстовые PDF/уже подготовленные страницы; платный OCR по умолчанию запрещён.
docker compose exec backend python -m app.services.rag --limit 5
```

**Ожидается:** индекс и манифест проверенных страниц; новые PDF добавляются без
повторной обработки готовых страниц. Для сканов без кэша будет pending. Не добавляй
`--allow-ocr`, пока команда отдельно не разрешила платное распознавание. Реальных PDF
в проверенной рабочей папке пока нет. Старый кэш без достоверных страниц/хеша не
переносится автоматически. После подготовки индекса проверяй цитаты и номера страниц.

**Только для согласованного платного прогона:**

```bash
docker compose exec backend python scripts/rank_news.py --company-id U_44564 --role cfo --limit 3
docker compose exec backend python scripts/process_analyses.py --analysis-id "$ANALYSIS_ID"
```

**Ожидается:** сохранённые оценки компании/роли; queued → running → completed/failed.
После completed повтори GET анализа/trace и POST чата из предыдущего раздела.
С тем же ключом чата сохранённый вопрос не дублируется. История содержит ответ
ассистента и evidence_ids. При ошибке ML оценка 0.5 и успешный ответ не выдумываются.

Для явного повтора failed/просроченного running после исправления конфигурации:

```bash
docker compose exec backend python scripts/process_analyses.py --analysis-id "$ANALYSIS_ID" --retry --company-id "$COMPANY_ID"
```

**При ошибке цитирования:** результат отклоняется; не отключай проверку источников.
Без подтверждённой банковской аналитики bank_opinion=null. Новость ЦБ/ФНС не является
позицией Альфа-Банка. Уровень importance независим от статуса выполнения анализа.

## 12. Безопасные тесты

**Основной набор в существующем контейнере:**

```bash
docker compose exec backend python -B -m unittest discover -s tests -v
```

**Ожидается:** основные тесты проходят; PostgreSQL-сценарии намеренно
пропущены и запускаются отдельным runner ниже. SDK проверяется через локальный HTTP stub, RAG — без оплаченного OCR.
**При ошибке:** проверь, что контейнер собран из main и использует актуальные файлы.

**Отдельный временный PostgreSQL** (если локальное Python-окружение ещё не создано,
команда установки необходима только для этого варианта):

```bash
python3.11 -m venv backend/.venv
(cd backend && .venv/bin/python -m pip install -r requirements-dev.txt)
POSTGRES_TEST_BIN=/opt/homebrew/opt/postgresql@16/bin PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -B backend/scripts/run_integration_tests.py
```

Не пересоздавай уже настроенный backend/.venv — в этом случае первые две команды
пропусти. **Ожидается:** 10/10; runner создаёт свой кластер без TCP, проверяет целевой
каталог/имя БД и удаляет только свои ресурсы. Рабочая alfa_news не меняется.
**При ошибке:** нужны доступные initdb/pg_ctl PostgreSQL 16 и Python 3.11; проверь
POSTGRES_TEST_BIN. Не подставляй рабочую DATABASE_URL как тестовый кластер.

## 13. Короткий сценарий демонстрации

1. Открой http://localhost:8001/docs, выполни roles и demo-profiles: 2 роли, 6 профилей.
2. Выбери U_44564: карточка, /relations, затем /feed с role=cfo и соответствующим заголовком.
3. Повтори для U_19717 и U_9250; поменяй ceo/cfo. База новостей общая, оценки отдельно по контексту.
4. Открой новость: реальный текст, дата, ФНС/ЦБ и исходная ссылка. Повтори импорт: число записей не выросло.
5. Создай анализ: сохрани analysis_id, проверь статус/trace/my-analyses.
6. В безопасном режиме покажи queued и сохранение вопроса без поддельного AI-ответа.
7. Только в отдельно согласованном реальном прогоне запусти ограниченный worker,
   покажи completed, подтверждённые источники, историю чата. Иначе покажи результаты изолированных тестов.
8. Открой localhost:3000/demo, повтори выбор компаний/ролей и открытие новостей через настоящий интерфейс. Разделы связей и списка сохранённых анализов ещё требуют отдельных UI-экранов.

## 14. Остановка без удаления данных

```bash
docker compose stop frontend backend analysis-worker news-collector db
```

**Ожидается:** сервисы остановлены, PostgreSQL volume и Chroma/OCR/model cache сохранены.
Запуск снова — команды раздела 3 и `docker compose up -d --no-deps frontend`.
Не используй `docker compose down -v` и не удаляй каталоги состояния ради перезапуска.

Оставшиеся ограничения: 0 фикстур Минфина; права на Интерфакс/Финмаркет не подтверждены;
качество реальных LLM/OCR/эмбеддингов требует проверки команды на разрешённых PDF и
ограниченном бюджете; UI связей и списка сохранённых анализов ещё не реализован. Готовые кэши
не отслеживаются, но старый OCR-blob остаётся в истории ML — историю не переписывали.
