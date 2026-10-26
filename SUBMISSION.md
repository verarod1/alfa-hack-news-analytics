# Комплект сдачи

Репозиторий: https://github.com/verarod1/alfa-hack-news-analytics

Ветка с комплектом: `front/upd`. Последний зафиксированный commit до этой актуализации: `8790b73fdc11662e65489f77bb4c1ff45ac5fc67` (26.10.2026, 18:03:45 UTC+03:00). Изменения после него требуют нового commit; этот hash не следует выдавать за окончательную версию комплекта. В README указан явный переход на ветку с материалами.

## Материалы

- README.md: назначение, окружение, запуск, конфигурация, компоненты.
- compose.review.yml: воспроизводимый изолированный технический сценарий.
- docker-compose.yml: реальные данные, RSS и внешний ML.
- backend/requirements.lock, requirements.txt; frontend/package-lock.json: версии зависимостей.
- THIRD_PARTY_NOTICES.md: сторонние компоненты, модели, данные и имитации.
- backend/fixtures/review.sql: полностью синтетические компании, платежи, связи и новости.
- docs/ACCEPTANCE.md и backend/scripts/review_smoke.py: ручной и автоматический сценарии.
- docs/ARCHITECTURE.md, backend/db/*.sql, docs/api/API_CONTRACT.md; Swagger /docs и OpenAPI /openapi.json.
- .github/workflows/acceptance.yml: сборка и проверка на GitHub Actions.

## Финальная фиксация

После проверки и коммита всех сдаваемых изменений выполните `python scripts/submission_manifest.py`. Скрипт откажется выдавать commit для грязного checkout. Сохраните выданный JSON отдельно от checkout и приложите его к сдаче; отправьте соответствующий commit в GitHub. Для проверяющих укажите ссылку вида `https://github.com/verarod1/alfa-hack-news-analytics/tree/<полный-hash>` и время commit из manifest. Ветку `front/upd` укажите дополнительно для удобства навигации.

Дедлайн в запросе не указан; соблюдение времени сдачи и окончательный commit должны быть подтверждены командой. Для приватного репозитория предоставьте доступ GitHub-аккаунту `alfa-hack-2026` и проверьте принятие приглашения. Доступ жюри в этой сессии не проверен и не изменён. Ключи, .env и закрытые данные в комплект не входят.
