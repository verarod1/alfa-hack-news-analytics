from fastapi import Header
from app.settings import Settings
from app.services.company_service import require_client_company
from app.services.errors import ServiceError


def require_demo_company(company_id):
    if company_id not in Settings().company_ids():
        raise ServiceError(
            403,
            "COMPANY_ACCESS_DENIED",
            "Компания не входит в разрешённый демо-контекст",
        )
    return require_client_company(company_id)


def selected_company(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID")
):
    """Явный демо-контекст. Это не авторизация пользователя интернет-банка."""
    allowed = Settings().company_ids()
    if not allowed:
        raise ServiceError(
            503, "DEMO_NOT_CONFIGURED", "Не настроены демонстрационные компании"
        )
    company_id = x_company_id or allowed[0]
    require_demo_company(company_id)
    return company_id


def check_company_scope(company_id, selected_id):
    if company_id != selected_id:
        raise ServiceError(
            403, "COMPANY_ACCESS_DENIED", "Запрос относится к другой выбранной компании"
        )
