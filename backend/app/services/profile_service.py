from app.services.client_context import require_demo_company
from app.settings import Settings
from app.services.errors import ServiceError

ROLES = (
    {"code": "ceo", "name": "Генеральный директор"},
    {"code": "cfo", "name": "Финансовый директор"},
)


def validate_role(role):
    if role not in {item["code"] for item in ROLES}:
        raise ServiceError(422, "VALIDATION_ERROR", "Неизвестная роль")


def get_demo_profiles():
    items = []
    for company_id in Settings().company_ids():
        try:
            company = require_demo_company(company_id)
        except ServiceError as error:
            if error.status_code in (403, 404, 409):
                continue
            raise
        for role in ROLES:
            items.append(
                {
                    "company_id": company.id,
                    "company_name": company.company_name,
                    "role": role["code"],
                    "role_name": role["name"],
                }
            )
    return {"items": items}
