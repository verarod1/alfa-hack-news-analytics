from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.company import CompanyResponse
from app.schemas.news import NewsResponse, RelevanceAssessment, NewsInput
from app.schemas.relation import RelationsResponse
from app.schemas.profile import RoleCode
from app.schemas.analysis import AnalysisResult, TraceStep


class BankPage(BaseModel):
    page: int = Field(ge=1)
    text: str = Field(min_length=1)


class BankDocument(BaseModel):
    document_id: str = Field(min_length=1)
    title: str
    url: str | None = None
    pages: list[BankPage]

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return NewsInput.http_url(value)


class AnalysisContext(BaseModel):
    analysis_id: str
    role: RoleCode
    company: CompanyResponse
    news: NewsResponse
    relations: RelationsResponse
    bank_materials: list[BankDocument] = Field(default_factory=list)


class AgentAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: AnalysisResult
    steps: list[TraceStep] = Field(default_factory=list)
    relevance: RelevanceAssessment | None = None
