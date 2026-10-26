"""Запускать через scripts/run_integration_tests.py: только отдельный временный кластер."""

import os
import sys
import uuid
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, skipUnless, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient
from app.api.main import app
from app.schemas.news import NewsInput
from app.services.news_service import save_news, save_relevance
from app.services.analysis_service import process_analysis, retry_analysis
from app.repositories import analysis_repository

ENABLED = bool(
    os.getenv("INTEGRATION_DATABASE_URL") and os.getenv("ALFA_TEST_CLUSTER_ROOT")
)


@skipUnless(
    ENABLED, "Нужен отдельный временный PostgreSQL: scripts/run_integration_tests.py"
)
class PostgreSQLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["INTEGRATION_DATABASE_URL"]
        # Проверка целевого кластера ДО первого INSERT. Рабочая alfa_news недопустима.
        with psycopg.connect(cls.dsn) as conn:
            database, data, host = conn.execute(
                "SELECT current_database(),current_setting('data_directory'),inet_server_addr()"
            ).fetchone()
            if (
                not database.startswith("alfa_mvp_test_")
                or Path(data) != Path(os.environ["ALFA_TEST_CLUSTER_ROOT"]) / "data"
                or host is not None
            ):
                raise RuntimeError(
                    "Отказ: PostgreSQL не является отдельным тестовым Unix-socket кластером"
                )
            companies = [
                ("U_81", "CLIENT", "1000", "1.0"),
                ("U_84", "CLIENT", "250000", "0.0"),
                ("U_67", "PROSPECT", "10000", "0.0"),
                ("U_90", "CLOSE_CLIENT", "10000", "0.0"),
            ]
            for cid, kind, revenue, owner in companies:
                raw = {
                    "SYNTHETIC_U": cid,
                    "CL_TYPE": kind,
                    "REVENUE_COMPANY": revenue,
                    "NEGATIVEMARK": owner,
                    "GROUP_ID": "test_group",
                    "CL_PRODUCT_LOA_MARK": "1.0",
                }
                conn.execute(
                    "INSERT INTO raw_companies (synthetic_u,raw_data) SELECT %s,%s "
                    "WHERE NOT EXISTS (SELECT 1 FROM raw_companies WHERE synthetic_u=%s)",
                    (cid, Jsonb(raw), cid),
                )
            if not conn.execute(
                "SELECT 1 FROM raw_payments WHERE payer='U_81' LIMIT 1"
            ).fetchone():
                conn.execute(
                    "INSERT INTO raw_payments (payer,beneficiary,pay_amt,pay_cnt) VALUES "
                    "('U_81','U_81',999999,1),('U_81','U_67',120.50,2),('U_84','U_81',25,1)"
                )
                conn.execute(
                    "INSERT INTO raw_person_links (synthetic_f,synthetic_u,raw_data) VALUES "
                    "('F_test','U_81','{}'),('F_test','U_67','{}')"
                )

    def setUp(self):
        self.env = self.enterContext(
            patch.dict(
                os.environ,
                {
                    "DATABASE_URL": self.dsn,
                    "DEMO_COMPANY_IDS": "U_81,U_84",
                    "ML_ADAPTER_MODULE": "",
                    "FEED_INCLUDE_SYNTHETIC": "true",
                    "BANK_MATERIALS_PATH": "",
                    "LLM_TIMEOUT_SECONDS": "1",
                    "LLM_BASE_URL": "",
                    "LLM_API_KEY": "",
                    "PYTHONPATH": str(Path(__file__).resolve().parent),
                },
            )
        )
        self.client = self.enterContext(TestClient(app, raise_server_exceptions=False))
        self.news = save_news(
            NewsInput(
                id="it_" + uuid.uuid4().hex,
                title="[ТЕСТ] " + uuid.uuid4().hex,
                text="Синтетическая новость интеграционного теста.",
                is_synthetic=True,
            )
        )

    def create(self, company="U_81"):
        response = self.client.post(
            "/api/v1/analyses",
            headers={"X-Company-ID": company},
            json={"company_id": company, "role": "cfo", "news_id": self.news.id},
        )
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()["analysis_id"]

    def test_collected_news_storage_api_ml_and_updates(self):
        """Collector fixtures -> real temporary SQL -> API/ML DTO, never working DB."""
        from datetime import datetime, timezone
        from unittest.mock import Mock
        from app.parsers.collector import collect
        from app.parsers.http_client import Response, NewsHTTPClient
        from app.parsers.sources import SOURCES
        from app.schemas.ml import AnalysisContext
        from app.settings import Settings

        fixtures = Path(__file__).parent / "fixtures" / "news"
        ids = []
        for code in ("cbr", "minfin", "fns"):
            source = SOURCES[code]
            body = (fixtures / (code + ".xml")).read_bytes()
            def client_for_feed(xml):
                client = Mock(spec=NewsHTTPClient)
                replies = [Response(200, xml, {}, source.feed_url)]
                if code != "cbr":
                    replies.append(Response(200, (fixtures / (code + ".html.txt")).read_bytes(), {}, "fixture"))
                client.get.side_effect = replies
                return client
            for _ in range(2):
                report = collect([code], Settings(), client=client_for_feed(body),
                                 now=datetime(2026, 10, 25, tzinfo=timezone.utc))
                self.assertEqual(report["sources"][0]["stored_or_existing"], 1, report)
            news_id = report["sources"][0]["items"][0]["id"]
            ids.append(news_id)
            with psycopg.connect(self.dsn) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM news WHERE id=%s", (news_id,)).fetchone()[0], 1)
            response = self.client.get("/api/v1/news/" + news_id)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["is_synthetic"])
            self.assertGreater(len(response.json()["text"]), 120)
            self.assertTrue(response.json()["source"]["url"].startswith("https://"))
            if code == "cbr":
                updated = body.replace("Условия финансирования бизнеса".encode(), "Исправленный заголовок".encode())
                conflict = collect([code], Settings(), client=client_for_feed(updated),
                                   now=datetime(2026, 10, 25, tzinfo=timezone.utc))
                self.assertEqual(conflict["sources"][0]["conflicts"], 1)
                self.assertEqual(self.client.get("/api/v1/news/" + news_id).json()["title"], response.json()["title"])
            context = AnalysisContext(
                analysis_id="fixture-context", role="ceo",
                company=self.client.get("/api/v1/companies/U_84", headers={"X-Company-ID": "U_84"}).json(),
                news=response.json(),
                relations=self.client.get("/api/v1/companies/U_84/relations?limit=1", headers={"X-Company-ID": "U_84"}).json(),
            )
            self.assertEqual(context.news.id, news_id)
            self.assertEqual(context.news.source.id, code)
        params = {"company_id": "U_84", "role": "ceo", "limit": 100}
        headers = {"X-Company-ID": "U_84"}
        feed = self.client.get("/api/v1/feed", params=params, headers=headers).json()
        self.assertEqual(feed["ranking_mode"], "chronological")
        self.assertTrue(set(ids).issubset({item["id"] for item in feed["items"]}))
        save_relevance({
            "company_id": "U_84", "role": "ceo", "news_id": ids[0],
            "relevance_score": 0.91, "relevance_reasons": ["Тестовая оценка совместимости ML"],
            "method": "fixture-only", "method_version": "1",
        })
        feed = self.client.get("/api/v1/feed", params=params, headers=headers).json()
        self.assertEqual(feed["ranking_mode"], "relevance")
        self.assertEqual(feed["items"][0]["id"], ids[0])

    def test_zz_integrated_ml_ranking_analysis_and_chat(self):
        """Реальный PostgreSQL + subprocess gateway + ML-адаптер; только LLM заменён."""
        from scripts.rank_news import rank_batch
        from app.repositories.news_repository import get_news
        os.environ["ML_ADAPTER_MODULE"] = "ml_pipeline_test_adapter"
        os.environ["LLM_TIMEOUT_SECONDS"] = "5"
        with patch('scripts.rank_news.list_news', return_value=([get_news(self.news.id)], 1)):
            for company, role in [("U_81", "cfo"), ("U_81", "ceo"), ("U_84", "cfo")]:
                self.assertEqual(rank_batch(company, role, 1)["saved"], [self.news.id])
        with psycopg.connect(self.dsn) as conn:
            scores = conn.execute("SELECT company_id,role,score FROM news_relevance WHERE news_id=%s", (self.news.id,)).fetchall()
        self.assertEqual(len({row[2] for row in scores}), 3)
        feed = self.client.get('/api/v1/feed', params={'company_id': 'U_81', 'role': 'cfo', 'limit': 100}).json()
        item = next(item for item in feed['items'] if item['id'] == self.news.id)
        self.assertEqual(item['relevance_score'], .91)
        # Ошибка ML не создаёт новую оценку и не заменяет старую фиктивной.
        with patch('scripts.rank_news.list_news', return_value=([get_news(self.news.id)], 1)), patch('app.services.ml_gateway.rank', return_value={}):
            self.assertEqual(rank_batch('U_81', 'cfo', 1)['failed'], [self.news.id])
        aid = self.create()
        self.assertEqual(self.client.get('/api/v1/analyses/' + aid).json()['status'], 'queued')
        process_analysis(aid)
        result = self.client.get('/api/v1/analyses/' + aid).json()
        self.assertEqual(result['status'], 'completed', result)
        self.assertIsNone(result['result']['bank_opinion'])
        reply = self.client.post('/api/v1/chat/messages', json={'analysis_id': aid, 'message': '[ТЕСТ] Почему?'})
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(reply.json()['evidence_ids'], ['e_test'])
        history = self.client.get('/api/v1/analyses/' + aid + '/messages').json()
        self.assertEqual([item['role'] for item in history['items']], ['user', 'assistant'])
        filtered = self.client.get('/api/v1/feed', params={'company_id': 'U_81', 'role': 'cfo', 'impact_type': 'risk', 'limit': 100}).json()
        self.assertIn(self.news.id, [item['id'] for item in filtered['items']])

    def test_profiles_relations_and_client_restrictions(self):
        profile = self.client.get("/api/v1/companies/U_81").json()
        self.assertEqual(
            profile["revenue"], {"value": None, "unit": "RUB", "year": 2025}
        )
        self.assertTrue(profile["key_owner_flag"])
        self.assertEqual(self.client.get("/api/v1/companies/missing").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/companies/U_67").status_code, 403)
        relations = self.client.get("/api/v1/companies/U_81/relations").json()[
            "relations"
        ]
        self.assertEqual(
            {r["company"]["id"] for r in relations["payment_counterparties"]},
            {"U_67", "U_84"},
        )
        self.assertEqual(
            relations["payment_counterparties"][0]["payment_currency"], "RUB"
        )
        self.assertEqual(
            relations["shared_person_links"][0]["shared_person_id"], "F_test"
        )
        profiles = self.client.get("/api/v1/demo-profiles").json()["items"]
        self.assertEqual({p["company_id"] for p in profiles}, {"U_81", "U_84"})
        for company in ["U_67", "U_90"]:
            self.assertEqual(
                self.client.get(
                    f"/api/v1/feed?company_id={company}&role=cfo"
                ).status_code,
                403,
            )

    def test_news_deduplication_and_relevance_before_pagination(self):
        value = NewsInput(
            id="same_" + uuid.uuid4().hex,
            title="[ТЕСТ] " + uuid.uuid4().hex,
            text="Одинаковый текст",
            is_synthetic=True,
        )
        first = save_news(value)
        second = save_news(value)
        self.assertEqual(first.id, second.id)
        other = save_news(value.model_copy(update={"id": "other_" + uuid.uuid4().hex}))
        self.assertEqual(other.id, first.id)
        with self.assertRaises(Exception):
            save_news(value.model_copy(update={"title": "Другое содержимое"}))
        for news, score in [(first, 0.1), (self.news, 0.95)]:
            save_relevance(
                {
                    "company_id": "U_81",
                    "role": "cfo",
                    "news_id": news.id,
                    "relevance_score": score,
                    "relevance_reasons": ["Синтетическая оценка теста"],
                    "method": "test-only",
                    "method_version": "1",
                }
            )
        page = self.client.get("/api/v1/feed?company_id=U_81&role=cfo&limit=1").json()
        self.assertEqual(page["items"][0]["id"], self.news.id)
        self.assertEqual(page["ranking_mode"], "relevance")
        unscored = self.client.get("/api/v1/feed?company_id=U_81&role=ceo").json()
        self.assertEqual(unscored["ranking_mode"], "chronological")
        self.assertTrue(
            all(item["relevance_score"] is None for item in unscored["items"])
        )

    def test_importance_is_independent_of_status_and_tabs(self):
        tag = self.news.title
        records = [
            ("queued", None),
            ("running", None),
            ("failed", None),
            ("failed", "important"),
            ("completed", "normal"),
            ("completed", "important"),
            ("completed", "critical"),
        ]
        with psycopg.connect(self.dsn) as conn:
            for status, importance in records:
                # Синтетические строки проверяют SQL-фильтры; это не результаты ML.
                result = (
                    Jsonb({"what_happened": "test", "why_important": "test"})
                    if status == "completed"
                    else None
                )
                conn.execute(
                    "INSERT INTO analyses (id,company_id,role,news_id,status,importance,result) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        "filter_" + uuid.uuid4().hex,
                        "U_81",
                        "cfo",
                        self.news.id,
                        status,
                        importance,
                        result,
                    ),
                )
        params = {"company_id": "U_81", "role": "cfo", "search": tag}
        cases = [
            ({"tab": "all"}, 7),
            ({"tab": "ready"}, 3),
            ({"tab": "processing"}, 2),
            ({"tab": "attention"}, 3),
            ({"status": "failed"}, 2),
            ({"tab": "attention", "status": "failed"}, 1),
            ({"importance": "critical", "status": "completed"}, 1),
            ({"tab": "processing", "importance": "important"}, 0),
        ]
        for filters, total in cases:
            response = self.client.get(
                "/api/v1/my-analyses", params={**params, **filters, "limit": 1}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["total"], total, (filters, response.text))
            self.assertLessEqual(len(response.json()["items"]), 1)
        response = self.client.get(
            "/api/v1/my-analyses", params={**params, "status": ["queued", "running"]}
        )
        self.assertEqual(response.json()["total"], 2)

    def test_analysis_scope_and_unavailable_ml(self):
        analysis = self.create()
        self.assertEqual(
            self.client.get("/api/v1/analyses/" + analysis).json()["status"], "queued"
        )
        body = {"company_id": "U_81", "role": "cfo", "news_id": self.news.id}
        headers = {"Idempotency-Key": "analysis-" + uuid.uuid4().hex}
        first = self.client.post("/api/v1/analyses", json=body, headers=headers)
        second = self.client.post("/api/v1/analyses", json=body, headers=headers)
        self.assertEqual(first.json()["analysis_id"], second.json()["analysis_id"])

        for suffix in ["", "/trace", "/messages"]:
            response = self.client.get(
                "/api/v1/analyses/" + analysis + suffix,
                headers={"X-Company-ID": "U_84"},
            )
            self.assertEqual(response.status_code, 403)
        with self.assertRaises(Exception):
            process_analysis(analysis)
        self.assertEqual(analysis_repository.get_analysis(analysis)["status"], "queued")
        headers = {"Idempotency-Key": "same-question"}
        body = {"analysis_id": analysis, "message": "Синтетический вопрос"}
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    "/api/v1/chat/messages", headers=headers, json=body
                ).status_code,
                503,
            )
        self.assertEqual(
            self.client.get("/api/v1/analyses/" + analysis + "/messages").json()[
                "total"
            ],
            1,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/chat/messages", headers={"X-Company-ID": "U_84"}, json=body
            ).status_code,
            403,
        )

        from app.repositories import chat_repository
        from app.schemas.chat import AgentChatReply

        with psycopg.connect(self.dsn) as conn:
            user_id = conn.execute(
                "SELECT m.id FROM chat_messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.analysis_id=%s AND m.role='user'",
                (analysis,),
            ).fetchone()[0]
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE analysis_id=%s", (analysis,)
            ).fetchone()[0]
        self.assertTrue(chat_repository.claim_message(user_id, "old-chat-token", 900))
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE chat_messages SET response_updated_at=now()-interval '2 days' WHERE id=%s",
                (user_id,),
            )
        self.assertTrue(chat_repository.claim_message(user_id, "new-chat-token", 900))
        reply = AgentChatReply(
            answer="Только тест",
            statement_type="model_inference",
            evidence_ids=["test"],
        )
        with self.assertRaises(ValueError):
            chat_repository.save_assistant_message(
                conversation, user_id, "old-chat-token", reply
            )
        chat_repository.fail_message(user_id, "new-chat-token")

    def test_real_worker_completion_chat_and_safe_retry(self):
        analysis = self.create()
        with patch.dict(
            os.environ, {"ML_ADAPTER_MODULE": "ml_test_adapter", "TEST_ML_MODE": "ok"}
        ):
            command = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "backend/scripts/process_analyses.py",
                    "--analysis-id",
                    analysis,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(
                analysis_repository.get_analysis(analysis)["status"], "completed"
            )
            trace = self.client.get("/api/v1/analyses/" + analysis + "/trace").json()[
                "steps"
            ]
            self.assertEqual([s["status"] for s in trace], ["completed"] * 3)
            body = {"analysis_id": analysis, "message": "Тест чата"}
            response = self.client.post(
                "/api/v1/chat/messages",
                headers={"Idempotency-Key": "reply-once"},
                json=body,
            )
            self.assertEqual(response.status_code, 200, response.text)
            second = self.client.post(
                "/api/v1/chat/messages",
                headers={"Idempotency-Key": "reply-once"},
                json=body,
            )
            self.assertEqual(second.json()["message_id"], response.json()["message_id"])
            self.assertEqual(
                self.client.get("/api/v1/analyses/" + analysis + "/messages").json()[
                    "total"
                ],
                2,
            )
        failed = self.create()
        with patch.dict(
            os.environ,
            {"ML_ADAPTER_MODULE": "ml_test_adapter", "TEST_ML_MODE": "error"},
        ):
            with self.assertRaises(Exception):
                process_analysis(failed)
        self.assertEqual(analysis_repository.get_analysis(failed)["status"], "failed")
        self.assertNotIn(
            "TEST-SECRET", str(self.client.get("/api/v1/analyses/" + failed).json())
        )
        retry_analysis(failed, "U_81")
        with patch.dict(
            os.environ, {"ML_ADAPTER_MODULE": "ml_test_adapter", "TEST_ML_MODE": "ok"}
        ):
            process_analysis(failed)
        self.assertEqual(analysis_repository.get_analysis(failed)["attempt_count"], 2)
        with self.assertRaises(Exception):
            retry_analysis(analysis, "U_81")

    def test_timeout_invalid_sources_and_stale_attempt_cannot_complete(self):
        for mode, code in [
            ("timeout", "ML_TIMEOUT"),
            ("bad_source", "ML_RESULT_INVALID"),
        ]:
            analysis = self.create()
            with patch.dict(
                os.environ,
                {"ML_ADAPTER_MODULE": "ml_test_adapter", "TEST_ML_MODE": mode},
            ):
                with self.assertRaises(Exception):
                    process_analysis(analysis)
            row = analysis_repository.get_analysis(analysis)
            self.assertEqual((row["status"], row["error_code"]), ("failed", code))
            trace = analysis_repository.get_trace(analysis)
            self.assertEqual(trace[-1]["status"], "failed")
        analysis = self.create()
        old = analysis_repository.claim_analysis(analysis, "old-token", 3)
        self.assertIsNone(
            analysis_repository.claim_analysis(analysis, "another-token", 3)
        )
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE analyses SET updated_at=now()-interval '2 days' WHERE id=%s",
                (analysis,),
            )
        retry_analysis(analysis, "U_81")
        with self.assertRaises(ValueError):
            analysis_repository.complete_analysis(analysis, "old-token", {}, [])
        self.assertEqual(analysis_repository.get_analysis(analysis)["status"], "queued")

    def test_transactions_and_foreign_keys(self):
        marker = "rollback_" + uuid.uuid4().hex
        try:
            with psycopg.connect(self.dsn) as conn:
                conn.execute(
                    "INSERT INTO news (id,title,is_synthetic,content_hash) VALUES (%s,%s,true,%s)",
                    (marker, "Тест", marker),
                )
                raise ValueError("Проверяем реальный rollback")
        except ValueError:
            pass
        with psycopg.connect(self.dsn) as conn:
            self.assertIsNone(
                conn.execute("SELECT id FROM news WHERE id=%s", (marker,)).fetchone()
            )
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            analysis_repository.create_analysis(
                "fk_" + uuid.uuid4().hex, "U_81", "cfo", "missing_news"
            )
        with psycopg.connect(self.dsn) as conn:
            before = conn.execute("SELECT count(*) FROM raw_companies").fetchone()[0]
            conn.execute(Path("backend/db/upgrade_mvp_v2.sql").read_text())
            conn.execute(Path("backend/db/mvp.sql").read_text())
            self.assertEqual(
                conn.execute("SELECT count(*) FROM raw_companies").fetchone()[0], before
            )

    def test_csv_replace_rollback_and_parallel_import_lock(self):
        from scripts import import_csv

        with psycopg.connect(self.dsn) as conn:
            before = [
                conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                for table in ["raw_companies", "raw_payments", "raw_person_links"]
            ]
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "df_Uid_data_hack.csv").write_text("SYNTHETIC_U\nT_1\n")
            (directory / "df_Uid_payment_hack.csv").write_text(
                "PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\nT_1;T_2;1;1\n"
            )
            (directory / "df_Fid_Uid_link_hack.csv").write_text(
                "SYNTHETIC_F;SYNTHETIC_U\nf;\n"
            )
            with patch.object(import_csv, "DATA_DIR", directory):
                with self.assertRaises(import_csv.ImportError):
                    with psycopg.connect(self.dsn) as conn:
                        import_csv.run_import(conn, replace=True)
        with psycopg.connect(self.dsn) as conn:
            after = [
                conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                for table in ["raw_companies", "raw_payments", "raw_person_links"]
            ]
        self.assertEqual(before, after)
        with psycopg.connect(self.dsn) as first:
            first.execute(
                "SELECT pg_advisory_xact_lock(%s)", (import_csv.IMPORT_LOCK_KEY,)
            )
            with self.assertRaisesRegex(import_csv.ImportError, "Другой импорт"):
                with psycopg.connect(self.dsn) as second:
                    import_csv.run_import(second)


if __name__ == "__main__":
    main()
