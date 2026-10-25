import sys
from pathlib import Path

# Добавляем папку backend в пути поиска Python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from app.services.rag import retrieve_analytics
from app.services.llm_client import call_llm


SYSTEM_PROMPT = """
Ты — экспертный аналитик Альфа-Банка. Проанализируй новость для компании.
Верни ответ СТРОГО в формате JSON (без markdown-разметки).

Структура JSON:
{
  "result": {
    "what_happened": "Краткое описание факта",
    "why_important": "Почему это важно для компании",
    "statements": [
      {"field": "what_happened", "text": "Тот же текст, что в what_happened", "statement_type": "fact", "evidence_ids": ["e_1"]},
      {"field": "why_important", "text": "Тот же текст, что в why_important", "statement_type": "model_inference", "evidence_ids": ["e_1"]}
    ],
    "impact_type": "risk | opportunity | mixed | neutral",
    "impact_level": "low | medium | high",
    "importance": "normal | important | critical",
    "confidence": "low | medium | high",
    "company_factors": [
      {"field": "bank_products.loan", "value": true, "impact": "Повышает значимость"}
    ],
    "analyzed_news_ids": ["{news_id}"],
    "risks": [
      {"id": "risk_1", "text": "Риск", "severity": "medium", "statement_type": "model_inference", "evidence_ids": ["e_1"]}
    ],
    "opportunities": [
      {"id": "opp_1", "text": "Возможность", "severity": "low|medium|high", "statement_type": "model_inference", "evidence_ids": ["e_1"]}
    ],
    "bank_opinion": null,
    "recommended_actions": [
      {"text": "Действие", "basis_ids": ["risk_1"]}
    ],
    "sources": [
      {"id": "e_1", "type": "news", "news_id": "{news_id}", "url": "{news_url}"}
    ],
    "limitations": []
  }
}

ВАЖНО:
- Если в блоке "АНАЛИТИКА БАНКА" нет цитаты — верни строго "bank_opinion": null. НЕ придумывай document_id, page, quote. Значения "unknown", "", 0 запрещены.
- В sources поле "url" либо валидный http(s)-адрес, либо null. Не пиши строку "None" или "unknown".
- У каждого элемента opportunities обязателен "severity": low|medium|high.
- Тексты в statements[].text ДОЛЖНЫ точно совпадать с what_happened и why_important соответственно.
"""


def _fallback_result(news: dict) -> dict:
    """Безопасная заглушка, которая проходит все Pydantic-схемы бэкенда."""
    title = news.get("title", "Событие")
    return {
        "what_happened": title,
        "why_important": "Не удалось сформировать интерпретацию.",
        "statements": [
            {"field": "what_happened", "text": title,
             "statement_type": "fact", "evidence_ids": ["e_1"]},
            {"field": "why_important", "text": "Не удалось сформировать интерпретацию.",
             "statement_type": "hypothesis", "evidence_ids": []}
        ],
        "impact_type": "neutral",
        "impact_level": "unknown",
        "importance": "normal",
        "confidence": "low",
        "company_factors": [],
        "analyzed_news_ids": [news.get("id", "")],
        "risks": [],
        "opportunities": [],
        "bank_opinion": None,
        "recommended_actions": [],
        "sources": [{"id": "e_1", "type": "news", "news_id": news.get("id", ""), "url": None}],
        "limitations": ["Ошибка генерации JSON"]
    }


