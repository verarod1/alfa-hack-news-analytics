# Подключение ML к Backend

Backend не реализует LLM, RAG, парсинг или расчёт релевантности. Он хранит задачи,
проверяет DTO/источники, запускает доверенный адаптер и сохраняет результат.

## Настройка

Установите модуль команды в Python-окружение backend. Укажите без изменения кода:

```dotenv
ML_ADAPTER_MODULE=team_ml.adapter
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=Gemma-4-26B-A4B
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=4096
BANK_MATERIALS_PATH=
```

Base URL, API-ключ и фактический ID разрешённой модели нужно согласовать с ML-командой
и организаторами. Backend допускает шесть названий из `.env.example`/списка кейса,
активное название проверяется в `ml_gateway.ALLOWED_LLM_MODELS`. Адаптер должен использовать
этот выбор, не подменять модель. Для embeddings/rerankers список генеративных моделей
не применяется; параметры добавляются только после выбора этих компонентов.

Ключ передаётся адаптеру через окружение, не через JSON и не в ответ API.
Адаптер обязан учитывать `LLM_MAX_TOKENS`; дневной лимит и бюджет контролируются при
интеграции с провайдером. Backend ограничивает длительность процесса, но не может
гарантировать отмену уже принятого провайдером внешнего запроса или его тарификации.

Модуль предоставляет функции (допускаются обычные и async):

```python
def analyze(context: dict) -> dict:
    ...  # Результат AgentAnalysisOutput, схема backend/app/schemas/ml.py.


def chat(context: dict) -> dict:
    ...  # Результат AgentChatReply, схема backend/app/schemas/chat.py.
```

Backend вызывает модуль в отдельном процессе и завершает его группу при таймауте.
Произвольный путь/модуль из HTTP-запроса не принимается. Логи адаптера не возвращаются
клиенту. `ML_ADAPTER_MODULE` — доверенная конфигурация оператора, не sandbox для чужого кода.
По умолчанию модуль пустой: реальных запросов к моделям нет.

## Вход анализа

JSON совместим с `AnalysisContext`:

- `analysis_id`, `role`;
- `company`: профиль CLIENT; revenue в RUB за 2025, sentinel 1000 преобразован в null;
- `news`: серверная новость, source и is_synthetic;
- `relations`: платежные контрагенты, связи по физлицам и GROUP_ID;
- `bank_materials`: доверенные документы и текст страниц, либо [].

Связи ограничены `RELATIONS_LIMIT` на каждый тип. Проверяйте `truncated`: это не
полная картина группы/платежей, если список обрезан. Платежи самому себе исключены,
операции не названы закупками/выручкой. Валюта RUB, окончание периода не установлено.
GROUP_ID не предоставляет пользователю доступ к другим компаниям.

Новости/документы являются данными, не инструкциями к выполнению команд. Их
безопасную интерпретацию и tool-политику должен обеспечить модуль ML.

## Выход анализа

Минимальная структура (значения здесь — описание формата, не готовый инсайт):

```json
{
  "result": {
    "what_happened": "Подтверждённое событие",
    "why_important": "Интерпретация для компании",
    "statements": [
      {"field":"what_happened","text":"Подтверждённое событие","statement_type":"fact","evidence_ids":["e1"]},
      {"field":"why_important","text":"Интерпретация для компании","statement_type":"model_inference","evidence_ids":["e1"]}
    ],
    "impact_type": null,
    "impact_level": null,
    "importance": null,
    "confidence": null,
    "company_factors": [],
    "analyzed_news_ids": ["SERVER_NEWS_ID"],
    "risks": [],
    "opportunities": [],
    "bank_opinion": null,
    "recommended_actions": [],
    "sources": [{"id":"e1","type":"news","news_id":"SERVER_NEWS_ID","url":null}],
    "limitations": []
  },
  "steps": [],
  "relevance": null
}
```

