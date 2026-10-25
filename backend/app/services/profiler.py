"""Совместимость ML с единым профилем Backend: CSV повторно не загружается."""
from app.services.company_service import require_client_company


def build_company_profile(company_id: str) -> dict:
    return require_client_company(company_id).model_dump(mode="json")
