"""Проверка по локальным доверенным материалам. Интернет и RAG здесь не вызываются."""

import json
from pathlib import Path
from app.schemas.ml import BankDocument
from app.settings import Settings, ROOT
from app.services.errors import ServiceError


def bank_materials():
    path = Settings().bank_materials_path
    if not path:
        # Читать готовый манифест можно без импорта/инициализации ML и Chroma.
        location = Path(Settings().ocr_cache_dir) / "bank_materials.json"
        if not location.is_absolute():
            location = ROOT / location
        if not location.exists():
            return []
        path = str(location)
    location = Path(path)
    if not location.is_absolute():
        location = ROOT / location
    try:
        documents = [
            BankDocument.model_validate(item)
            for item in json.loads(location.read_text())
        ]
        if len({item.document_id for item in documents}) != len(documents):
            raise ValueError
        for document in documents:
            if len({page.page for page in document.pages}) != len(document.pages):
                raise ValueError
        return documents
    except (OSError, ValueError, TypeError):
        raise ServiceError(
            503,
            "BANK_MATERIALS_INVALID",
            "Не удалось прочитать доверенные материалы банка",
        ) from None


def normalized(text):
    return " ".join(text.split())


def verify_sources(sources, news, documents):
    documents_by_id = {document.document_id: document for document in documents}
    pages = {
        (document.document_id, page.page): page.text
        for document in documents
        for page in document.pages
    }
    for source in sources:
        if source.type == "news":
            if source.news_id != news.id or source.url != news.source.url:
                raise ValueError("Источник новости не совпадает с серверной записью")
            if source.quote is not None:
                quote = normalized(source.quote)
                if not quote or quote not in normalized(
                    news.title + " " + (news.text or "")
                ):
                    raise ValueError("Цитата отсутствует в новости")
            source.title = news.title
            source.published_at = news.published_at
        else:
            text = pages.get((source.document_id, source.page))
            document = documents_by_id.get(source.document_id)
            if (
                not text
                or not document
                or source.url != document.url
                or not normalized(source.quote or "")
                or normalized(source.quote or "") not in normalized(text)
            ):
                raise ValueError("Документ, страница или цитата банка не подтверждены")
            source.document_title = document.title
            source.title = document.title


def verify_bank_opinion(opinion, sources):
    if opinion is None:
        return
    linked = [source for source in sources if source.id in opinion.evidence_ids]
    if not linked or not any(
        source.type == "bank_analytics"
        and source.document_id == opinion.document_id
        and source.page == opinion.page
        and source.quote == opinion.quote
        for source in linked
    ):
        raise ValueError("Позиция банка не связана с проверенным документом")


def verify_company_factors(factors, company):
    for factor in factors:
        current = company.model_dump()
        for part in factor.field.split("."):
            if not isinstance(current, dict) or part not in current:
                raise ValueError("Неизвестный признак компании")
            current = current[part]
        if current != factor.value:
            raise ValueError("Признак модели не совпадает с профилем компании")
