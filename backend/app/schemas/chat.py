from typing import Literal
from app.settings import DISCLAIMER
from app.schemas.analysis import BankOpinion
from pydantic import BaseModel, Field, AwareDatetime, ConfigDict, field_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: str = Field(min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1)
    message: str = Field(min_length=1, max_length=10000)

    @field_validator("message")
    @classmethod
    def nonempty_message(cls, value):
        if not value.strip():
            raise ValueError("Сообщение не может быть пустым")
        return value


class ChatResponse(BaseModel):
    disclaimer: str = DISCLAIMER
    statement_type: Literal["model_inference", "hypothesis"]
    bank_opinion: BankOpinion | None = None
    conversation_id: str
    message_id: str
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["completed"] = "completed"


class ChatMessage(BaseModel):
    statement_type: Literal["model_inference", "hypothesis"] | None = None
    bank_opinion: BankOpinion | None = None
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: AwareDatetime


class MessagesResponse(BaseModel):
    analysis_id: str
    items: list[ChatMessage]
    total: int
    limit: int
    offset: int


class AgentChatReply(BaseModel):
    statement_type: Literal["model_inference", "hypothesis"]
    bank_opinion: BankOpinion | None = None
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("answer")
    @classmethod
    def nonempty_answer(cls, value):
        if not value.strip():
            raise ValueError("Пустой ответ агента")
        return value
