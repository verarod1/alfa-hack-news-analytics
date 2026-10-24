from uuid import uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app.database import get_connection


def save_user_message(analysis_id, conversation_id, message, request_key=None):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        if conversation_id is not None:
            cursor.execute(
                "SELECT id FROM conversations WHERE id=%s AND analysis_id=%s",
                (conversation_id, analysis_id),
            )
            conversation = cursor.fetchone()
            if conversation is None:
                return None
        else:
            cursor.execute(
                "INSERT INTO conversations (id,analysis_id) VALUES (%s,%s) "
                "ON CONFLICT (analysis_id) DO NOTHING",
                ("chat_" + uuid4().hex, analysis_id),
            )
            cursor.execute(
                "SELECT id FROM conversations WHERE analysis_id=%s", (analysis_id,)
            )
            conversation = cursor.fetchone()
        message_id = "msg_" + uuid4().hex
        cursor.execute(
            "INSERT INTO chat_messages (id,conversation_id,role,content,request_key,response_status) "
            "VALUES (%s,%s,'user',%s,%s,'queued') ON CONFLICT DO NOTHING RETURNING id",
            (message_id, conversation["id"], message, request_key),
        )
        inserted = cursor.fetchone()
        if inserted is None:
            cursor.execute(
                "SELECT id,content FROM chat_messages WHERE conversation_id=%s AND request_key=%s AND role='user'",
                (conversation["id"], request_key),
            )
            inserted = cursor.fetchone()
            if inserted is None or inserted["content"] != message:
                raise ValueError(
                    "Idempotency-Key уже использован для другого сообщения"
                )
        return {"conversation_id": conversation["id"], "message_id": inserted["id"]}


def get_reply(user_message_id):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT id,content,evidence_ids,metadata FROM chat_messages WHERE reply_to=%s",
            (user_message_id,),
        )
        return cursor.fetchone()


def claim_message(message_id, token, lease_seconds):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE chat_messages SET response_status='running',response_token=%s,response_updated_at=now() "
            "WHERE id=%s AND role='user' AND (response_status IN ('queued','failed') OR "
            "(response_status='running' AND response_updated_at<now()-make_interval(secs => %s))) RETURNING id",
            (token, message_id, lease_seconds),
        )
        return cursor.fetchone() is not None


def fail_message(message_id, token):
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE chat_messages SET response_status='failed',response_token=NULL,response_updated_at=now() "
            "WHERE id=%s AND response_token=%s AND response_status='running'",
            (message_id, token),
        )


def save_assistant_message(conversation_id, user_message_id, token, reply):
    message_id = "msg_" + uuid4().hex
    metadata = {
        "statement_type": reply.statement_type,
        "bank_opinion": (
            reply.bank_opinion.model_dump(mode="json") if reply.bank_opinion else None
        ),
    }
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE chat_messages SET response_status='completed',response_token=NULL,response_updated_at=now() "
            "WHERE id=%s AND conversation_id=%s AND response_token=%s AND response_status='running' RETURNING id",
            (user_message_id, conversation_id, token),
        )
        if cursor.fetchone() is None:
            raise ValueError("Попытка ответа устарела")
        cursor.execute(
            "INSERT INTO chat_messages (id,conversation_id,role,content,evidence_ids,reply_to,metadata) "
            "VALUES (%s,%s,'assistant',%s,%s,%s,%s)",
            (
                message_id,
                conversation_id,
                reply.answer,
                Jsonb(reply.evidence_ids),
                user_message_id,
                Jsonb(metadata),
            ),
        )
    return message_id


def list_messages(analysis_id, limit, offset):
    base = " FROM chat_messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.analysis_id=%s"
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SELECT count(*) AS total" + base, (analysis_id,))
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT m.id AS message_id,m.role,m.content,m.evidence_ids,m.created_at, "
            "m.metadata->>'statement_type' AS statement_type,m.metadata->'bank_opinion' AS bank_opinion"
            + base
            + " ORDER BY m.created_at,m.id LIMIT %s OFFSET %s",
            (analysis_id, limit, offset),
        )
        return cursor.fetchall(), total
