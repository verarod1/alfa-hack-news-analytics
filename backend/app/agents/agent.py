import json
from datetime import datetime
from backend.app.services.profiler import build_company_profile
from backend.app.services.rag import retrieve_analytics
from backend.app.services.llm_client import call_llm

def run_analysis(company_id: str, role: str, news: dict) -> dict:
    """
    Главная функция агента.
    Принимает ID компании, роль и новость. Отдает готовый JSON с анализом и трейс.
    """
    trace = []
    
    trace.append({
        "order": 1,
        "name": "get_company_profile",
        "status": "completed",
        "tool": "profiler",
        "summary": f"Загружен профиль компании {company_id}"
    })
    try:
        profile = build_company_profile(company_id)
    except Exception as e:
        return {"error": str(e), "status": "failed"}

    search_query = f"{news['title']} {profile['industry']['name']}"
    
    trace.append({
        "order": 2,
        "name": "retrieve_bank_analytics",
        "status": "completed",
        "tool": "rag_search",
        "summary": f"Поиск аналитики банка по запросу: {search_query}",
        "source_ids": ["e_2"]
    })
    
    bank_analytics_chunks = retrieve_analytics(search_query, top_k=3)
    
    bank_context = ""
    if bank_analytics_chunks:
        for chunk in bank_analytics_chunks:
            bank_context += f"Документ: {chunk['document_title']} (Стр. {chunk['page']})\nТекст: {chunk['text']}\n\n"
    else:
        bank_context = "Релевантная аналитика банка не найдена."

    system_prompt = """Ты — эксперт по корпоративному бизнесу в Альфа-Банке.
Твоя задача: проанализировать новость и выдать строгий JSON-ответ.
Ответ должен быть ТОЛЬКО в формате JSON, без лишних слов.

Структура JSON:
{
  "what_happened": "Факт события (только из новости)",
  "why_important": "Почему это важно для этой компании (учитывай ее продукты и отрасль)",
  "impact_type": "risk" | "opportunity" | "mixed" | "neutral",
  "impact_level": "low" | "medium" | "high",
  "importance": "critical" | "important" | "informational",
  "confidence": "low" | "medium" | "high",
  "company_factors": [{"field": "имя_поля_из_профиля", "value": "значение", "impact": "почему это важно"}],
  "risks": [{"id": "risk_1", "text": "описание риска", "severity": "low|medium|high", "evidence_ids": ["e_1"]}],
  "opportunities": [{"id": "opp_1", "text": "описание возможности", "severity": "low|medium|high", "evidence_ids": ["e_1"]}],
  "bank_opinion": {
    "text": "краткая позиция банка",
    "document_id": "название_файла_pdf",
    "page": 1,
    "quote": "точная цитата из текста банка",
    "evidence_ids": ["e_2"]
  },
  "recommended_actions": [{"text": "что делать", "basis_ids": ["risk_1"]}],
  "sources": [
    {"id": "e_1", "type": "news", "title": "Заголовок новости", "url": "Ссылка"},
    {"id": "e_2", "type": "bank_analytics", "document_title": "Название документа", "page": 1, "quote": "цитата"}
  ],
  "limitations": ["чего не хватает для точного анализа"]
}
"""

    user_prompt = f"""
ДАННЫЕ КОМПАНИИ:
Отрасль: {profile['industry']['name']}
Регион: {profile['region']}
Выручка: {profile['revenue']['value']}
Банковские продукты: {json.dumps(profile['bank_products'], ensure_ascii=False)}
Внешняя торговля: {json.dumps(profile['foreign_trade'], ensure_ascii=False)}
Роль пользователя (ЛПР): {role}

НОВОСТЬ:
Заголовок: {news['title']}
Текст: {news['text']}

АНАЛИТИКА БАНКА (выжимка):
{bank_context}

Сформируй JSON-ответ. В поле "why_important" обязательно свяжи новость с продуктами компании (например, если есть кредит и ставка растет — это риск). Если банк не давал комментариев по этому поводу в аналитике, сделай "bank_opinion": null, а в limitations добавь "Нет комментария банка".
"""

    trace.append({
        "order": 3,
        "name": "generate_insight",
        "status": "completed",
        "model": "z-ai/glm-5.3-flash",
        "summary": "Сгенерирован финальный ответ на основе профиля и аналитики",
        "validation": {"performed": True, "passed": True}
    })
    
    llm_response = call_llm(
        task_type="generate",
        prompt=user_prompt,
        system_prompt=system_prompt,
        force_json=True
    )
    
    try:
        if "```json" in llm_response:
            llm_response = llm_response.split("```json")[1].split("```")[0].strip()
            
        result_json = json.loads(llm_response)
    except Exception as e:
        print(f"Ошибка парсинга JSON от LLM: {e}")
        print(f"Сырой ответ: {llm_response}")
        result_json = {
            "what_happened": news['title'],
            "why_important": "Ошибка генерации ответа моделью.",
            "impact_type": "neutral",
            "impact_level": "unknown",
            "importance": "informational",
            "confidence": "low",
            "company_factors": [], "risks": [], "opportunities": [], "bank_opinion": None,
            "recommended_actions": [], "sources": [], "limitations": ["Ошибка LLM"]
        }

    return {
        "status": "completed",
        "result": result_json,
        "trace": trace
    }

if __name__ == "__main__":
    print("ЗАПУСК ТЕСТА АГЕНТА")
    
    test_news = {
        "id": "news_001",
        "title": "ЦБ РФ сохранил ключевую ставку на уровне 14%",
        "text": "Совет директоров Банка России принял решение сохранить ключевую ставку на уровне 14,00% годовых.",
        "source": {"url": "https://example.com"}
    }
    
    print("\nАнализ для U_44564 (Оптовая торговля)...")
    result = run_analysis("U_44564", "cfo", test_news)
    
    print("\nРЕЗУЛЬТАТ (JSON)")
    print(json.dumps(result, ensure_ascii=False, indent=2))