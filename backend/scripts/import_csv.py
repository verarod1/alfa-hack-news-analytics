"""Атомарный импорт трёх CSV; замена существующих данных только с --replace."""
import argparse
import csv
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
TABLES = "raw_companies, raw_payments, raw_person_links"
# Постоянный ключ для всех запусков этого импортёра в одной БД.
IMPORT_LOCK_KEY = 71423001
FILES = {
    "df_Uid_data_hack.csv": ("SYNTHETIC_U",),
    "df_Uid_payment_hack.csv": ("PAYER", "BENEFICIARY", "PAY_AMT", "PAY_CNT"),
    "df_Fid_Uid_link_hack.csv": ("SYNTHETIC_F", "SYNTHETIC_U"),
}


class ImportError(ValueError):
    """Ошибка входных данных или отказ от небезопасного импорта."""


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url, connect_timeout=10)

    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ImportError("Не задан POSTGRES_PASSWORD или DATABASE_URL.")
    try:
        port = int(os.getenv("POSTGRES_PORT", "5433"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ImportError("POSTGRES_PORT должен быть числом от 1 до 65535.") from None
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=port,
        dbname=os.getenv("POSTGRES_DB", "alfa_news"),
        user=os.getenv("POSTGRES_USER", "alfa_user"),
        password=password,
        connect_timeout=10,
    )


def clean(value):
    if value is None:
        return None
    return value.strip() or None


def payment_values(row, filename, line):
    amount, count = clean(row["PAY_AMT"]), clean(row["PAY_CNT"])
    try:
        amount = Decimal(amount) if amount is not None else None
        if amount is not None and not amount.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        raise ImportError(f"{filename}, строка {line}: некорректный PAY_AMT.") from None
    if count is not None:
        if not re.fullmatch(r"[+-]?[0-9]+", count):
            raise ImportError(f"{filename}, строка {line}: PAY_CNT должен быть целым числом.")
        # Ограничиваем длину до int(), чтобы не обрабатывать огромные числа.
        digits = count.lstrip("+-").lstrip("0") or "0"
        if len(digits) > 19:
            raise ImportError(f"{filename}, строка {line}: PAY_CNT вне диапазона BIGINT.")
        count = int(("-" if count.startswith("-") else "") + digits)
        if not -(2**63) <= count < 2**63:
            raise ImportError(f"{filename}, строка {line}: PAY_CNT вне диапазона BIGINT.")
    return amount, count


def read_csv(filename):
    """Проверяем CSV построчно, сохраняя исходные значения для JSONB."""
    path = DATA_DIR / filename
    line = 1
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, delimiter=";", strict=True)
            headers = reader.fieldnames
            if not headers:
                raise ImportError(f"{filename}: пустой CSV, отсутствует заголовок.")
            if len(set(headers)) != len(headers) or any(not h.strip() for h in headers):
                raise ImportError(f"{filename}: пустые или повторяющиеся имена колонок.")
            missing = set(FILES[filename]) - set(headers)
            if missing:
                raise ImportError(f"{filename}: отсутствуют колонки: {', '.join(sorted(missing))}.")
            count = 0
            for row in reader:
                line = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    raise ImportError(f"{filename}, строка {line}: число полей не соответствует заголовку.")
                if any("\x00" in value for value in row.values()):
                    raise ImportError(f"{filename}, строка {line}: недопустимый нулевой символ.")
                for field in FILES[filename]:
                    if field not in ("PAY_AMT", "PAY_CNT") and clean(row[field]) is None:
                        raise ImportError(f"{filename}, строка {line}: пустое обязательное поле {field}.")
                if filename == "df_Uid_payment_hack.csv":
                    payment_values(row, filename, line)
                count += 1
                yield row, line
            if not count:
                raise ImportError(f"{filename}: CSV не содержит строк данных.")
    except UnicodeError:
        raise ImportError(f"{filename}: ошибка кодировки, ожидается UTF-8 (допустим BOM).") from None
    except csv.Error:
        raise ImportError(f"{filename}, строка {line}: некорректный формат CSV.") from None
    except OSError:
        raise ImportError(f"{filename}: файл отсутствует или недоступен для чтения.") from None


def import_companies(conn):
    count = 0
    with conn.cursor() as cursor:
        with cursor.copy("COPY raw_companies (synthetic_u, raw_data) FROM STDIN") as copy:
            for row, _ in read_csv("df_Uid_data_hack.csv"):
                copy.write_row((clean(row["SYNTHETIC_U"]), json.dumps(row, ensure_ascii=False)))
                count += 1
    return count


def import_payments(conn):
    count = 0
    filename = "df_Uid_payment_hack.csv"
    with conn.cursor() as cursor:
        with cursor.copy("COPY raw_payments (payer, beneficiary, pay_amt, pay_cnt) FROM STDIN") as copy:
            for row, line in read_csv(filename):
                amount, payment_count = payment_values(row, filename, line)
                copy.write_row((clean(row["PAYER"]), clean(row["BENEFICIARY"]), amount, payment_count))
                count += 1
    return count


def import_person_links(conn):
    count = 0
    with conn.cursor() as cursor:
        with cursor.copy("COPY raw_person_links (synthetic_f, synthetic_u, raw_data) FROM STDIN") as copy:
            for row, _ in read_csv("df_Fid_Uid_link_hack.csv"):
                copy.write_row((clean(row["SYNTHETIC_F"]), clean(row["SYNTHETIC_U"]), json.dumps(row, ensure_ascii=False)))
                count += 1
    return count


def run_import(conn, replace=False):
    # Проверка, блокировка и все COPY находятся в одной транзакции.
    with conn.transaction():
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", (IMPORT_LOCK_KEY,))
            if not cursor.fetchone()[0]:
                raise ImportError("Другой импорт уже выполняется. Повторите запуск позже.")
            if replace:
                cursor.execute(f"TRUNCATE TABLE {TABLES} RESTART IDENTITY")
            else:
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM raw_companies) "
                    "OR EXISTS (SELECT 1 FROM raw_payments) "
                    "OR EXISTS (SELECT 1 FROM raw_person_links)"
                )
                if cursor.fetchone()[0]:
                    raise ImportError("Исходные таблицы уже содержат данные. Импорт отменён; для полной замены предусмотрен --replace.")
        return import_companies(conn), import_payments(conn), import_person_links(conn)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="заменить данные только трёх исходных таблиц")
    args = parser.parse_args(argv)
    if args.replace:
        print("ВНИМАНИЕ: --replace заменит все данные raw_companies, raw_payments и raw_person_links.", file=sys.stderr, flush=True)
    try:
        # Проверяем все файлы до подключения и возможной очистки.
        for filename in FILES:
            for _ in read_csv(filename):
                pass
        with get_connection() as conn:
            counts = run_import(conn, replace=args.replace)
    except ImportError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except (psycopg.Error, ValueError):
        # Сообщения драйвера могут содержать DSN, пароль или данные строки COPY.
        print("Ошибка PostgreSQL: не удалось подключиться или завершить импорт. Проверьте настройки подключения, доступность БД, права и схему. Транзакция не подтверждена.", file=sys.stderr)
        return 1
    print(f"Все CSV успешно импортированы: компании — {counts[0]}, платежи — {counts[1]}, связи — {counts[2]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
