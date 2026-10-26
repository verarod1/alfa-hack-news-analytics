"""The Compose worker and retry API must keep the analysis lifecycle usable."""

import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.api.main import app
from app.services.client_context import selected_company
from app.services.errors import ServiceError
from scripts import analysis_worker


class AnalysisWorkerTests(TestCase):
    def test_failed_analysis_does_not_block_next_queued_analysis(self):
        with patch.object(analysis_worker, "configured", return_value=True), patch.object(
            analysis_worker, "queued_ids", return_value=["first", "second"]
        ) as queued, patch.object(
            analysis_worker,
            "process_analysis",
            side_effect=[ServiceError(502, "ML_ADAPTER_ERROR", "Failed"), None],
        ) as process:
            analysis_worker.run_once()
        self.assertEqual(queued.call_args.args[1], analysis_worker.BATCH_SIZE)
        self.assertEqual(process.call_count, 2)

    def test_retry_route_returns_status_for_frontend(self):
        app.dependency_overrides[selected_company] = lambda: "U_44564"
        try:
            with patch("app.api.routes.analyses.analysis_service.retry_analysis", return_value={
                "analysis_id": "analysis_test",
                "status": "queued",
                "company_id": "U_44564",
                "news_id": "news_test",
                "role": "cfo",
                "result": None,
                "error_code": None,
                "attempt_count": 1,
            }) as retry, TestClient(app) as client:
                response = client.post("/api/v1/analyses/analysis_test/retry")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "queued")
            retry.assert_called_once_with("analysis_test", "U_44564")
        finally:
            app.dependency_overrides.pop(selected_company, None)
