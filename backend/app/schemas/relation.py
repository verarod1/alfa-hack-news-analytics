from typing import Literal
from pydantic import BaseModel, Field, FiniteFloat
from app.schemas.company import Industry


class CompanyBrief(BaseModel):
    id: str
    company_name: str
    industry: Industry
    region: str | None = None


class PaymentCounterparty(BaseModel):
    company: CompanyBrief
    direction: Literal["incoming", "outgoing"]
    payment_amount: FiniteFloat | None = None
    payment_count: int | None = None
    payment_currency: Literal["RUB"] = "RUB"


class SharedPersonLink(BaseModel):
    company: CompanyBrief
    shared_person_id: str


class GroupLink(BaseModel):
    company: CompanyBrief
    group_id: str
    relation_type: Literal["same_group_id"] = "same_group_id"


class Relations(BaseModel):
    payment_counterparties: list[PaymentCounterparty] = Field(default_factory=list)
    shared_person_links: list[SharedPersonLink] = Field(default_factory=list)
    group_links: list[GroupLink] = Field(default_factory=list)


class RelationsResponse(BaseModel):
    company_id: str
    relations: Relations
    limit: int
    truncated: dict[str, bool]
