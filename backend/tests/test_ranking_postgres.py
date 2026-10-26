"""Run only against an explicitly created disposable alfa_rank_test_* database."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest import TestCase, skipUnless
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import get_connection
from app.repositories import news_repository
from app.schemas.company import CompanyResponse
from app.schemas.news import NewsInput, RelevanceAssessment
from app.services import news_service
from app.services.company_mapper import map_company
from scripts import ranking_worker


@skipUnless(os.getenv('RANKING_TEST_DATABASE'), 'Requires disposable ranking test database')
class RankingPostgresTests(TestCase):
    def test_persisted_news_ranking_and_feed(self):
        database = os.environ['RANKING_TEST_DATABASE']
        if not database.startswith('alfa_rank_test_') or not database.replace('_', '').isalnum():
            raise RuntimeError('Refusing non-test database')
        with patch.dict(os.environ, {'DATABASE_URL': '', 'POSTGRES_DB': database,
                                     'NEWS_RANK_ENABLED': 'true', 'DEMO_COMPANY_IDS': 'U_test',
                                     'FEED_INCLUDE_SYNTHETIC': 'false', 'NEWS_MAX_AGE_DAYS': '30'}):
            with get_connection() as conn:
                self.assertEqual(conn.execute('SELECT current_database()').fetchone()[0], database)
                conn.execute((Path(__file__).resolve().parents[1] / 'db/mvp.sql').read_text(encoding='utf-8'))
            now = datetime.now(timezone.utc)
            for nid, synthetic, date in [('real', False, now), ('demo', True, now),
                                         ('old', False, now - timedelta(days=90))]:
                news_service.save_news(NewsInput(id=nid, title=nid, text='Test publication',
                                                 is_synthetic=synthetic, published_at=date))
            # An old high demo score must not hide the actual publication.
            news_repository.save_relevance(RelevanceAssessment(
                company_id='U_test', role='cfo', news_id='demo', relevance_score=1,
                relevance_reasons=['Test'], method='test', method_version='1'))
            self.assertEqual([n['id'] for n in news_repository.list_unranked_news('U_test', 'cfo', 3, 30)], ['real'])
            company = CompanyResponse.model_validate(map_company({'SYNTHETIC_U': 'U_test', 'CL_TYPE': 'CLIENT'}))
            def score(context):
                return {'company_id': 'U_test', 'role': context['role'], 'news_id': context['news']['id'],
                        'relevance_score': .8, 'relevance_reasons': ['Test'], 'method': 'test', 'method_version': '1'}
            with patch.object(ranking_worker.ml_gateway, 'configured', return_value=True), patch.object(ranking_worker, 'require_demo_company', return_value=company), patch.object(news_service, 'require_client_company', return_value=company), patch.object(ranking_worker.ml_gateway, 'rank', side_effect=score) as rank:
                self.assertEqual(ranking_worker.run_once()['saved'], ['real', 'real'])
                self.assertEqual(ranking_worker.run_once()['saved'], [])
                self.assertEqual(rank.call_count, 2)
                feed = news_service.get_feed('U_test', 'cfo', None, 20, 0)
                self.assertEqual(feed['scored_total'], 1)
                self.assertEqual(feed['ranking_mode'], 'relevance')
                self.assertEqual(feed['items'][0]['id'], 'real')
                self.assertNotIn('demo', [item['id'] for item in feed['items']])
                self.assertEqual(feed['total'], 2)
