from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Alfa Hack News Analytics API",
    description="API для обработки новостей и генерации бизнес-инсайтов",
    version="1.0.0"
)

# Настройка CORS для локальной разработки (чтобы React мог делать запросы)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NewsRequest(BaseModel):
    text: str
    company_id: str

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running"}

@app.post("/api/analyze")
async def analyze_news(request: NewsRequest):
    # Позже здесь будет вызов многошаговой логики агента
    return {
        "status": "success",
        "company_id": request.company_id,
        "insight": "Здесь будет сгенерированная персонализированная интерпретация события."
    }