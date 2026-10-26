"""No external LLM or working database is contacted by these tests."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import ranking_worker, rank_news


class RankingWorkerTests(TestCase):
    def test_disabled_by_default_without_database_or_llm(self):
        with patch.dict(os.environ, {'NEWS_RANK_ENABLED': 'false'}), patch.object(ranking_worker, 'get_connection') as connection, patch.object(ranking_worker, 'rank_rows') as rank:
            self.assertEqual(ranking_worker.run_once()['skipped'], 'RANKING_DISABLED')
        connection.assert_not_called()
        rank.assert_not_called()

    def test_all_companies_and_roles_use_persistent_backlog(self):
        lock = MagicMock()
        lock.execute.return_value.fetchone.return_value = (True,)
        with patch.dict(os.environ, {'NEWS_RANK_ENABLED': 'true', 'DEMO_COMPANY_IDS': 'U_a,U_b', 'NEWS_RANK_LIMIT': '2', 'NEWS_MAX_AGE_DAYS': '30'}), patch.object(ranking_worker.ml_gateway, 'configured', return_value=True), patch.object(ranking_worker, 'get_connection') as connection, patch.object(ranking_worker, 'require_demo_company', side_effect=lambda cid: SimpleNamespace(id=cid)), patch.object(ranking_worker, 'list_unranked_news', return_value=[{'id': 'real'}]) as backlog, patch.object(ranking_worker, 'rank_rows', return_value={'saved': ['real'], 'failed': []}) as rank:
            connection.return_value.__enter__.return_value = lock
            report = ranking_worker.run_once()
        self.assertEqual(report['saved'], ['real'] * 4)
        self.assertEqual(backlog.call_count, 4)
        self.assertEqual(rank.call_count, 4)
        self.assertEqual({call.args[:2] for call in backlog.call_args_list},
                         {('U_a', 'ceo'), ('U_a', 'cfo'), ('U_b', 'ceo'), ('U_b', 'cfo')})
        self.assertTrue(all(call.args[2:] == (2, 30) for call in backlog.call_args_list))
        self.assertIn('pg_advisory_unlock', lock.execute.call_args.args[0])

    def test_busy_worker_does_not_rank(self):
        lock = MagicMock()
        lock.execute.return_value.fetchone.return_value = (False,)
        with patch.dict(os.environ, {'NEWS_RANK_ENABLED': 'true'}), patch.object(ranking_worker.ml_gateway, 'configured', return_value=True), patch.object(ranking_worker, 'get_connection') as connection, patch.object(ranking_worker, 'rank_rows') as rank:
            connection.return_value.__enter__.return_value = lock
            self.assertEqual(ranking_worker.run_once()['skipped'], 'WORKER_BUSY')
        rank.assert_not_called()

    def test_ranker_cannot_save_score_for_another_news(self):
        from app.services.company_mapper import map_company
        from app.schemas.company import CompanyResponse
        company = CompanyResponse.model_validate(map_company({'SYNTHETIC_U': 'U_test', 'CL_TYPE': 'CLIENT'}))
        row = {'id': 'real', 'title': 'Test', 'text': 'Text', 'published_at': None,
               'created_at': '2026-10-26T00:00:00Z', 'source_id': 'cbr',
               'source_name': 'CBR', 'source_url': 'https://www.cbr.ru/', 'is_synthetic': False}
        output = {'company_id': 'U_test', 'role': 'cfo', 'news_id': 'other',
                  'relevance_score': .8, 'relevance_reasons': ['Test'],
                  'method': 'test', 'method_version': '1'}
        with patch.object(rank_news.ml_gateway, 'rank', return_value=output), patch.object(rank_news.news_service, 'save_relevance') as save:
            self.assertEqual(rank_news.rank_rows(company, 'cfo', [row]), {'saved': [], 'failed': ['real']})
        save.assert_not_called()
