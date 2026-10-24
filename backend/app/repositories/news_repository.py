from psycopg.rows import dict_row
from app.database import get_connection


def save_news(values):
    query = """
        INSERT INTO news (id, title, text, published_at, source_id, source_name,
                          source_url, content_hash, is_synthetic)
        VALUES (%(id)s, %(title)s, %(text)s, %(published_at)s, %(source_id)s,
                %(source_name)s, %(source_url)s, %(content_hash)s, %(is_synthetic)s)
        ON CONFLICT DO NOTHING RETURNING *
    """
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, values)
        inserted = cursor.fetchone()
        if inserted:
            return [inserted]
        cursor.execute(
            "SELECT * FROM news WHERE id = %s OR content_hash = %s ORDER BY id",
            (values["id"], values["content_hash"]),
        )
        return cursor.fetchall()


def get_news(news_id):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM news WHERE id = %s", (news_id,))
        return cursor.fetchone()


def list_news(limit, offset):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT count(*) AS total FROM news")
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT * FROM news ORDER BY published_at DESC NULLS LAST, id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cursor.fetchall(), total


def save_relevance(value):
    from psycopg.types.json import Jsonb

    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO news_relevance (company_id, role, news_id, score, reasons, method, method_version) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (company_id, role, news_id) "
            "DO UPDATE SET score=EXCLUDED.score, reasons=EXCLUDED.reasons, method=EXCLUDED.method, "
            "method_version=EXCLUDED.method_version, calculated_at=now()",
            (
                value.company_id,
                value.role,
                value.news_id,
                value.relevance_score,
                Jsonb(value.relevance_reasons),
                value.method,
                value.method_version,
            ),
        )


def get_feed(company_id, role, impact_type, limit, offset):
    base = """
        FROM news n
        LEFT JOIN news_relevance r ON r.news_id=n.id AND r.company_id=%s AND r.role=%s
        LEFT JOIN LATERAL (
            SELECT id AS analysis_id, result FROM analyses
            WHERE news_id=n.id AND company_id=%s AND role=%s AND status='completed'
            ORDER BY created_at DESC, id DESC LIMIT 1
        ) a ON true
        WHERE (%s::text IS NULL OR a.result->>'impact_type'=%s)
    """
    params = (company_id, role, company_id, role, impact_type, impact_type)
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        # Одна snapshot для total и страницы при параллельной записи.
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(
            "SELECT count(*) AS total, count(r.score) AS scored " + base, params
        )
        counts = cursor.fetchone()
        cursor.execute(
            "SELECT n.*, a.analysis_id, a.result, r.score, r.reasons "
            + base
            + " ORDER BY r.score DESC NULLS LAST, n.published_at DESC NULLS LAST, n.id LIMIT %s OFFSET %s",
            (*params, limit, offset),
        )
        return cursor.fetchall(), counts["total"], counts["scored"]
