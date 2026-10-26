from uuid import uuid4
from app.repositories import analysis_repository as repository
from app.schemas.ml import AnalysisContext, AgentAnalysisOutput
from app.schemas.relation import RelationsResponse
from app.services.company_service import require_client_company
from app.services.client_context import check_company_scope, require_demo_company
from app.services.news_service import get_news
from app.services.relation_service import get_relations
from app.services.profile_service import validate_role
from app.services.evidence_service import (
    bank_materials,
    verify_sources,
    verify_bank_opinion,
    verify_company_factors,
)
from app.services.errors import ServiceError
from app.services import ml_gateway
from app.settings import Settings


def require_analysis(analysis_id, company_id):
    row = repository.get_analysis(analysis_id)
    if row is None:
        raise ServiceError(404, "ANALYSIS_NOT_FOUND", "Анализ не найден")
    check_company_scope(row["company_id"], company_id)
    require_demo_company(company_id)
    return row


def create_analysis(request, company_id, request_key=None):
    check_company_scope(request.company_id, company_id)
    require_demo_company(company_id)
    validate_role(request.role)
    get_news(request.news_id)
    try:
        row = repository.create_analysis(
            "analysis_" + uuid4().hex,
            company_id,
            request.role,
            request.news_id,
            request_key,
        )
    except ValueError:
        raise ServiceError(
            409, "IDEMPOTENCY_CONFLICT", "Ключ уже использован для другой новости"
        ) from None
    return {"analysis_id": row["id"], "status": row["status"], "result": row["result"]}


def get_analysis(analysis_id, company_id):
    row = require_analysis(analysis_id, company_id)
    return {
        "analysis_id": row["id"],
        "status": row["status"],
        "company_id": row["company_id"],
        "news_id": row["news_id"],
        "role": row["role"],
        "result": row["result"],
        "error_code": row["error_code"],
        "attempt_count": row["attempt_count"],
    }


def get_trace(analysis_id, company_id):
    require_analysis(analysis_id, company_id)
    return {"analysis_id": analysis_id, "steps": repository.get_trace(analysis_id)}


def get_my_analyses(company_id, role, search, statuses, importance, tab, limit, offset):
    require_demo_company(company_id)
    validate_role(role)
    rows, total = repository.list_analyses(
        company_id, role, search, statuses, importance, tab, limit, offset
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def retry_analysis(analysis_id, company_id):
    require_analysis(analysis_id, company_id)
    settings = Settings()
    row = repository.retry_analysis(
        analysis_id, settings.analysis_lease_seconds, settings.max_analysis_attempts
    )
    if row is None:
        raise ServiceError(
            409,
            "RETRY_NOT_ALLOWED",
            "Повтор допускается только для failed/просроченной running в пределах лимита",
        )
    return get_analysis(analysis_id, company_id)


def process_analysis(analysis_id):
    original = repository.get_analysis(analysis_id)
    if original is None:
        raise ServiceError(404, "ANALYSIS_NOT_FOUND", "Анализ не найден")
    require_demo_company(original["company_id"])
    if not ml_gateway.configured():
        raise ServiceError(
            503, "ML_UNAVAILABLE", "Задача остаётся queued: ML-модуль ещё не подключён"
        )
    settings = Settings()
    token = uuid4().hex
    row = repository.claim_analysis(analysis_id, token, settings.max_analysis_attempts)
    if row is None:
        raise ServiceError(
            409,
            "ANALYSIS_STATE_CONFLICT",
            "Задача уже обрабатывается либо исчерпан лимит попыток",
        )
    phase = 1

    def step(order, name, status):
        repository.record_step(
            analysis_id,
            token,
            {
                "order": order,
                "name": name,
                "status": status,
                "tool": "backend",
                "source_ids": [],
                "validation": {"performed": False, "passed": None},
            },
        )

    try:
        step(1, "prepare_context", "running")
        context = AnalysisContext(
            analysis_id=analysis_id,
            role=row["role"],
            company=require_client_company(row["company_id"]),
            news=get_news(row["news_id"]),
            relations=RelationsResponse.model_validate(
                get_relations(row["company_id"])
            ),
            bank_materials=bank_materials(),
        )
        step(1, "prepare_context", "completed")
        phase = 2
        step(2, "ml_call", "running")
        output = AgentAnalysisOutput.model_validate(
            ml_gateway.analyze(context.model_dump(mode="json"))
        )
        step(2, "ml_call", "completed")
        phase = 3
        step(3, "validate_result", "running")
        if output.result.analyzed_news_ids != [row["news_id"]]:
            raise ValueError("Адаптер должен анализировать текущую новость")
        verify_sources(output.result.sources, context.news, context.bank_materials)
        verify_bank_opinion(output.result.bank_opinion, output.result.sources)
        verify_company_factors(output.result.company_factors, context.company)
        ids = {item.id for item in output.result.sources}
        orders = [item.order for item in output.steps]
        if len(set(orders)) != len(orders) or any(
            not 1 <= order <= 999 for order in orders
        ):
            raise ValueError("Некорректный порядок шагов агента")
        if any(not set(item.source_ids) <= ids for item in output.steps):
            raise ValueError("Неизвестный источник в трассировке")
        # Relevance относится к тому же контексту; сохраняется вместе с completed ниже.
        if output.relevance is not None:
            if (
                output.relevance.company_id,
                output.relevance.role,
                output.relevance.news_id,
            ) != (row["company_id"], row["role"], row["news_id"]):
                raise ValueError("Оценка относится к другому контексту")
        step(3, "validate_result", "completed")
        steps = [
            dict(item.model_dump(mode="json"), order=item.order + 100)
            for item in output.steps
        ]
        repository.complete_analysis(
            analysis_id,
            token,
            output.result.model_dump(mode="json"),
            steps,
            output.relevance,
        )
    except Exception as error:
        code = error.code if isinstance(error, ServiceError) else "ML_RESULT_INVALID"
        name = {1: "prepare_context", 2: "ml_call", 3: "validate_result"}[phase]
        step(phase, name, "failed")
        repository.fail_analysis(analysis_id, token, code)
        if isinstance(error, ServiceError):
            raise
        raise ServiceError(
            502, code, "Не удалось получить проверенный результат анализа"
        ) from None
    return get_analysis(analysis_id, row["company_id"])
