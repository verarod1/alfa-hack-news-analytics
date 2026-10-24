from typing import Literal
from fastapi import APIRouter, Query, Depends, Header
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisAccepted,
    AnalysisResponse,
    TraceResponse,
    SavedAnalysesResponse,
    AnalysisStatus,
    Importance,
)
from app.schemas.profile import RoleCode
from app.services import analysis_service
from app.services.client_context import selected_company, check_company_scope

router = APIRouter(prefix="/api/v1", tags=["Analyses"])


@router.post("/analyses", status_code=202, response_model=AnalysisAccepted)
def create_analysis(
    request: AnalysisRequest,
    company_id: str = Depends(selected_company),
    request_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=100
    ),
):
    return analysis_service.create_analysis(request, company_id, request_key)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str, company_id: str = Depends(selected_company)):
    return analysis_service.get_analysis(analysis_id, company_id)


@router.get("/analyses/{analysis_id}/trace", response_model=TraceResponse)
def get_trace(analysis_id: str, company_id: str = Depends(selected_company)):
    return analysis_service.get_trace(analysis_id, company_id)


@router.get(
    "/my-analyses",
    response_model=SavedAnalysesResponse,
    description="Демо-контекст без пользовательской авторизации. importance и status независимы.",
)
def my_analyses(
    company_id: str = Query(min_length=1),
    role: RoleCode = Query(),
    search: str | None = Query(default=None, max_length=500),
    status: list[AnalysisStatus] | None = Query(default=None),
    importance: list[Importance] | None = Query(default=None),
    tab: Literal["all", "ready", "processing", "attention"] = "all",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context_company: str = Depends(selected_company),
):
    check_company_scope(company_id, context_company)
    return analysis_service.get_my_analyses(
        company_id, role, search, status, importance, tab, limit, offset
    )
