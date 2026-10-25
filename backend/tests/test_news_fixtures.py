"""Целевые проверки новых источников/локального импорта, без сети и рабочей БД."""
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.parsers.sources import SOURCES
from app.parsers.collector import collect
from app.parsers.rss_parser import rss_items
from app.parsers.article_extractor import extract_article
from app.settings import Settings
from scripts.import_news_fixtures import DEFAULT_FILE, import_fixtures, load_fixtures


class NewsFixturesTests(TestCase):
    def test_windows1251_rss_and_article(self):
        xml = '<?xml version="1.0" encoding="windows-1251"?><rss><channel><item><title>Финансы и налоги</title></item></channel></rss>'
        self.assertEqual(rss_items(xml.encode('cp1251'))[0].findtext('title'), 'Финансы и налоги')
        text = '[ТЕСТ] Финансирование предприятий и стоимость кредитования. ' * 4
        html = f'<html><meta charset="windows-1251"><h1>Тест</h1><article><p>{text}</p></article></html>'
        self.assertIn('Финансирование', extract_article(html.encode('cp1251'), 'finmarket', 'Тест'))

    def test_restricted_sources_never_download_or_save(self):
        client = Mock()
        with patch('app.parsers.collector.news_service.save_news') as save:
            result = collect(['interfax', 'finmarket'], Settings(_env_file=None), client=client)
        client.get.assert_not_called()
        save.assert_not_called()
        self.assertTrue(all(row['errors'][0]['code']=='SOURCE_RIGHTS_REQUIRED' for row in result['sources']))

    def test_real_fixture_metadata_and_dry_run(self):
        values = load_fixtures(DEFAULT_FILE)
        self.assertTrue(values)
        for value in values:
            self.assertFalse(value.is_synthetic)
            self.assertEqual(value.id, SOURCES[value.source_id].news_id(value.source_url))
            self.assertIsNotNone(value.published_at.utcoffset())
        with patch('scripts.import_news_fixtures.save_news') as save:
            self.assertEqual(import_fixtures(dry_run=True)['failed'], [])
            save.assert_not_called()

    def test_bad_fixture_rejected_before_any_write(self):
        values=json.loads(DEFAULT_FILE.read_text())
        values[-1]['text']=''
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'news.json';path.write_text(json.dumps(values))
            with patch('scripts.import_news_fixtures.save_news') as save:
                with self.assertRaises(ValueError):import_fixtures(path)
                save.assert_not_called()

    def test_conflict_is_reported_without_overwriting(self):
        with patch('scripts.import_news_fixtures.save_news', side_effect=ValueError('test conflict')):
            result=import_fixtures()
        self.assertFalse(result['stored_or_existing'])
        self.assertEqual(len(result['failed']),len(load_fixtures(DEFAULT_FILE)))
