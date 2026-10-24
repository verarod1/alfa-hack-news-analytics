from psycopg.rows import dict_row
from app.database import get_connection


def get_payment_counterparties(company_id, limit):
    query = """
        SELECT beneficiary AS company_id, 'outgoing' AS direction,
               SUM(pay_amt) AS payment_amount, SUM(pay_cnt) AS payment_count
        FROM raw_payments
        WHERE payer = %s AND beneficiary IS NOT NULL AND beneficiary <> %s
        GROUP BY beneficiary
        UNION ALL
        SELECT payer AS company_id, 'incoming' AS direction,
               SUM(pay_amt) AS payment_amount, SUM(pay_cnt) AS payment_count
        FROM raw_payments
        WHERE beneficiary = %s AND payer IS NOT NULL AND payer <> %s
        GROUP BY payer
        ORDER BY company_id, direction LIMIT %s
    """
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, (company_id, company_id, company_id, company_id, limit))
        return cursor.fetchall()
