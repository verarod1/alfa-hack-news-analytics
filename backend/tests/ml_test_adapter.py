"""Только синтетический адаптер тестов. Не подключать в демо или production."""

import os
import time


def analyze(context):
    mode = os.getenv("TEST_ML_MODE", "ok")
    if mode == "timeout":
        time.sleep(10)
    if mode == "error":
        raise RuntimeError("TEST-SECRET-MUST-NOT-LEAK")
    news = context["news"]
    what = news["title"]
    why = "Синтетический ответ тестового адаптера, не бизнес-инсайт."
    source = {
        "id": "e_test",
        "type": "news",
        "news_id": news["id"],
        "title": news["title"],
        "url": news["source"]["url"],
        "published_at": news["published_at"],
    }
    if mode == "bad_source":
        source["news_id"] = "made_up"
    result = {
        "what_happened": what,
        "why_important": why,
        "importance": "important",
        "impact_type": "risk",
        "impact_level": "medium",
        "confidence": "low",
        "analyzed_news_ids": [news["id"]],
        "sources": [source],
        "bank_opinion": None,
        "statements": [
            {
                "field": "what_happened",
                "text": what,
                "statement_type": "fact",
                "evidence_ids": ["e_test"],
            },
            {
                "field": "why_important",
                "text": why,
                "statement_type": "model_inference",
                "evidence_ids": ["e_test"],
            },
        ],
        "company_factors": [
            {"field": "client_type", "value": "CLIENT", "impact": "Тест формата"}
        ],
    }
    return {
        "result": result,
        "steps": [],
        "relevance": {
            "company_id": context["company"]["id"],
            "role": context["role"],
            "news_id": news["id"],
            "relevance_score": 0.8,
            "relevance_reasons": ["Тест хранения оценки, не алгоритм релевантности"],
            "method": "synthetic-test-only",
            "method_version": "1",
        },
    }


def chat(context):
    if os.getenv("TEST_ML_MODE") == "error":
        raise RuntimeError("TEST-SECRET-MUST-NOT-LEAK")
    return {
        "answer": "Синтетический ответ чата для интеграционного теста.",
        "statement_type": "model_inference",
        "evidence_ids": ["e_test"],
        "bank_opinion": None,
    }
