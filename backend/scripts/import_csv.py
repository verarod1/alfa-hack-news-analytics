
import csv
import json
import os
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv



ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


load_dotenv(ROOT / ".env")


def clean(value):
    """Пустые строки преобразуем в None."""
    if value is None:
        return None

    value = value.strip()
    return value if value else None


def read_csv(filename):
    """Читаем CSV построчно, не загружая весь файл в память."""
    path = DATA_DIR / filename

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            yield {
                key: clean(value)
                for key, value in row.items()
            }


def import_companies(conn):
    count = 0

    with conn.cursor() as cursor:
        with cursor.copy(
            "COPY raw_companies "
            "(synthetic_u, raw_data) FROM STDIN"
        ) as copy:

            for row in read_csv("df_Uid_data_hack.csv"):
                copy.write_row((
                    row["SYNTHETIC_U"],
                    json.dumps(row, ensure_ascii=False)
                ))
                count += 1

    print(f"Компании загружены: {count}")


def import_payments(conn):
    count = 0

    with conn.cursor() as cursor:
        with cursor.copy(
            "COPY raw_payments "
            "(payer, beneficiary, pay_amt, pay_cnt) FROM STDIN"
        ) as copy:

            for row in read_csv("df_Uid_payment_hack.csv"):
                amount = row["PAY_AMT"]
                payment_count = row["PAY_CNT"]

                copy.write_row((
                    row["PAYER"],
                    row["BENEFICIARY"],
                    Decimal(amount) if amount else None,
                    int(payment_count) if payment_count else None
                ))
                count += 1

    print(f"Платежи загружены: {count}")


def import_person_links(conn):
    count = 0

    with conn.cursor() as cursor:
        with cursor.copy(
            "COPY raw_person_links "
            "(synthetic_f, synthetic_u, raw_data) FROM STDIN"
        ) as copy:

            for row in read_csv("df_Fid_Uid_link_hack.csv"):
                copy.write_row((
                    row["SYNTHETIC_F"],
                    row["SYNTHETIC_U"],
                    json.dumps(row, ensure_ascii=False)
                ))
                count += 1

    print(f"Связи загружены: {count}")


def main():
    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "Не найдена переменная POSTGRES_PASSWORD в .env"
        )

    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        dbname="alfa_news",
        user="alfa_user",
        password=password
    ) as conn:

        # Одна транзакция: при ошибке изменения откатятся
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    "TRUNCATE TABLE "
                    "raw_companies, raw_payments, raw_person_links "
                    "RESTART IDENTITY"
                )

            import_companies(conn)
            import_payments(conn)
            import_person_links(conn)

    print("Все CSV успешно импортированы")


if __name__ == "__main__":
    main()
