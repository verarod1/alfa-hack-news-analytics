from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent if BACKEND_DIR.name == "backend" else BACKEND_DIR
DISCLAIMER = "Материал носит информационный характер и не является индивидуальной инвестиционной рекомендацией."


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5433, ge=1, le=65535)
    postgres_db: str = "alfa_news"
    postgres_user: str = "alfa_user"
    postgres_password: SecretStr = SecretStr("")
    db_connect_timeout: int = Field(default=10, ge=1, le=60)
    db_statement_timeout_ms: int = Field(default=15000, ge=100, le=120000)
    demo_company_ids: str = "U_81"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    relations_limit: int = Field(default=200, ge=1, le=500)
    ml_adapter_module: str = ""
    llm_base_url: str = ""
    llm_model: str = "Gemma-4-26B-A4B"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: int = Field(default=60, ge=1, le=600)
    llm_max_tokens: int = Field(default=4096, ge=1, le=64000)
    max_analysis_attempts: int = Field(default=3, ge=1, le=10)
    analysis_lease_seconds: int = Field(default=900, ge=60, le=86400)
    bank_materials_path: str = ""
    bank_pdf_dir: str = "data/raw/bank_analytics"
    chroma_db_dir: str = "data/chroma_db"
    ocr_cache_dir: str = "data/ocr_cache"
    hf_home: str = "data/model_cache"
    embedding_model: str = "intfloat/multilingual-e5-small"
    llm_rank_model: str = ""
    llm_chat_model: str = ""
    llm_ocr_model: str = "Qwen3-VL-30B-A3B-Instruct"
    rag_top_k: int = Field(default=3, ge=1, le=10)
    news_sources: str = "cbr,minfin,fns"
    news_cbr_rss_url: str = "https://www.cbr.ru/rss/RssPress"
    news_minfin_rss_url: str = "https://minfin.gov.ru/rss_news?mod=news&lim=50"
    news_fns_rss_url: str = "https://www.nalog.gov.ru/rn77/rss/"
    news_limit: int = Field(default=10, ge=1, le=100)
    news_timeout_seconds: int = Field(default=20, ge=1, le=60)
    news_max_response_bytes: int = Field(default=2_000_000, ge=1000, le=5_000_000)
    news_user_agent: str = Field(default="AlfaHackNewsCollector/1.0", min_length=5, max_length=200, pattern=r"^[\x20-\x7e]+$")
    news_request_delay_seconds: float = Field(default=1.0, ge=1, le=60)
    news_max_age_days: int = Field(default=30, ge=0, le=3650)
    news_min_text_chars: int = Field(default=120, ge=40, le=1000)
    news_keywords: str = ""

    def company_ids(self):
        return tuple(
            dict.fromkeys(
                x.strip() for x in self.demo_company_ids.split(",") if x.strip()
            )
        )
