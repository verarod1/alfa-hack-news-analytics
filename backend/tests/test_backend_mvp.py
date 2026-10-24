"""Небольшие проверки бизнес-правил без рабочей PostgreSQL."""

import sys
import os
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.api.main import app
from app.services import company_service
from app.services.company_mapper import map_company
from app.schemas.analysis import AnalysisResult
from app.schemas.news import NewsInput
from app.settings import Settings


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(
            patch.dict(
                os.environ, {"DEMO_COMPANY_IDS": "U_81", "ML_ADAPTER_MODULE": ""}
            )
        )
        self.enterContext(
            patch.object(
                psycopg, "connect", side_effect=AssertionError("Рабочая БД запрещена")
            )
        )
        self.rows = self.enterContext(
            patch.object(
                company_service,
                "get_company_raw",
                return_value=[
                    {
                        "SYNTHETIC_U": "U_81",
                        "CL_TYPE": "CLIENT",
                        "REVENUE_COMPANY": "1000",
                        "NEGATIVEMARK": "1.0",
                    }
                ],
            )
        )
        self.client = self.enterContext(TestClient(app, raise_server_exceptions=False))

    def test_money_and_owner_mapping(self):
        result = map_company(
            {"SYNTHETIC_U": "U_81", "REVENUE_COMPANY": "1000.0", "NEGATIVEMARK": "1.0"}
        )
        self.assertEqual(
            result["revenue"], {"value": None, "unit": "RUB", "year": 2025}
        )
        self.assertTrue(result["key_owner_flag"])
        for amount in ["NaN", "Infinity", "1e9999"]:
            self.assertIsNone(
                map_company({"REVENUE_COMPANY": amount})["revenue"]["value"]
            )
        self.assertFalse(map_company({"NEGATIVEMARK": "0.0"})["key_owner_flag"])
        self.assertIsNone(map_company({"NEGATIVEMARK": "unknown"})["key_owner_flag"])

    def test_client_context_and_demo_profiles(self):
        self.assertEqual(self.client.get("/api/v1/companies/U_81").status_code, 200)
        self.assertEqual(
            len(self.client.get("/api/v1/demo-profiles").json()["items"]), 2
        )
        for kind in ["PROSPECT", "CLOSE_CLIENT"]:
            self.rows.return_value = [{"SYNTHETIC_U": "U_81", "CL_TYPE": kind}]
            self.assertEqual(
                self.client.get("/api/v1/feed?company_id=U_81&role=cfo").status_code,
                403,
            )
            self.assertEqual(
                self.client.get("/api/v1/demo-profiles").json(), {"items": []}
            )

    def test_roles_validation_and_swagger(self):
        self.assertEqual(
            [r["code"] for r in self.client.get("/api/v1/roles").json()["items"]],
            ["ceo", "cfo"],
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/my-analyses?company_id=U_81&role=cfo&importance=urgent"
            ).status_code,
            422,
        )
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(
            self.client.get(
                "/api/v1/feed?company_id=U_81&role=cfo&limit=0"
            ).status_code,
            422,
        )

    def test_sources_and_dates_are_not_optional_proof(self):
        with self.assertRaises(ValidationError):
            AnalysisResult(
                what_happened="Без источников", why_important="Без оснований"
            )
        with self.assertRaises(ValidationError):
            NewsInput(
                id="n", title="t", source_url="javascript:alert(1)", is_synthetic=True
            )
        with self.assertRaises(ValidationError):
            NewsInput(
                id="n", title="t", published_at="2026-10-24T12:00:00", is_synthetic=True
            )
        from datetime import datetime, timezone
        from app.schemas.ml import BankDocument
        from app.schemas.news import NewsResponse
        from app.schemas.analysis import Evidence
        from app.services.evidence_service import verify_sources

        news = NewsResponse(
            id="n",
            title="Тест",
            text="Текст",
            source={"id": None, "name": None, "url": None},
            is_synthetic=True,
            created_at=datetime.now(timezone.utc),
        )
        document = BankDocument(
            document_id="test_document",
            title="Только тест",
            pages=[{"page": 1, "text": "Синтетическая цитата"}],
        )
        source = Evidence(
            id="e",
            type="bank_analytics",
            document_id="test_document",
            page=1,
            quote="Синтетическая цитата",
        )
        verify_sources([source], news, [document])
        for quote in ["Выдуманный текст", "   "]:
            with self.assertRaises(ValueError):
                verify_sources(
                    [source.model_copy(update={"quote": quote})], news, [document]
                )

    def test_errors_and_cors(self):
        with patch.object(
            company_service,
            "get_company_raw",
            side_effect=psycopg.OperationalError("PASSWORD-SECRET"),
        ):
            response = self.client.get("/api/v1/companies/U_81")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PASSWORD-SECRET", response.text)
        with patch.object(
            company_service,
            "get_company_raw",
            side_effect=RuntimeError("PASSWORD-SECRET"),
        ):
            response = self.client.get("/api/v1/companies/U_81")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assertIn("x-request-id", response.headers)
        response = self.client.get(
            "/api/v1/roles", headers={"Origin": "https://untrusted.example"}
        )
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
