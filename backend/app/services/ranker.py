import json
from app.services.llm_client import call_llm, _extract_json
from app.schemas.news import RelevanceAssessment
from app.repositories import news_repository

def rank_news(company_profile: dict, role: str, news: dict) -> dict | None:
    """
    Оценивает релевантность одной новости для компании и роли.
    Сохраняет оценку в БД через репозиторий бэкенда.
    """
    system_prompt = """Ты — аналитик Альфа-Банка. Оцени релевантность новости для компании.
Ответ ТОЛЬКО JSON:
{
  "relevance_score": 0.85,
  "relevance_reasons": ["Причина 1", "Причина 2"]
}
Оценка от 0.0 до 1.0. Учитывай отрасль, регион, банковские продукты и роль (ceo = стратегия/риски, cfo = деньги/налоги/кредиты)."""

    prompt = f"""
Компания: {company_profile.get('industry', {}).get('name', 'неизвестно')}
Регион: {company_profile.get('region', 'неизвестно')}
Продукты банка: {json.dumps(company_profile.get('bank_products', {}), ensure_ascii=False)}
Роль: {role}

Новость: {news['title']}
Текст: {news.get('text', '')}
"""

    raw = call_llm("rank", prompt, system_prompt, force_json=True)

    try:
        data = json.loads(_extract_json(raw))

        assessment = RelevanceAssessment(
            company_id=company_profile["id"],
            role=role,
            news_id=news["id"],
            relevance_score=float(data.get("relevance_score", 0.5)),
            relevance_reasons=data.get("relevance_reasons", ["Совпадение по отрасли"]),
            method="llm_ranker_glm",
            method_version="1.0"
        )

        # Сохранение в news_relevance (бэкенд сам подхватит для /feed)
        news_repository.save_relevance(assessment)
        print(f" [RANK] Новость {news['id']} -> Оценка: {assessment.relevance_score:.2f}")
        return assessment.model_dump()

    except Exception as e:
        print(f" Ranker error для {news.get('id')}: {e}")
        return None