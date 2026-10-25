from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
import psycopg
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.database import DatabaseConfigError
from app.settings import Settings
from app.services.errors import ServiceError
from app.api.routes import profiles, news, analyses, chat
from app.api.routes.companies import router as companies_router

app = FastAPI(
    title="Alfa Hack News Analytics API",
    description="API для обработки новостей и генерации бизнес-инсайтов",
    version="1.0.0",
)

# Настройка CORS для локальной разработки (чтобы React мог делать запросы)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        value.strip() for value in Settings().cors_origins.split(",") if value.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(companies_router)
app.include_router(profiles.router)
app.include_router(news.router)
app.include_router(analyses.router)
app.include_router(chat.router)


@app.middleware("http")
async def request_id(request, call_next):
    request.state.request_id = "req_" + uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        response = error_response(
            request, 500, "INTERNAL_ERROR", "Внутренняя ошибка сервера"
        )
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def error_response(request, status, code, message, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": details or []},
            "request_id": getattr(request.state, "request_id", "req_" + uuid4().hex),
        },
    )


@app.exception_handler(ServiceError)
async def service_error(request, error):
    return error_response(
        request, error.status_code, error.code, error.message, error.details
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    details = [
        {"field": ".".join(str(part) for part in item["loc"]), "reason": item["type"]}
        for item in error.errors()
    ]
    return error_response(
        request, 422, "VALIDATION_ERROR", "Некорректные параметры запроса", details
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request, error):
    return error_response(request, error.status_code, "HTTP_ERROR", str(error.detail))


@app.exception_handler(psycopg.Error)
@app.exception_handler(DatabaseConfigError)
async def database_error(request, error):
    return error_response(
        request,
        503,
        "DATABASE_UNAVAILABLE",
        "База данных недоступна или схема не подготовлена",
    )


class NewsRequest(BaseModel):
    text: str
    company_id: str


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running"}


@app.post("/api/analyze", deprecated=True)
async def analyze_news(request: NewsRequest):
    raise ServiceError(
        503,
        "ML_UNAVAILABLE",
        "Используйте POST /api/v1/analyses; ML-агент ещё не подключён",
    )
