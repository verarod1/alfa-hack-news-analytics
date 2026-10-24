from app.database import get_connection


def get_company_raw(company_id: str):
    query = """
        SELECT raw_data
        FROM raw_companies
        WHERE synthetic_u = %s
        ORDER BY row_id
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (company_id,))
            rows = cursor.fetchall()

    return [row[0] for row in rows]


def get_group_company_ids(company_id, group_id, limit):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT synthetic_u FROM raw_companies "
            "WHERE raw_data->>'GROUP_ID' = %s AND synthetic_u <> %s "
            "ORDER BY synthetic_u LIMIT %s",
            (group_id, company_id, limit),
        )
        return [row[0] for row in cursor.fetchall()]


def get_companies_raw(company_ids):
    if not company_ids:
        return {}
    grouped = {}
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT synthetic_u, raw_data FROM raw_companies WHERE synthetic_u=ANY(%s) ORDER BY row_id",
            (list(company_ids),),
        )
        for company_id, raw in cursor.fetchall():
            grouped.setdefault(company_id, []).append(raw)
    return grouped
