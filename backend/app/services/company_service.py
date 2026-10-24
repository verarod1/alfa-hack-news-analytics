from app.repositories.company_repository import get_company_raw
from app.schemas.company import CompanyResponse
from app.services.company_mapper import map_company
from app.services.errors import ServiceError


def get_company_profile(company_id: str):
    rows = get_company_raw(company_id)
    if not rows:
        raise ServiceError(404, "COMPANY_NOT_FOUND", "Компания не найдена")
    if any(row != rows[0] for row in rows[1:]):
        raise ServiceError(
            409, "COMPANY_CONFLICT", "Найдены разные записи одной компании"
        )
    return CompanyResponse.model_validate(map_company(rows[0]))


def require_client_company(company_id):
    company = get_company_profile(company_id)
    if company.client_type != "CLIENT":
        raise ServiceError(
            403,
            "CLIENT_REQUIRED",
            "Персональный сценарий доступен только действующим клиентам",
        )
    return company
