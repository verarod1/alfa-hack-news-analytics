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

    def company_ids(self):
        return tuple(
            dict.fromkeys(
                x.strip() for x in self.demo_company_ids.split(",") if x.strip()
            )
        )
