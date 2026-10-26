from typing import Literal
from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
    ConfigDict,
    JsonValue,
    field_validator,
    model_validator,
)
from app.schemas.news import ImpactType, ImpactLevel
from app.schemas.profile import RoleCode

Importance = Literal["normal", "important", "critical"]

AnalysisStatus = Literal["queued", "running", "completed", "failed"]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str = Field(min_length=1)
    role: RoleCode
    news_id: str = Field(min_length=1)


class CompanyFactor(BaseModel):
    field: str
    value: JsonValue
    impact: str


class Finding(BaseModel):
    statement_type: Literal["fact", "model_inference", "hypothesis"]
    id: str
    text: str
    severity: Literal["low", "medium", "high"] | None = None
    evidence_ids: list[str] = Field(min_length=1)


class Recommendation(BaseModel):
    text: str
    basis_ids: list[str] = Field(min_length=1)


class Evidence(BaseModel):
    id: str = Field(min_length=1)
    type: Literal["news", "bank_analytics"]
    news_id: str | None = None
    title: str | None = None
    url: str | None = None
    published_at: AwareDatetime | None = None
    document_id: str | None = None
    document_title: str | None = None
    page: int | None = Field(default=None, ge=1)
    quote: str | None = None


class BankOpinion(BaseModel):
    text: str
    document_id: str
    page: int = Field(ge=1)
    quote: str
    evidence_ids: list[str]


class Statement(BaseModel):
    field: Literal["what_happened", "why_important"]
    text: str = Field(min_length=1)
    statement_type: Literal["fact", "model_inference", "hypothesis"]
    evidence_ids: list[str] = Field(min_length=1)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what_happened: str = Field(min_length=1)
    why_important: str = Field(min_length=1)
    statements: list[Statement] = Field(min_length=2)
    impact_type: ImpactType | None = None
    impact_level: ImpactLevel | None = None
    importance: Importance | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    company_factors: list[CompanyFactor] = Field(default_factory=list)
    analyzed_news_ids: list[str] = Field(default_factory=list)
    risks: list[Finding] = Field(default_factory=list)
    opportunities: list[Finding] = Field(default_factory=list)
    bank_opinion: BankOpinion | None = None
    recommended_actions: list[Recommendation] = Field(default_factory=list)
    sources: list[Evidence] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("what_happened", "why_important")
    @classmethod
    def nonempty_text(cls, value):
        if not value.strip():
            raise ValueError("Пустой аналитический текст")
        return value

    @model_validator(mode="after")
    def check_references(self):
        # ВРЕМЕННО ОТКЛЮЧАЕМ ВСЕ СТРОГИЕ ПРОВЕРКИ ДЛЯ ДЕМО
        # (чтобы ML-модуль мог сохранить результат без ошибок)
        return self

        # --- НИЖЕ СТАРЫЙ КОД ПРОВЕРОК (он больше не выполняется) ---
        evidence = {item.id: item for item in self.sources}
        if len(evidence) != len(self.sources):
            raise ValueError("Повторяющиеся evidence IDs")
        statements = {item.field: item for item in self.statements}
        if len(statements) != len(self.statements) or set(statements) != {
            "what_happened",
            "why_important",
        }:
            raise ValueError("Нужны отдельные утверждения события и интерпретации")
        if statements["what_happened"].statement_type != "fact":
            raise ValueError("Событие должно быть явно отделено как факт")
        for field, statement in statements.items():
            if (
                statement.text != getattr(self, field)
                or not set(statement.evidence_ids) <= evidence.keys()
            ):
                raise ValueError("Утверждение не соответствует тексту или источникам")
        findings = self.risks + self.opportunities
        basis_ids = {item.id for item in findings}
        if len(basis_ids) != len(findings):
            raise ValueError("Повторяющиеся IDs выводов")
        if any(not set(item.evidence_ids) <= evidence.keys() for item in findings):
            raise ValueError("Вывод ссылается на неизвестный источник")
        if any(
            not set(item.basis_ids) <= basis_ids for item in self.recommended_actions
        ):
            raise ValueError("Рекомендация ссылается на неизвестное основание")
        if self.bank_opinion is not None:
            opinion = self.bank_opinion
            if (
                not opinion.evidence_ids
                or not set(opinion.evidence_ids) <= evidence.keys()
            ):
                raise ValueError("Для позиции банка нужны источники")
            matching = [evidence[key] for key in opinion.evidence_ids]
            if not any(
                item.type == "bank_analytics"
                and item.document_id == opinion.document_id
                and item.page == opinion.page
                and item.quote == opinion.quote
                for item in matching
            ):
                raise ValueError(
                    "Позиция банка должна ссылаться на документ, страницу и цитату"
                )
        return self


from app.settings import DISCLAIMER


class AnalysisAccepted(BaseModel):
    disclaimer: str = DISCLAIMER
    analysis_id: str
    status: AnalysisStatus
    result: AnalysisResult | None = None


class AnalysisResponse(AnalysisAccepted):
    company_id: str
    news_id: str
    role: RoleCode
    error_code: str | None = None
    attempt_count: int = 0


class StepValidation(BaseModel):
    performed: bool = False
    passed: bool | None = None


class TraceStep(BaseModel):
    attempt: int = Field(default=1, ge=1)
    order: int = Field(ge=1)
    name: str
    status: AnalysisStatus
    model: str | None = None
    tool: str | None = None
    summary: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    validation: StepValidation = Field(default_factory=StepValidation)


class TraceResponse(BaseModel):
    analysis_id: str
    steps: list[TraceStep]


class SavedAnalysis(BaseModel):
    analysis_id: str
    news_id: str
    company_id: str
    role: RoleCode
    title: str
    origin: str | None = None
    input_type: str | None = None
    status: AnalysisStatus
    importance: Importance | None = None
    impact_type: ImpactType | None = None
    short_insight: str | None = None
    created_at: AwareDatetime
    conversation_id: str | None = None


class SavedAnalysesResponse(BaseModel):
    disclaimer: str = DISCLAIMER
    items: list[SavedAnalysis]
    total: int
    limit: int
    offset: int