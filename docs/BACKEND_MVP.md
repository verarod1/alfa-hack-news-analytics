# Backend перед интеграцией ML

Текущая ветка: codex/backend-mvp. Код оставлен локально. Рабочие CSV, .env,
Frontend и рабочая PostgreSQL не изменялись; были только read-only SELECT для проверки.

## Реализовано без модели

12 маршрутов `/api/v1`: профиль/связи компании, demo-profiles, roles, news, feed,
создание/получение анализа, trace, чат/история, my-analyses. Архитектура сохраняется:
Router → Service → Repository → PostgreSQL, psycopg, Pydantic, без ORM.

Основной контекст — только CLIENT из DEMO_COMPANY_IDS. Подтверждён U_81 в CSV и
рабочей БД read-only запросом. `X-Company-ID` выбирает компанию из разрешённого
демо-набора; без заголовка используется первая. Анализ, trace и сообщения другой
компании недоступны. Это демонстрационная граница, не авторизация личности в банке.
PROSPECT/CLOSE_CLIENT остаются в raw_* и могут появляться как контрагенты.

Выручка: RUB/2025, значение 1000 → null. Продукты/ФТС распознают 0.0/1.0.
key_owner_flag означает наличие у банка достоверных сведений, а не существование
собственника или риск. Представление 1→true/0→false реализовано как явное соглашение
API; это ещё нужно подтвердить командой/организаторами. Платежи — RUB, не закупки
и не выручка; self-payments исключены из списка контрагентов. Период «с 1 января»:
год/конечная дата не установлены. GROUP_ID не даёт прав доступа ко всей группе.

Связи выбираются с SQL-лимитом, профили контрагентов одним batch-запросом.
`limit` и `truncated` показывают неполноту результата; молча считать его полным нельзя.

## Вкладки макета

Из `/Users/mac/Downloads/analytics-desktop.html` взяты реальные названия и ключи:

| Вкладка | Параметр | SQL-условие |
| --- | --- | --- |
| Все | tab=all | Без дополнительного ограничения |
| Готовые | tab=ready | status=completed |
| В обработке | tab=processing | status IN (queued,running) |
| Требуют внимания | tab=attention | importance IN (important,critical) |

Последнее правило — минимальное соглашение для подтверждения командой: HTML
сейчас не содержит рабочей бизнес-логики attention, его код не изменялся.
Не добавлена выдуманная вкладка ошибок. Технический status=failed можно передать
отдельным фильтром. importance normal/important/critical/null хранится отдельно
от status. Значения важности backend не назначает; null не считается важным.

Параметры status/importance можно повторять и комбинировать с tab (AND):

```text
/api/v1/my-analyses?company_id=U_81&role=cfo&tab=attention&status=completed
/api/v1/my-analyses?company_id=U_81&role=cfo&status=queued&status=running
```

COUNT и страница берутся из одной repeatable-read snapshot. Возвращаются корректные
items/total/limit/offset. Чужой company_id относительно выбранного заголовка даёт 403.

## PostgreSQL

`backend/db/schema.sql` не менялся. Текущий `mvp.sql` создаёт прежние пять таблиц
и одну необходимую для ML-оценок: news_relevance (company_id,role,news_id,score,reasons,
method,method_version). Все новые SQL относятся только к новым сущностям.

В analyses добавлены importance, attempt_count и run_token. Шаги сохраняются по
попыткам, включая реальные этапы backend при ошибке. Старый run_token не может
завершить новую попытку. В сообщениях добавлены idempotency key, reply_to, response_status,
метаданные происхождения ответа. Для старой MVP-схемы подготовлен upgrade_mvp_v2.sql;
рабочая база его не получала. Старые completed DTO требуют отдельной проверки.

## ML и обработчик

Подробный вход/выход: [ML_INTEGRATION.md](ML_INTEGRATION.md).
ML_ADAPTER_MODULE пустой по умолчанию. Результат не симулируется: POST сохраняет queued,
чат сохраняет вопрос и возвращает 503. В каждой порции аналитики есть дисклеймер.

