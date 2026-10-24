from typing import Literal
from pydantic import BaseModel

RoleCode = Literal["ceo", "cfo"]


class Role(BaseModel):
    code: RoleCode
    name: str


class RolesResponse(BaseModel):
    items: list[Role]


class DemoProfile(BaseModel):
    company_id: str
    company_name: str
    role: RoleCode
    role_name: str


class DemoProfilesResponse(BaseModel):
    items: list[DemoProfile]
