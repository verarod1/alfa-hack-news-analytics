"""Только изолированные тесты: настоящий ML-адаптер, ответы LLM заменены явно."""
import json
from unittest.mock import patch
from team_ml import adapter
import ml_test_adapter


def analyze(context):
    output = ml_test_adapter.analyze(context)
    # Оценку отдельно создаёт ранкер, а не генеративный анализ.
    output.pop("relevance", None)
    with patch.object(adapter, "call_llm", return_value=json.dumps(output)):
        return adapter.analyze(context)


def chat(context):
    with patch.object(adapter, "call_llm", return_value=json.dumps(ml_test_adapter.chat(context))):
        return adapter.chat(context)


def rank(context):
    from app.services import ranker
    score = 0.91 if context["role"] == "cfo" else 0.63
    if context["company"]["id"] == "U_84":
        score -= 0.2
    with patch.object(ranker, "call_llm", return_value=json.dumps({
        "relevance_score": score,
        "relevance_reasons": ["Тестовая оценка, не результат модели"],
    })):
        return adapter.rank(context)
