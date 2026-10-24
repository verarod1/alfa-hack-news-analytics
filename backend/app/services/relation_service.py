from app.repositories.company_repository import get_group_company_ids, get_companies_raw
from app.repositories.payment_repository import get_payment_counterparties
from app.repositories.person_link_repository import get_shared_person_links
from app.services.company_service import require_client_company
from app.services.company_mapper import to_number, map_company
from app.services.errors import ServiceError
from app.settings import Settings


def get_relations(company_id, limit=None):
    profile = require_client_company(company_id)
    limit = limit or Settings().relations_limit
    payments = get_payment_counterparties(company_id, limit + 1)
    people = get_shared_person_links(company_id, limit + 1)
    groups = (
        get_group_company_ids(company_id, profile.group_id, limit + 1)
        if profile.group_id
        else []
    )
    truncated = {
        "payment_counterparties": len(payments) > limit,
        "shared_person_links": len(people) > limit,
        "group_links": len(groups) > limit,
    }
    payments, people, groups = payments[:limit], people[:limit], groups[:limit]
    ids = {row["company_id"] for row in payments + people} | set(groups)
    raw = get_companies_raw(ids)
    summaries = {}
    for company in ids:
        rows = raw.get(company, [])
        if rows and any(row != rows[0] for row in rows[1:]):
            raise ServiceError(
                409, "COMPANY_CONFLICT", "Найдены разные записи контрагента"
            )
        mapped = (
            map_company(rows[0])
            if rows
            else {"industry": {"code": None, "name": None}, "region": None}
        )
        summaries[company] = {
            "id": company,
            "company_name": f"Компания {company}",
            "industry": mapped["industry"],
            "region": mapped["region"],
        }
    return {
        "company_id": company_id,
        "limit": limit,
        "truncated": truncated,
        "relations": {
            "payment_counterparties": [
                {
                    "company": summaries[row["company_id"]],
                    "direction": row["direction"],
                    "payment_amount": to_number(row["payment_amount"]),
                    "payment_count": row["payment_count"],
                    "payment_currency": "RUB",
                }
                for row in payments
            ],
            "shared_person_links": [
                {
                    "company": summaries[row["company_id"]],
                    "shared_person_id": row["shared_person_id"],
                }
                for row in people
            ],
            "group_links": [
                {
                    "company": summaries[other],
                    "group_id": profile.group_id,
                    "relation_type": "same_group_id",
                }
                for other in groups
            ],
        },
    }
