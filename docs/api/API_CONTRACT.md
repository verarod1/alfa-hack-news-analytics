# API Backend перед интеграцией ML

Источник JSON — согласование1.docx; правила данных дополнены официальными ответами
организаторов. Все 12 маршрутов сохранены. OpenAPI: `/openapi.json`, Swagger: `/docs`.

## Общие правила

ID — строки; неизвестное — null, списки — []; даты ISO 8601 с timezone.
`X-Company-ID` выбирает компанию из DEMO_COMPANY_IDS, первая используется по умолчанию.
Для персональных сценариев нужна CLIENT. Анализы/чаты другой выбранной компании → 403.
Это демо-контекст, не проверка прав конкретного человека в интернет-банке.

Ошибки имеют error.code/message/details и request_id, включая безопасные 500.
DB недоступна → 503; ML не подключён → 503; некорректный результат → 502;
ML timeout → 504. В ответах нет ключей, DSN, exception text или скрытых промптов.

## Маршруты

| Метод | Путь после /api/v1 | Поведение |
| --- | --- | --- |
| GET | /companies/{id} | CLIENT-профиль: 404 отсутствует, 403 другой контекст/не CLIENT, 409 противоречивые записи |
| GET | /companies/{id}/relations | Три типа связей, RUB, limit и truncated; SQL ограничен, профили batch |
| GET | /demo-profiles | Только существующие разрешённые CLIENT, по две роли |
| GET | /roles | ceo и cfo |
| GET | /news/{id} | Новость с source/датами/is_synthetic, 404 при отсутствии |
| GET | /feed | company_id, role, impact_type risk/opportunity, limit/offset |
| POST | /analyses | company_id, role, news_id, необязательный Idempotency-Key; 202 с analysis_id/queued/result=null/disclaimer |
| GET | /analyses/{id} | Статус, result/null, error_code, attempt_count, disclaimer |
| GET | /analyses/{id}/trace | analysis_id, steps с attempt/order/status и реальными этапами |
| POST | /chat/messages | analysis_id/conversation_id/message; необязательный Idempotency-Key |
| GET | /analyses/{id}/messages | История в контексте, items/total/limit/offset |
| GET | /my-analyses | company_id/role обязательны; search/status/importance/tab/limit/offset |

## Данные компаний

revenue.value — RUB за 2025; 1000→null, NaN/Infinity→null. revenue.year=2025.
key_owner_flag теперь bool|null: сведения банка о ключевом собственнике.
Преобразование 1→true/0→false — предлагаемое соглашение API, требующее подтверждения;
это не «негативный риск» и не утверждение об отсутствии владельца при false.
client_type сохраняет CLIENT/PROSPECT/CLOSE_CLIENT, но пользовательский сценарий только CLIENT.
Группа означает same_group_id, не автоматические права ко всем её участникам.
Платёжные суммы RUB, self-payments не входят в контрагентов, характер отношений не угадывается.

## Вкладки и фильтры

В HTML: «Все», «Готовые», «В обработке», «Требуют внимания».
API tab: all / ready / processing / attention.
Ready: completed; processing: queued/running; attention: important/critical.
Последнее — минимальное правило для подтверждения команды: HTML его не определяет.
Status и importance независимы, передаются отдельно, допускаются повторяющиеся query:
`status=queued&status=running`. Дополнительные фильтры объединяются через AND.
null importance не попадает в attention; failed сам по себе не означает внимание.

Пагинация 1<=limit<=100, offset>=0; COUNT и страница одной snapshot.
Importance: normal/important/critical/null; backend не назначает её без результата алгоритма.
Полные значения и смысл шкал требуется согласовать с ML/frontend; это не официальный enum организаторов.

## Feed и ML-результат

score/reasons поступают из ML, хранятся по company_id/role/news_id с методом/версией.
Сортировка score DESC NULLS LAST до LIMIT/OFFSET; без оценок ranking_mode=chronological,
relevance_score=null, relevance_reasons=[]. Дополнительно возвращается scored_total.
Impact-фильтр использует сохранённый completed-результат именно этой компании/роли.

Анализ содержит statements для what_happened/why_important с типами
fact/model_inference/hypothesis и непустыми evidence_ids; риски и возможности тоже
имеют statement_type. Источники проверяются по серверной новости и локальным документам.
BankOpinion принимается только с подтверждёнными document/page/quote. В чате свободный
answer — модельный вывод/гипотеза, официальная позиция — отдельный bank_opinion.
Во всех аналитических ответах disclaimer об отсутствии индивидуальной инвестрекомендации.
Эти расширения DTO документированы для подтверждения frontend/ML до интеграции.

## Чат и обработка

Без ML вопрос сохранён, затем 503; IDs есть в error.details. Одинаковые Idempotency-Key
и текст переиспользуют сообщение/ответ. Ключ с другим текстом → 409; параллельный ответ → 409.
История хранит evidence_ids и метаданные происхождения. Один диалог на анализ.

Обработка queued запускается ограниченным CLI, не автоматически бесконечным процессом.
Retry — только failed/просроченная running, с ограничением попыток и отзывом run_token.
Все новые таблицы/SQL подготовлены, но к рабочей БД не применялись.
