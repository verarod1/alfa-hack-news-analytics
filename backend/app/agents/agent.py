"""Совместимый вход ML-агента. HTTP и очередь используют analysis_service.

Новость должна уже существовать в PostgreSQL. Не запускается при импорте модуля.
"""
from app.services.profiler import build_company_profile
from app.services.news_service import get_news
from app.services.relation_service import get_relations
from app.services.evidence_service import bank_materials
from app.services.profile_service import validate_role
from app.schemas.ml import AnalysisContext
from team_ml.adapter import analyze


def run_analysis(company_id: str, role: str, news: dict) -> dict:
    validate_role(role)
    context = AnalysisContext(
        analysis_id="standalone", role=role, company=build_company_profile(company_id),
        news=get_news(news["id"]), relations=get_relations(company_id),
        bank_materials=bank_materials(),
    )
    # Ошибка не маскируется status=completed; вызывающий код должен её обработать.
    result = analyze(context.model_dump(mode="json"))
    return {"status": "completed", "result": result["result"], "trace": result["steps"]}
