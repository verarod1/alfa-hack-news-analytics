from psycopg.rows import dict_row
from app.database import get_connection


def get_shared_person_links(company_id, limit):
    query = """
        SELECT DISTINCT other.synthetic_u AS company_id,
                        own.synthetic_f AS shared_person_id
        FROM raw_person_links own
        JOIN raw_person_links other ON other.synthetic_f = own.synthetic_f
        WHERE own.synthetic_u = %s AND other.synthetic_u <> %s
        ORDER BY company_id, shared_person_id LIMIT %s
    """
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, (company_id, company_id, limit))
        return cursor.fetchall()
