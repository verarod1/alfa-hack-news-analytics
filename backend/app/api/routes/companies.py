from fastapi import APIRouter, Depends, Query
from app.schemas.company import CompanyResponse
from app.schemas.relation import RelationsResponse
from app.services.company_service import require_client_company
from app.services.relation_service import get_relations
from app.services.client_context import selected_company, check_company_scope

router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: str, context_company: str = Depends(selected_company)):
    company = require_client_company(company_id)
    check_company_scope(company_id, context_company)
    return company


@router.get("/{company_id}/relations", response_model=RelationsResponse)
def company_relations(
    company_id: str,
    limit: int | None = Query(default=None, ge=1, le=500),
    context_company: str = Depends(selected_company),
):
    require_client_company(company_id)
    check_company_scope(company_id, context_company)
    return get_relations(company_id, limit)
