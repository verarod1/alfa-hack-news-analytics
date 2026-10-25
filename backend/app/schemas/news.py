from typing import Literal
from urllib.parse import urlsplit
from app.settings import DISCLAIMER
from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
    ConfigDict,
    field_validator,
    FiniteFloat,
    model_validator,
)

ImpactType = Literal["risk", "opportunity", "mixed", "neutral"]
ImpactLevel = Literal["low", "medium", "high", "unknown"]


class NewsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str | None = None
    published_at: AwareDatetime | None = None
    source_id: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    is_synthetic: bool

    @field_validator("source_url")
    @classmethod
    def http_url(cls, value):
        if value is not None:
            url = urlsplit(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
            ):
                raise ValueError("Источник должен иметь HTTP(S) URL без credentials")
        return value


class Source(BaseModel):
    id: str | None = None
    name: str | None = None
    url: str | None = None

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return NewsInput.http_url(value)


class NewsResponse(BaseModel):
    id: str
    title: str
    text: str | None = None
    published_at: AwareDatetime | None = None
    source: Source
    is_synthetic: bool
    created_at: AwareDatetime


class FeedItem(BaseModel):
    id: str
    title: str
    published_at: AwareDatetime | None = None
    source: Source
    is_synthetic: bool
    relevance_score: float | None = Field(default=None, ge=0, le=1)
    impact_type: ImpactType | None = None
    impact_level: ImpactLevel | None = None
    short_insight: str | None = None
    relevance_reasons: list[str] = Field(default_factory=list)
    analysis_id: str | None = None


class FeedResponse(BaseModel):
    disclaimer: str = DISCLAIMER
    ranking_mode: Literal["chronological", "relevance"]
    scored_total: int
    items: list[FeedItem]
    total: int
    limit: int
    offset: int


class RelevanceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str = Field(min_length=1)
    role: Literal["ceo", "cfo"]
    news_id: str = Field(min_length=1)
    relevance_score: FiniteFloat = Field(ge=0, le=1)
    relevance_reasons: list[str] = Field(min_length=1)
    method: str = Field(min_length=1)
    method_version: str = Field(min_length=1)

    @field_validator("relevance_reasons")
    @classmethod
    def nonempty_reasons(cls, values):
        if any(not value.strip() for value in values):
            raise ValueError("Пустая причина релевантности")
        return values
