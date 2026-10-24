from pydantic import BaseModel, Field, FiniteFloat
from typing import Literal


class Industry(BaseModel):
    code: str | None = None
    name: str | None = None


class Revenue(BaseModel):
    value: FiniteFloat | None = None
    unit: Literal["RUB"] = "RUB"
    year: Literal[2025] = 2025


class ForeignTrade(BaseModel):
    has_data: bool | None = None
    countries: list[str] = Field(default_factory=list)


class BankProducts(BaseModel):
    rko: bool | None = None
    guarantee: bool | None = None
    loan: bool | None = None
    leasing: bool | None = None
    deposit: bool | None = None
    payroll: bool | None = None
    factoring: bool | None = None


class CompanyResponse(BaseModel):
    id: str
    company_name: str
    industry: Industry

    region: str | None = None
    city: str | None = None

    age_range: str | None = None
    employees_range: str | None = None
    business_stage: str | None = None
    client_type: Literal["CLIENT", "PROSPECT", "CLOSE_CLIENT"] | None = None

    revenue: Revenue
    foreign_trade: ForeignTrade
    bank_products: BankProducts

    group_id: str | None = None
    organization_type: str | None = None
    ownership_form: str | None = None
    key_owner_flag: bool | None = None
    employees_spark_range: str | None = None
