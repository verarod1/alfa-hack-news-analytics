from fastapi import APIRouter, Query, Depends, Header
from app.schemas.chat import ChatRequest, ChatResponse, MessagesResponse
from app.services.chat_service import send_message, get_messages
from app.services.client_context import selected_company

router = APIRouter(prefix="/api/v1", tags=["Chat"])


@router.post("/chat/messages", response_model=ChatResponse)
def chat_message(
    request: ChatRequest,
    company_id: str = Depends(selected_company),
    request_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=100
    ),
):
    return send_message(request, company_id, request_key)


@router.get("/analyses/{analysis_id}/messages", response_model=MessagesResponse)
def messages(
    analysis_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    company_id: str = Depends(selected_company),
):
    return get_messages(analysis_id, company_id, limit, offset)
