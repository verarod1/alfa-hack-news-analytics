from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app.database import get_connection


def create_analysis(analysis_id, company_id, role, news_id, request_key=None):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "INSERT INTO analyses (id,company_id,role,news_id,request_key) VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING RETURNING *",
            (analysis_id, company_id, role, news_id, request_key),
        )
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "SELECT * FROM analyses WHERE company_id=%s AND role=%s AND request_key=%s",
                (company_id, role, request_key),
            )
            row = cursor.fetchone()
            if row is None or row["news_id"] != news_id:
                raise ValueError("Ключ анализа уже использован для другой новости")
        return row


def get_analysis(analysis_id):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM analyses WHERE id = %s", (analysis_id,))
        return cursor.fetchone()


def queued_ids(company_ids, limit):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM analyses WHERE status = 'queued' AND company_id = ANY(%s) "
            "ORDER BY created_at, id LIMIT %s",
            (list(company_ids), limit),
        )
        return [row[0] for row in cursor.fetchall()]


def claim_analysis(analysis_id, run_token, max_attempts):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "UPDATE analyses SET status='running', updated_at=now(), run_token=%s, "
            "attempt_count=attempt_count+1, error_code=NULL "
            "WHERE id=%s AND status='queued' AND attempt_count < %s RETURNING *",
            (run_token, analysis_id, max_attempts),
        )
        return cursor.fetchone()


def record_step(analysis_id, run_token, step):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO analysis_steps (analysis_id, attempt, step_order, name, status, model, tool, "
            "summary, source_ids, validation) SELECT id, attempt_count, %s,%s,%s,%s,%s,%s,%s,%s "
            "FROM analyses WHERE id=%s AND run_token=%s AND status='running' "
            "ON CONFLICT (analysis_id, attempt, step_order) DO UPDATE SET "
            "status=EXCLUDED.status, summary=EXCLUDED.summary, source_ids=EXCLUDED.source_ids, "
            "validation=EXCLUDED.validation",
            (
                step["order"],
                step["name"],
                step["status"],
                step.get("model"),
                step.get("tool"),
                step.get("summary"),
                Jsonb(step.get("source_ids", [])),
                Jsonb(step.get("validation", {})),
                analysis_id,
                run_token,
            ),
        )


def complete_analysis(analysis_id, run_token, result, steps, relevance=None):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE analyses SET status='completed', result=%s, importance=%s, "
            "updated_at=now(), run_token=NULL WHERE id=%s AND run_token=%s "
            "AND status='running' RETURNING attempt_count",
            (Jsonb(result), result.get("importance"), analysis_id, run_token),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Попытка анализа устарела")
        for step in steps:
            cursor.execute(
                "INSERT INTO analysis_steps (analysis_id, attempt, step_order, name, status, model, tool, "
                "summary, source_ids, validation) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    analysis_id,
                    row[0],
                    step["order"],
                    step["name"],
                    step["status"],
                    step.get("model"),
                    step.get("tool"),
                    step.get("summary"),
                    Jsonb(step.get("source_ids", [])),
                    Jsonb(step.get("validation", {})),
                ),
            )

        if relevance is not None:
            cursor.execute(
                "INSERT INTO news_relevance (company_id,role,news_id,score,reasons,method,method_version) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (company_id,role,news_id) "
                "DO UPDATE SET score=EXCLUDED.score,reasons=EXCLUDED.reasons,method=EXCLUDED.method, "
                "method_version=EXCLUDED.method_version,calculated_at=now()",
                (
                    relevance.company_id,
                    relevance.role,
                    relevance.news_id,
                    relevance.relevance_score,
                    Jsonb(relevance.relevance_reasons),
                    relevance.method,
                    relevance.method_version,
                ),
            )


def fail_analysis(analysis_id, run_token, error_code):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE analyses SET status='failed', result=NULL, importance=NULL, error_code=%s, "
            "updated_at=now(), run_token=NULL WHERE id=%s AND run_token=%s AND status='running'",
            (error_code, analysis_id, run_token),
        )


def retry_analysis(analysis_id, lease_seconds, max_attempts):
    # Только явный retry: failed либо просроченная running. Старый run_token отзывается.
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "UPDATE analyses SET status='queued', result=NULL, importance=NULL, run_token=NULL, "
            "error_code=NULL, updated_at=now() WHERE id=%s AND attempt_count < %s "
            "AND (status='failed' OR (status='running' AND "
            "updated_at < now() - make_interval(secs => %s))) RETURNING *",
            (analysis_id, max_attempts, lease_seconds),
        )
        return cursor.fetchone()


def get_trace(analysis_id):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            'SELECT attempt, step_order AS "order", name, status, model, tool, summary, '
            "source_ids, validation FROM analysis_steps WHERE analysis_id=%s ORDER BY attempt, step_order",
            (analysis_id,),
        )
        return cursor.fetchall()


def list_analyses(company_id, role, search, statuses, importance, tab, limit, offset):
    # tab — бизнес-фильтр, status/importance независимы и комбинируются через AND.
    tab_status = {"ready": ["completed"], "processing": ["queued", "running"]}.get(tab)
    tab_importance = ["important", "critical"] if tab == "attention" else None
    base = """
        FROM analyses a JOIN news n ON n.id=a.news_id
        LEFT JOIN conversations c ON c.analysis_id=a.id
        WHERE a.company_id=%s AND a.role=%s
        AND (%s::text IS NULL OR strpos(lower(n.title), lower(%s))>0)
        AND (%s::text[] IS NULL OR a.status=ANY(%s))
        AND (%s::text[] IS NULL OR a.importance=ANY(%s))
        AND (%s::text[] IS NULL OR a.status=ANY(%s))
        AND (%s::text[] IS NULL OR a.importance=ANY(%s))
    """
    params = (
        company_id,
        role,
        search,
        search,
        statuses,
        statuses,
        importance,
        importance,
        tab_status,
        tab_status,
        tab_importance,
        tab_importance,
    )
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SELECT count(*) AS total " + base, params)
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT a.id AS analysis_id, a.news_id, a.company_id, a.role, n.title, "
            "NULL::text AS origin, NULL::text AS input_type, a.status, a.importance, "
            "a.result->>'impact_type' AS impact_type, a.result->>'why_important' AS short_insight, "
            "a.created_at, c.id AS conversation_id "
            + base
            + " ORDER BY a.created_at DESC, a.id DESC LIMIT %s OFFSET %s",
            (*params, limit, offset),
        )
        return cursor.fetchall(), total
