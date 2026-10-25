"""Общий клиент ML. Ошибка провайдера никогда не превращается в успешный ответ."""
import json
import re
from app.settings import Settings

# Имена контракта отдельно от идентификаторов OpenAI-совместимого провайдера.
MODEL_IDS = {
    "Gemma-4-26B-A4B": "google/gemma-4-26b-a4b-it",
    "GLM-5.3-Flash": "z-ai/glm-5.3-flash",
    "Qwen3.6-35B-A3B": "qwen/qwen3.6-35b-a3b",
    "DeepSeek-V4.1-Flash": "deepseek/deepseek-v4.1-flash",
    "Qwen3-VL-30B-A3B-Instruct": "qwen/qwen3-vl-30b-a3b-instruct",
    "Kimi-K2.6": "moonshotai/kimi-k2.6",
}
TOKEN_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def model_name(task_type):
    settings = Settings()
    selected = {
        "rank": settings.llm_rank_model,
        "chat": settings.llm_chat_model,
        "ocr": settings.llm_ocr_model,
    }.get(task_type) or settings.llm_model
    if selected not in MODEL_IDS:
        raise ValueError("Модель не входит в согласованный список")
    return MODEL_IDS[selected]


def get_client():
    # Импорт не создаёт клиента, не загружает модели и не выполняет сетевых запросов.
    from openai import OpenAI
    settings = Settings()
    if not settings.llm_api_key.get_secret_value() or not settings.llm_base_url:
        raise RuntimeError("Не настроены LLM_API_KEY и LLM_BASE_URL")
    return OpenAI(api_key=settings.llm_api_key.get_secret_value(),
                  base_url=settings.llm_base_url,
                  timeout=settings.llm_timeout_seconds, max_retries=0)


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    # Произвольный текст вокруг JSON не принимается за проверенный результат.
    json.loads(text)
    return text


def call_llm(task_type, prompt, system_prompt="", force_json=False):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    kwargs = dict(model=model_name(task_type), messages=messages, temperature=0.1,
                  max_tokens=Settings().llm_max_tokens)
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}
    response = get_client().chat.completions.create(**kwargs)
    choice = response.choices[0]
    if choice.finish_reason != "stop" or not choice.message.content or not choice.message.content.strip():
        raise ValueError("Провайдер вернул неполный или пустой ответ")
    if response.usage:
        for key in TOKEN_USAGE:
            TOKEN_USAGE[key] += getattr(response.usage, key, 0) or 0
    result = choice.message.content
    return _extract_json(result) if force_json else result


def get_usage_stats():
    return dict(TOKEN_USAGE)
