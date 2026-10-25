"""Ограниченный вызов доверенного ML-модуля в отдельном процессе, без реализации LLM."""

import json
import os
import re
import signal
import subprocess
import sys
from urllib.parse import urlsplit
from pathlib import Path
from app.settings import Settings, ROOT
from app.services.errors import ServiceError

ALLOWED_LLM_MODELS = {
    "Gemma-4-26B-A4B",
    "GLM-5.3-Flash",
    "Qwen3.6-35B-A3B",
    "DeepSeek-V4.1-Flash",
    "Qwen3-VL-30B-A3B-Instruct",
    "Kimi-K2.6",
}


def configured():
    return bool(Settings().ml_adapter_module)


def invoke(operation, context):
    settings = Settings()
    module = settings.ml_adapter_module
    if not module:
        raise ServiceError(503, "ML_UNAVAILABLE", "ML-модуль ещё не подключён")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module):
        raise ServiceError(503, "ML_CONFIG_ERROR", "Некорректное имя модуля адаптера")
    if settings.llm_base_url:
        base = urlsplit(settings.llm_base_url)
        if (
            base.scheme not in {"http", "https"}
            or not base.hostname
            or base.username
            or base.password
        ):
            raise ServiceError(503, "ML_CONFIG_ERROR", "Некорректный LLM_BASE_URL")
    if settings.llm_model not in ALLOWED_LLM_MODELS:
        raise ServiceError(
            503,
            "ML_CONFIG_ERROR",
            "Генеративная модель не входит в согласованный список",
        )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # Значения из .env передаются только процессу адаптера, не в JSON-контекст/ответ API.
    env.update(
        LLM_BASE_URL=settings.llm_base_url,
        LLM_MODEL=settings.llm_model,
        LLM_API_KEY=settings.llm_api_key.get_secret_value(),
        LLM_MAX_TOKENS=str(settings.llm_max_tokens),
        ML_PROCESS_TIMEOUT=str(settings.llm_timeout_seconds + 2),
        LLM_TIMEOUT_SECONDS=str(settings.llm_timeout_seconds),
        LLM_RANK_MODEL=settings.llm_rank_model,
        LLM_CHAT_MODEL=settings.llm_chat_model,
        LLM_OCR_MODEL=settings.llm_ocr_model,
        CHROMA_DB_DIR=settings.chroma_db_dir,
        HF_HOME=str(ROOT / settings.hf_home),
        OCR_CACHE_DIR=settings.ocr_cache_dir,
        EMBEDDING_MODEL=settings.embedding_model,
        RAG_TOP_K=str(settings.rag_top_k),
        HF_HUB_OFFLINE="1",
    )
    backend = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = str(backend) + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen(
        [sys.executable, "-B", "-m", "app.services.ml_runner", module, operation],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(
            json.dumps(context, ensure_ascii=False),
            timeout=settings.llm_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise ServiceError(
            504, "ML_TIMEOUT", "Превышено время ожидания ML-модуля"
        ) from None
    try:
        result = json.loads(output)
        if process.returncode != 0 or not result["ok"]:
            raise ValueError
        return result["value"]
    except (ValueError, KeyError, TypeError):
        raise ServiceError(
            502, "ML_ADAPTER_ERROR", "ML-модуль не вернул корректный результат"
        ) from None


def analyze(context):
    return invoke("analyze", context)


def chat(context):
    return invoke("chat", context)


def rank(context):
    return invoke("rank", context)
