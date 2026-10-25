"""Явное ограниченное ранжирование. Может обращаться к платному LLM, не запускается автоматически."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import ml_gateway, news_service
from app.services.client_context import require_demo_company
from app.services.profile_service import validate_role
from app.repositories.news_repository import list_news
from app.schemas.news import RelevanceAssessment


def rank_batch(company_id, role, limit):
    if not 1 <= limit <= 20:
        raise ValueError("limit: 1..20")
    company = require_demo_company(company_id)
    validate_role(role)
    rows, _ = list_news(limit, 0)
    saved, errors = [], []
    for row in rows:
        news = news_service.news_response(row)
        try:
            context = {"company": company.model_dump(mode="json"), "role": role,
                       "news": news.model_dump(mode="json")}
            value = RelevanceAssessment.model_validate(ml_gateway.rank(context))
            if (value.company_id, value.role, value.news_id) != (company_id, role, news.id):
                raise ValueError("Ранкер изменил контекст")
            news_service.save_relevance(value)
            saved.append(news.id)
        except Exception:
            # Без сырого ответа провайдера, секретов и фиктивных оценок.
            errors.append(news.id)
    return {"saved": saved, "failed": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--role", choices=["ceo", "cfo"], required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("--limit: 1..20")
    try:
        result = rank_batch(args.company_id, args.role, args.limit)
        print(json.dumps(result, ensure_ascii=False))
        return int(bool(result["failed"]))
    except Exception:
        print("Проверьте ML-конфигурацию, компанию и PostgreSQL.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
