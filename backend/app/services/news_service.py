import hashlib
import json
from datetime import timezone
from app.repositories import news_repository
from app.schemas.news import NewsInput, NewsResponse
from app.services.company_service import require_client_company
from app.services.profile_service import validate_role
from app.services.errors import ServiceError


def news_response(row):
    return NewsResponse.model_validate(
        {
            "id": row["id"],
            "title": row["title"],
            "text": row["text"],
            "published_at": row["published_at"],
            "created_at": row["created_at"],
            "source": {
                "id": row["source_id"],
                "name": row["source_name"],
                "url": row["source_url"],
            },
            "is_synthetic": row["is_synthetic"],
        }
    )


def save_news(value: NewsInput):
    values = value.model_dump()
    values["id"] = values["id"].strip()
    values["title"] = values["title"].strip()
    if not values["id"] or not values["title"]:
        raise ServiceError(
            422, "VALIDATION_ERROR", "ID и заголовок новости не могут быть пустыми"
        )
    # Хеш точного содержимого и метаданных, без ID; не семантическая дедупликация.
    canonical = {key: item for key, item in values.items() if key != "id"}
    if value.published_at is not None:
        canonical["published_at"] = value.published_at.astimezone(
            timezone.utc
        ).isoformat()
    values["content_hash"] = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    rows = news_repository.save_news(values)
    # ID уже занят другим содержимым: не перезаписываем существующую новость.
    if any(
        row["id"] == values["id"] and row["content_hash"] != values["content_hash"]
        for row in rows
    ):
        raise ServiceError(
            409, "NEWS_CONFLICT", "ID новости уже занят другим содержимым"
        )
    saved = next(
        (row for row in rows if row["content_hash"] == values["content_hash"]), None
    )
    if saved is None:
        raise ServiceError(
            409, "NEWS_CONFLICT", "Не удалось сохранить новость без конфликта"
        )
    return news_response(saved)


def get_news(news_id):
    row = news_repository.get_news(news_id)
    if row is None:
        raise ServiceError(404, "NEWS_NOT_FOUND", "Новость не найдена")
    return news_response(row)


def get_feed(company_id, role, impact_type, limit, offset):
    require_client_company(company_id)
    validate_role(role)
    rows, total, scored = news_repository.get_feed(
        company_id, role, impact_type, limit, offset
    )
    items = []
    for row in rows:
        news = news_response(row)
        result = row.get("result") or {}
        items.append(
            {
                "id": news.id,
                "title": news.title,
                "published_at": news.published_at,
                "source": news.source,
                "is_synthetic": news.is_synthetic,
                "relevance_score": row.get("score"),
                "impact_type": result.get("impact_type"),
                "impact_level": result.get("impact_level"),
                "short_insight": result.get("why_important"),
                "relevance_reasons": row.get("reasons") or [],
                "analysis_id": row.get("analysis_id"),
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "ranking_mode": "relevance" if scored else "chronological",
        "scored_total": scored,
    }


def save_relevance(value):
    from app.schemas.news import RelevanceAssessment

    assessment = RelevanceAssessment.model_validate(value)
    require_client_company(assessment.company_id)
    validate_role(assessment.role)
    get_news(assessment.news_id)
    news_repository.save_relevance(assessment)
    return assessment
