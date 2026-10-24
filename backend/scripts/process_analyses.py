"""Однократная обработка ограниченной пачки queued-задач, без фонового daemon."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from app.database import DatabaseConfigError
from app.settings import Settings
from app.repositories.analysis_repository import queued_ids
from app.services.analysis_service import process_analysis, retry_analysis
from app.services import ml_gateway
from app.services.errors import ServiceError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--analysis-id")
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Явно повторить failed или просроченную running",
    )
    parser.add_argument(
        "--company-id", help="Обязательно для --retry; разрешённый демо-контекст"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("--limit должен быть от 1 до 100")
    if args.retry and (not args.analysis_id or not args.company_id):
        parser.error("--retry требует --analysis-id и --company-id")
    if not ml_gateway.configured():
        print("ML-модуль не подключён. Задачи оставлены queued.", file=sys.stderr)
        return 1
    try:
        if args.retry:
            retry_analysis(args.analysis_id, args.company_id)
        ids = (
            [args.analysis_id]
            if args.analysis_id
            else queued_ids(Settings().company_ids(), args.limit)
        )
        failed = False
        for analysis_id in ids:
            try:
                process_analysis(analysis_id)
                print(f"{analysis_id}: completed")
            except ServiceError as error:
                failed = True
                print(f"{analysis_id}: {error.code}", file=sys.stderr)
        return int(failed)
    except (psycopg.Error, DatabaseConfigError, ServiceError):
        print(
            "Не удалось выполнить обработчик. Проверьте конфигурацию и состояние задачи.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