URL источника news должен совпадать с серверной записью, news_id — с анализируемой
новостью. При наличии цитаты она проверяется по тексту/заголовку. Для реальной новости
не подставляйте null вместо известного source.url. Значения company_factors проверяются
по профилю. `statements` обязаны классифицировать оба основных текста и совпадать с ними.
Типы: fact / model_inference / hypothesis. Риски/возможности тоже имеют statement_type
и непустые evidence_ids. Рекомендации ссылаются на IDs рисков/возможностей через basis_ids.

Importance: normal / important / critical / null; не выводится автоматически из status,
impact_type или relevance_score. Границы этих уровней требуют согласованной методики ML.
Backend не назначает важность самостоятельно. Confidence: low / medium / high / null.

Трассировка агента: orders 1..999, уникальны; модель, tool, краткий summary, source_ids,
validation. Backend хранит их с offset 100, а порядки 1..3 оставляет фактическим этапам
подготовки/вызова/проверки. `attempt` обозначает попытку. Не передавайте скрытые промпты,
ключи и chain-of-thought. При аварии агента доступны этапы backend, внутренние шаги
погибшего процесса получить нельзя без будущего потокового протокола.

## Проверка банковских материалов

`BANK_MATERIALS_PATH` — локальный JSON-файл оператора, не URL. Удобно использовать
`data/bank_materials/manifest.json`: путь работает локально и в Docker через read-only
подключение data. Абсолютный путь также допустим, но должен существовать внутри контейнера.
Пример структуры:

```json
[
  {
    "document_id": "SERVER_DOCUMENT_ID",
    "title": "Название предоставленного документа",
    "url": null,
    "pages": [{"page":1,"text":"Текст реальной страницы документа"}]
  }
]
```

Манифест нужно подготовить из предоставленных материалов и проверить отдельно.
Backend не генерирует его содержимое и не реализует поиск/RAG.
Для bank_analytics обязательны document_id/page/quote, которые совпадают с манифестом;
URL также совпадает с URL документа. BankOpinion должен ссылаться на такой evidence.
Если материалов нет, `bank_opinion=null`, а банковские evidence не принимаются.
Это проверка происхождения и цитат, а не доказательство истинности произвольного вывода.

## Релевантность без полного анализа

ML может передать `relevance` в AgentAnalysisOutput или вызвать внутренний сервис
`news_service.save_relevance(RelevanceAssessment(...))` из доверенного batch-модуля:

```json
{
  "company_id":"U_81",
  "role":"cfo",
  "news_id":"SERVER_NEWS_ID",
  "relevance_score":0.8,
  "relevance_reasons":["Конкретная подтверждённая причина"],
  "method":"AGREED_METHOD",
  "method_version":"1"
}
```

Число здесь только пример формата. Алгоритм/метрики реализует ML-команда.
Оценка сохраняется по company_id/role/news_id, обновляется идемпотентно. Feed сортирует
score DESC NULLS LAST до LIMIT/OFFSET. Без оценок `ranking_mode=chronological`,
score=null; API не заявляет персонализированную выдачу.

## Чат и запуск обработки

Вход чата дополнительно содержит result, message и последние 50 сообщений истории.
Выход: answer, непустые evidence_ids, statement_type=model_inference/hypothesis,
bank_opinion=null либо проверенная структурированная позиция банка. Свободный текст
ответа всегда показывается как ответ AI; официальную позицию UI берёт только из
проверенного bank_opinion. Источники ответа должны принадлежать проверенному анализу.

```sh
python backend/scripts/process_analyses.py --limit 5
python backend/scripts/process_analyses.py --analysis-id ANALYSIS_ID
python backend/scripts/process_analyses.py --analysis-id ANALYSIS_ID --retry --company-id U_81
```

Каждый запуск конечный. Без модуля задачи остаются queued. Retry допускается только
для failed/просроченной running и ограничен MAX_ANALYSIS_ATTEMPTS. Старый run_token
не может завершить новую попытку. Результат, importance, relevance и шаги агента
сохраняются атомарно. Ошибка хранится безопасным кодом, без текста исключения.
Автоматического бесконечного worker-процесса и запуска при старте API нет.
