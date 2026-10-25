import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    timeout=180.0
)

MODELS = {
    "extract": "google/gemma-4-26b-a4b-it",
    "rank": "google/gemma-4-26b-a4b-it",
    "generate": "z-ai/glm-5.3-flash",
    "chat": "qwen/qwen3.6-35b-a3b",
    "research": "deepseek/deepseek-v4.1-flash"
}

CACHE = {}

TOKEN_USAGE = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
}


def _extract_json(text: str) -> str:
    """Достаёт JSON даже если модель обернула его в markdown или текст."""
    text = text.strip()
    if text.startswith("```json"):
        text = text.split("```json", 1)[1]
    if text.startswith("```"):
        text = text.split("```", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else text


def call_llm(task_type: str, prompt: str, system_prompt: str = "", force_json: bool = False) -> str:
    model_name = MODELS.get(task_type, MODELS["generate"])
    
    use_cache = os.getenv("ENABLE_LLM_CACHE", "true").lower() == "true"
    cache_key = f"{model_name}_{hash(system_prompt)}_{hash(prompt)}_{force_json}"
    
    if use_cache and cache_key in CACHE:
        print(f" [CACHE HIT] {task_type}")
        return CACHE[cache_key]

    print(f" [API CALL] {model_name} (task: {task_type})...")
    
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,          # Стабильный JSON
            "max_tokens": 4096           # Увеличен лимит
        }

        if force_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        
        if hasattr(response, 'usage') and response.usage:
            TOKEN_USAGE["prompt_tokens"] += response.usage.prompt_tokens
            TOKEN_USAGE["completion_tokens"] += response.usage.completion_tokens
            TOKEN_USAGE["total_tokens"] += response.usage.total_tokens
            print(f" [TOKENS] +{response.usage.total_tokens}. Всего: {TOKEN_USAGE['total_tokens']}")

        result = response.choices[0].message.content
        
        if use_cache:
            CACHE[cache_key] = result
            
        return result
        
    except Exception as e:
        print(f" Ошибка LLM: {e}")
        return "{}"


def get_usage_stats():
    return TOKEN_USAGE