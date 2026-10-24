from fastapi import APIRouter, Query, Depends
from typing import Literal
from app.schemas.news import NewsResponse, FeedResponse
from app.schemas.profile import RoleCode
from app.services.news_service import get_news, get_feed
from app.services.client_context import selected_company, check_company_scope

router = APIRouter(prefix="/api/v1", tags=["News"])


@router.get("/news/{news_id}", response_model=NewsResponse)
def news(news_id: str):
    return get_news(news_id)


@router.get("/feed", response_model=FeedResponse)
def feed(
    company_id: str = Query(min_length=1),
    role: RoleCode = Query(),
    impact_type: Literal["risk", "opportunity"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context_company: str = Depends(selected_company),
):
    check_company_scope(company_id, context_company)
    return get_feed(company_id, role, impact_type, limit, offset)
