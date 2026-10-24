from uuid import uuid4
from app.settings import Settings
from app.repositories import chat_repository as repository
from app.schemas.chat import AgentChatReply, ChatMessage
from app.schemas.analysis import AnalysisResult
from app.services.analysis_service import require_analysis
from app.services.company_service import require_client_company
from app.services.news_service import get_news
from app.services.relation_service import get_relations
from app.services.evidence_service import (
    bank_materials,
    verify_sources,
    verify_bank_opinion,
)
from app.services.errors import ServiceError
from app.services import ml_gateway


def send_message(request, company_id, request_key=None):
    analysis = require_analysis(request.analysis_id, company_id)
    company = require_client_company(company_id)
    news = get_news(analysis["news_id"])
    try:
        saved = repository.save_user_message(
            request.analysis_id, request.conversation_id, request.message, request_key
        )
    except ValueError:
        raise ServiceError(
            409, "IDEMPOTENCY_CONFLICT", "Ключ уже использован для другого сообщения"
        ) from None
    if saved is None:
        raise ServiceError(
            404, "CONVERSATION_NOT_FOUND", "Диалог не найден для этого анализа"
        )
    existing = repository.get_reply(saved["message_id"])
    if existing:
        return {
            "conversation_id": saved["conversation_id"],
            "message_id": existing["id"],
            "answer": existing["content"],
            "evidence_ids": existing["evidence_ids"],
            "status": "completed",
            **existing["metadata"],
        }
    details = [
        {"field": "conversation_id", "value": saved["conversation_id"]},
        {"field": "message_id", "value": saved["message_id"]},
    ]
    if not ml_gateway.configured():
        raise ServiceError(
            503, "ML_UNAVAILABLE", "Вопрос сохранён; ML-модуль не подключён", details
        )
    if analysis["status"] != "completed":
        raise ServiceError(
            409,
            "ANALYSIS_NOT_COMPLETED",
            "Вопрос сохранён; анализ ещё не завершён",
            details,
        )
    token = uuid4().hex
    if not repository.claim_message(
        saved["message_id"], token, Settings().analysis_lease_seconds
    ):
        raise ServiceError(
            409, "MESSAGE_IN_PROGRESS", "Ответ уже обрабатывается", details
        )
    try:
        result = AnalysisResult.model_validate(analysis["result"])
        documents = bank_materials()
        verify_sources(result.sources, news, documents)
        _, total = repository.list_messages(request.analysis_id, 1, 0)
        history, _ = repository.list_messages(
            request.analysis_id, 50, max(total - 50, 0)
        )
        context = {
            "analysis_id": request.analysis_id,
            "role": analysis["role"],
            "company": company.model_dump(mode="json"),
            "news": news.model_dump(mode="json"),
            "relations": get_relations(company_id),
            "bank_materials": [item.model_dump(mode="json") for item in documents],
            "result": result.model_dump(mode="json"),
            "message": request.message,
            "history": [
                ChatMessage.model_validate(item).model_dump(mode="json")
                for item in history
            ],
        }
        # Relations содержат Pydantic-совместимые словари, преобразуем весь контекст в JSON.
        from fastapi.encoders import jsonable_encoder

        reply = AgentChatReply.model_validate(
            ml_gateway.chat(jsonable_encoder(context))
        )
        known = {source.id for source in result.sources}
        if not set(reply.evidence_ids) <= known:
            raise ValueError("Ответ ссылается на неизвестный источник")
        verify_bank_opinion(reply.bank_opinion, result.sources)
        if reply.bank_opinion and not set(reply.bank_opinion.evidence_ids) <= set(
            reply.evidence_ids
        ):
            raise ValueError("Позиция банка не включена в источники ответа")
        message_id = repository.save_assistant_message(
            saved["conversation_id"], saved["message_id"], token, reply
        )
    except Exception as error:
        repository.fail_message(saved["message_id"], token)
        code = error.code if isinstance(error, ServiceError) else "ML_CHAT_INVALID"
        raise ServiceError(
            error.status_code if isinstance(error, ServiceError) else 502,
            code,
            "Не удалось получить проверенный ответ; вопрос сохранён",
            details,
        ) from None
    return {
        "conversation_id": saved["conversation_id"],
        "message_id": message_id,
        "answer": reply.answer,
        "evidence_ids": reply.evidence_ids,
        "statement_type": reply.statement_type,
        "bank_opinion": reply.bank_opinion,
        "status": "completed",
    }


def get_messages(analysis_id, company_id, limit, offset):
    require_analysis(analysis_id, company_id)
    items, total = repository.list_messages(analysis_id, limit, offset)
    return {
        "analysis_id": analysis_id,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
