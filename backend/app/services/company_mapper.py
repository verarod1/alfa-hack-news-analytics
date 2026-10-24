from decimal import Decimal, InvalidOperation
import math


def normalize(value):
    """Преобразует пустые значения в None."""
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    return value


def to_number(value):
    """Преобразует число из CSV в float или None."""
    value = normalize(value)

    if value is None:
        return None

    try:
        number = float(Decimal(str(value).replace(",", ".")))
        return number if math.isfinite(number) else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def to_boolean(value):
    """Преобразует известные значения в bool."""
    value = normalize(value)

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    text = str(value).lower()

    if text in ("1", "1.0", "true"):
        return True

    if text in ("0", "0.0", "false"):
        return False

    return None


def map_company(raw: dict) -> dict:
    """Преобразует профиль компании в формат API."""

    company_id = normalize(raw.get("SYNTHETIC_U"))

    return {
        "id": company_id,
        "company_name": f"Компания {company_id}",
        "industry": {
            "code": normalize(raw.get("MAINOKVED_CODE")),
            "name": normalize(raw.get("MAINOKVED_NAME")),
        },
        "region": normalize(raw.get("REGION")),
        "city": normalize(raw.get("CITY")),
        "age_range": normalize(raw.get("COMPANY_AGE_YEARS_GRADATION")),
        "employees_range": normalize(raw.get("AMOUNT_WORKERS_FNS_GRADATION")),
        "business_stage": normalize(raw.get("ECO_MARK_LABEL")),
        "client_type": (
            normalize(raw.get("CL_TYPE"))
            if normalize(raw.get("CL_TYPE")) in {"CLIENT", "PROSPECT", "CLOSE_CLIENT"}
            else None
        ),
        "revenue": {
            "value": (
                None
                if to_number(raw.get("REVENUE_COMPANY")) == 1000
                else to_number(raw.get("REVENUE_COMPANY"))
            ),
            "unit": "RUB",
            "year": 2025,
        },
        "foreign_trade": {
            "has_data": to_boolean(raw.get("FTS_FLAG")),
            "countries": (
                [normalize(raw.get("FTS_COUNTRY_NAME"))]
                if normalize(raw.get("FTS_COUNTRY_NAME"))
                else []
            ),
        },
        "bank_products": {
            "rko": to_boolean(raw.get("CL_PRODUCT_RKO_MARK")),
            "guarantee": to_boolean(raw.get("CL_PRODUCT_GAR_MARK")),
            "loan": to_boolean(raw.get("CL_PRODUCT_LOA_MARK")),
            "leasing": to_boolean(raw.get("CL_PRODUCT_LEA_MARK")),
            "deposit": to_boolean(raw.get("CL_PRODUCT_DEP_MARK")),
            "payroll": to_boolean(raw.get("CL_PRODUCT_ZPP_MARK")),
            "factoring": to_boolean(raw.get("FACTORING_MARK")),
        },
        "group_id": normalize(raw.get("GROUP_ID")),
        "organization_type": normalize(raw.get("ORG_TYPE")),
        "ownership_form": normalize(raw.get("OKFS_NAME")),
        # Это наличие достоверных сведений у банка, а не риск или личность владельца.
        # Булева кодировка 1/0 — явное соглашение API, ожидающее подтверждения команды.
        "key_owner_flag": to_boolean(raw.get("NEGATIVEMARK")),
        "employees_spark_range": normalize(raw.get("AMOUNT_WORKERS_SPARK_GRADATION")),
    }
