"""Добавляет только явно синтетические новости. Не применять к рабочей БД без согласования."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg
from app.database import DatabaseConfigError
from app.schemas.news import NewsInput
from app.services.news_service import save_news
from app.services.errors import ServiceError

DEMO_NEWS = [
    {"id": "demo_news_001", "title": "[ТЕСТ] Учебный сценарий изменения условий кредитования",
     "text": "Синтетический пример для проверки сервиса: предприятие рассматривает изменение условий финансирования. Не является реальной публикацией.",
     "published_at": "2026-10-20T12:00:00+03:00"},
    {"id": "demo_news_002", "title": "[ТЕСТ] Учебный сценарий роста стоимости логистики",
     "text": "Синтетический пример для проверки сервиса: в условном сценарии меняется стоимость доставки товаров. Не является реальной публикацией.",
     "published_at": "2026-10-21T12:00:00+03:00"},
    {"id": "demo_news_003", "title": "[ТЕСТ] Учебный сценарий обновления оборудования",
     "text": "Синтетический пример для проверки сервиса: компания изучает возможность обновления производственного оборудования. Не является реальной публикацией.",
     "published_at": "2026-10-22T12:00:00+03:00"},
]


def main():
    try:
        for item in DEMO_NEWS:
            news = NewsInput(**item, source_id="demo_local", source_name="Локальные синтетические данные",
                             source_url=None, is_synthetic=True)
            saved = save_news(news)
            print(f"Доступна демонстрационная новость: {saved.id}")
    except (psycopg.Error, DatabaseConfigError, ServiceError):
        print("Не удалось сохранить демонстрационные новости. Проверьте подключение и схему БД.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
