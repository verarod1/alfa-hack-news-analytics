import psycopg
from pydantic import ValidationError
from app.settings import Settings


class DatabaseConfigError(RuntimeError):
    pass


def get_connection():
    try:
        settings = Settings()
    except ValidationError:
        raise DatabaseConfigError("Некорректная конфигурация приложения") from None
    options = {
        "connect_timeout": settings.db_connect_timeout,
        "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
    }
    if settings.database_url:
        return psycopg.connect(settings.database_url, **options)
    password = settings.postgres_password.get_secret_value()
    if not password:
        raise DatabaseConfigError("Не задан POSTGRES_PASSWORD или DATABASE_URL")
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=password,
        **options,
    )