```sh
python backend/scripts/process_analyses.py --limit 5
python backend/scripts/process_analyses.py --analysis-id ANALYSIS_ID
python backend/scripts/process_analyses.py --analysis-id ANALYSIS_ID --retry --company-id U_81
```

Обработчик конечный, без автозапуска daemon. Адаптер вызывается отдельным процессом
с timeout; queued → running → completed/failed, ошибка — безопасный code.
Явный retry разрешён failed/просроченной running, в пределах MAX_ANALYSIS_ATTEMPTS.
ANALYSIS_LEASE_SECONDS выбирайте с запасом к длительности подготовки и LLM_TIMEOUT_SECONDS.

ML может передать RelevanceAssessment через результат или внутренний save_relevance.
Она хранится по компании/роли/новости; SQL сортирует score до пагинации.
Без оценок ranking_mode=chronological, score=null; алгоритм релевантности не реализован.

Источники проверяются по серверной новости и локальному манифесту bank_materials;
проверяются документ/страница/цитата и company_factors. Факты, интерпретации, гипотезы
разделены statements/statement_type. Происхождение подтверждается, но смысловую
истинность каждого предложения без ML/экспертной проверки backend не доказывает.
Свободный текст чата — AI-ответ; официальная позиция берётся только из bank_opinion.

Для повторов чата передавайте одинаковый Idempotency-Key и тот же текст. После 503
не создаётся повторный вопрос при повторении с этим ключом. После успешного ответа
возвращается сохранённый ответ, не запускается новый вызов. Одновременный повтор — 409.
После аварии API повтор с тем же ключом может забрать просроченную попытку через
ANALYSIS_LEASE_SECONDS; старый response_token не может сохранить запоздалый ответ.
До истечения lease повтор получает 409; lease должен превышать максимальное время обработки. У процесса адаптера есть собственный deadline,
который действует и при аварии родительского API/worker.

## Проверки

```sh
python -B -m unittest discover -s backend/tests -v
POSTGRES_TEST_BIN=/opt/homebrew/opt/postgresql@16/bin python -B backend/scripts/run_integration_tests.py
```

Первый запуск: 10 unit/mock-проверок, 8 интеграционных пропущены без явного изолированного
окружения. Второй создаёт отдельный временный PostgreSQL, без TCP и Docker volumes,
проверяет имя БД/data_directory, применяет SQL и выполняет 8 интеграционных сценариев.
Временные ресурсы удаляются после остановки. Нужны initdb/pg_ctl PostgreSQL 16 и
непривилегированный пользователь ОС; можно задать POSTGRES_TEST_BIN для Linux/macOS.

На настоящей временной БД проверены: SQL, FK, дедупликация, CLIENT/scope, importance/status,
пагинация, CLI-worker, процессы адаптера/timeout, failed/retry/token, чат/idempotency,
реальный rollback --replace и advisory lock двух импортёров. Использовался явно
синтетический ml_test_adapter, не бизнес-модель; production его подключать нельзя.

Отдельно в изолированную БД загружен полный локальный набор: 85 525 компаний,
1 380 585 платежей, 12 514 связей. Импорт около 8.95 с. Одиночные локальные запросы:
профиль ~8.6 мс, связи limit=200 ~19.7 мс, demo-profiles ~4.1 мс. Это наблюдения
одного прогона, не нагрузочный benchmark. План профиля использует idx_companies_u.

## Что остаётся команде

- ML-разработчице: подключить адаптер/RAG/оценку релевантности и реальные материалы.
- Подтвердить rule attention, кодировку owner, семантику шкал importance/impact/confidence.
- Frontend: поддержать X-Company-ID, tab, repeated filters, дисклеймер, происхождение,
  ranking_mode, truncated и корректные статусы. HTML не изменялся; фраза о приватности
  личного профиля не должна считаться реальной пользовательской авторизацией.
- Оператору: после разрешения применить схемы к выбранной БД; новые таблицы в рабочей
  alfa_news пока не созданы. Проверить приватность GitHub/доступ жюри до публикации.
- Парсинг внешних новостей, платные API и собственный ML намеренно не реализованы.