def analyze(context: dict) -> dict:
    """
    Главная функция, которую вызывает Backend.
    context содержит: company, news, role, relations, bank_materials.
    """
    print(" [ML ADAPTER] Получен запрос на анализ от бэкенда!")
    
    company = context.get("company", {})
    news = context.get("news", {})
    role = context.get("role", "cfo")
    
    # 1. Ищем в PDF (используем нашу базу)
    query = f"{news.get('title', '')} {news.get('text', '')}"
    bank_chunks = retrieve_analytics(query, top_k=1)
    
    bank_context = ""
    doc_id = "unknown"
    page_num = 1
    
    if bank_chunks:
        best_chunk = bank_chunks[0]
        bank_context = best_chunk["text"]
        doc_id = best_chunk["document_title"].replace(".pdf", "")
        page_num = best_chunk["page"]

    # 2. Формируем промпт
    prompt = f"""
    ПРОФИЛЬ: Отрасль {company.get('industry', {}).get('name')}, Продукты: {json.dumps(company.get('bank_products'))}
    РОЛЬ: {role}
    НОВОСТЬ: {news.get('title')}. {news.get('text')}
    АНАЛИТИКА БАНКА: {bank_context or 'НЕТ ДАННЫХ — bank_opinion должен быть null'}
    """

    # Подставляем реальные ID в системный промпт
    news_url = news.get("source", {}).get("url") or ""
    sys_prompt = SYSTEM_PROMPT.replace("{news_id}", news.get("id", "")).replace("{news_url}", str(news_url)).replace("{doc_id}", doc_id).replace("{page_num}", str(page_num))

    # 3. Вызываем нейросеть
    raw_json = call_llm(task_type="generate", prompt=prompt, system_prompt=sys_prompt, force_json=True)
    
    try:
        result_dict = json.loads(raw_json)
        if "result" not in result_dict:
            raise ValueError("Модель не вернула ключ result")
    except (json.JSONDecodeError, ValueError) as e:
        print(f" [ОШИБКА LLM] {e}")
        return {"result": _fallback_result(news), "steps": []}

    res = result_dict["result"]

    # --- САНИТАЙЗЕР (Чистим ответ от галлюцинаций нейросети) ---
    
    # 1. bank_opinion должен быть null, если нет чанков
    if not bank_chunks:
        res["bank_opinion"] = None
    elif isinstance(res.get("bank_opinion"), dict):
        bo = res["bank_opinion"]
        if not bo.get("quote") or bo.get("document_id") in (None, "", "unknown"):
            res["bank_opinion"] = None

    # 2. Чистим sources (чтобы URL не был строкой "None")
    for src in res.get("sources", []):
        url = src.get("url")
        if not url or not isinstance(url, str) or not url.startswith("http"):
            src["url"] = None
        if src.get("type") == "news" and not src.get("news_id"):
            src["news_id"] = news.get("id", "")

    # 3. Добавляем severity в opportunities, если нейросеть забыла
    for opp in res.get("opportunities", []):
        opp.setdefault("severity", "medium")
        opp.setdefault("statement_type", "model_inference")

    # 4. Возвращаем бэкенду СТРОГО нужный формат (extra="forbid")
    # Бэкенд сам подставит свои шаги и статусы
    return {
        "result": res,
        "steps": [] 
    }


def chat(context: dict) -> dict:
    """
    Ответ на вопрос пользователя в чате.
    """
    message = context.get("message", "")
    analysis_result = context.get("result", {})
    
    # Достаем ID источников из готового анализа
    sources = analysis_result.get("sources", [])
    evidence_ids = [s.get("id") for s in sources if s.get("id")] or ["e_1"]
    
    prompt = f"""
    Контекст анализа: {json.dumps(analysis_result, ensure_ascii=False)}
    Вопрос пользователя: {message}
    Ответь кратко и по делу.
    """
    
    answer = call_llm(task_type="chat", prompt=prompt)
    
    # Формат ответа для чата по контракту
    return {
        "answer": answer,
        "evidence_ids": evidence_ids,
        "statement_type": "model_inference",
        "bank_opinion": None
    }
    

if __name__ == "__main__":
    # Создаем фейковые данные, как будто их прислал бэкенд
    test_context = {
        "company": {
            "industry": {"name": "Оптовая торговля", "code": "46.51"},
            "bank_products": {"loan": True, "deposit": False},
            "revenue": {"value": 1000000}
        },
        "news": {
            "id": "demo_news_001",
            "title": "ЦБ сохранил ключевую ставку",
            "text": "Совет директоров Банка России принял решение сохранить ключевую ставку на уровне 14%.",
            "source": {"url": "http://example.com"}
        },
        "role": "cfo"
    }
    print("Запуск локального теста адаптера...")
    try:
        result = analyze(test_context)
        print("\n УСПЕХ! Результат:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n ОШИБКА: {e}")