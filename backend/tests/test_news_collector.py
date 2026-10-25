"""Offline collector tests; fixtures are synthetic, never published to a working DB."""

from pathlib import Path
import socket
import sys
from datetime import datetime, timezone
from unittest import TestCase, main
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import Settings
from app.parsers.sources import SOURCES, CollectionError
from app.parsers.rss_parser import rss_items, parse_item
from app.parsers.article_extractor import extract_article
from app.parsers.http_client import NewsHTTPClient, Response, robots_rules, public_addresses
from app.parsers.collector import collect
from app.services.errors import ServiceError

FIXTURES = Path(__file__).parent / 'fixtures' / 'news'
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def fixture(name):
    return (FIXTURES / name).read_bytes()


class CollectorTests(TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None)
        self.enterContext(patch('psycopg.connect', side_effect=AssertionError('Working DB forbidden')))
        self.enterContext(patch('socket.create_connection', side_effect=AssertionError('Network forbidden')))

    def client(self, code):
        client = Mock(spec=NewsHTTPClient)
        values = [Response(200, fixture(code + '.xml'), {}, SOURCES[code].feed_url)]
        if code != 'cbr':
            values.append(Response(200, fixture(code + '.html.txt'), {}, 'https://unused'))
        client.get.side_effect = values
        return client

    def test_three_sources_normalize_and_dry_run_never_writes(self):
        with patch('app.parsers.collector.news_service.save_news') as save:
            for code in SOURCES:
                with self.subTest(code=code):
                    report = collect([code], self.settings, dry_run=True, now=NOW, client=self.client(code))
                    item = report['sources'][0]['items'][0]
                    self.assertEqual(report['sources'][0]['accepted'], 1)
                    self.assertFalse(item['is_synthetic'])
                    self.assertGreater(item['text_chars'], 120)
                    self.assertTrue(item['url'].startswith('https://'))
                    self.assertTrue(item['published_at'].endswith('+00:00'))
            save.assert_not_called()

    def test_clean_article_requires_right_scope_and_title(self):
        for code in ['minfin', 'fns']:
            text = extract_article(fixture(code + '.html.txt'), code, '[ТЕСТ XML] Налоговая отчётность')
            self.assertNotIn('Не включать', text)
            self.assertNotIn('unwanted_script', text)
            self.assertEqual(text.count('Это синтетический текст HTML фикстуры'), 1)
        for html in [b'<h1>Access denied</h1>', b'<h1>Title</h1><body><p>Menu only</p></body>']:
            with self.assertRaises(CollectionError):
                extract_article(html, 'fns', 'Title')

    def test_identity_dates_and_untrusted_xml(self):
        body = fixture('cbr.xml')
        first = parse_item(rss_items(body)[0], SOURCES['cbr'])
        changed = body.replace(b'fixture-cbr', b'different-guid').replace('Условия финансирования бизнеса'.encode(), 'Исправленный заголовок'.encode())
        self.assertEqual(first.id, parse_item(rss_items(changed)[0], SOURCES['cbr']).id)
        self.assertEqual(first.published_at.hour, 9)
        for invalid in [b'broken xml', b'<!DOCTYPE rss><rss/>', '<!DOCTYPE rss><rss/>'.encode('utf-16'), b'<html/>']:
            with self.assertRaises(CollectionError):
                rss_items(invalid)
        with self.assertRaises(CollectionError):
            parse_item(rss_items(body.replace(b' +0300', b''))[0], SOURCES['cbr'])
        missing = body.replace(b'<pubDate>Sat, 24 Oct 2026 12:00:00 +0300</pubDate>', b'')
        self.assertIsNone(parse_item(rss_items(missing)[0], SOURCES['cbr']).published_at)

    def test_filters_limits_and_conflicts_continue(self):
        body = fixture('cbr.xml')
        item = rss_items(body)[0]
        second = body.replace(b'test-fixture.htm', b'test-next.htm')
        joined = body.replace(b'</channel>', second.split(b'<channel>')[1].split(b'</channel>')[0] + b'</channel>')
        client = Mock(spec=NewsHTTPClient)
        client.get.return_value = Response(200, joined, {}, SOURCES['cbr'].feed_url)
        with patch('app.parsers.collector.news_service.save_news', side_effect=[ServiceError(409, 'NEWS_CONFLICT', 'conflict'), parse_item(item, SOURCES['cbr'])]) as save:
            result = collect(['cbr'], self.settings, limit=2, client=client, now=NOW)['sources'][0]
            self.assertEqual(result['conflicts'], 1)
            self.assertEqual(result['stored_or_existing'], 1)
            self.assertEqual(save.call_count, 2)
        for options in [{'keywords': ('несуществующая тема',)}, {'max_age_days': 1, 'now': datetime(2026, 11, 1, tzinfo=timezone.utc)}]:
            result = collect(['cbr'], self.settings, dry_run=True, client=client, **({'now': NOW} | options))['sources'][0]
            self.assertEqual(result['accepted'], 0)
        result = collect(['cbr'], self.settings, limit=1, dry_run=True, client=client, now=NOW)['sources'][0]
        self.assertEqual(result['inspected'], 1)

    def test_http_status_timeout_and_invalid_xml_are_reported(self):
        for error in [CollectionError('HTTP_STATUS', 403), CollectionError('HTTP_STATUS', 429, '120'), CollectionError('HTTP_STATUS', 500), CollectionError('TIMEOUT')]:
            client = Mock(spec=NewsHTTPClient)
            client.get.side_effect = error
            result = collect(['cbr'], self.settings, client=client, dry_run=True, now=NOW)['sources'][0]
            self.assertEqual(result['errors'][0]['code'], error.code)
            client.get.assert_called_once()
        client.get.side_effect = None
        client.get.return_value = Response(200, b'<rss>', {}, 'unused')
        result = collect(['cbr'], self.settings, client=client, dry_run=True)['sources'][0]
        self.assertEqual(result['errors'][0]['code'], 'INVALID_XML')

    def test_robots_wildcards_precedence_and_source_stop(self):
        rules = 'User-agent: *\nDisallow: /?\nDisallow: /blocked*\nAllow: /blocked/rss$\nCrawl-delay: 2'
        self.assertEqual(robots_rules(rules, 'Collector', 'https://example.org/rss'), (True, 2))
        self.assertFalse(robots_rules(rules, 'Collector', 'https://example.org/blocked/a')[0])
        self.assertTrue(robots_rules(rules, 'Collector', 'https://example.org/blocked/rss')[0])
        special = rules + '\nUser-agent: Collector\nDisallow: /\n'
        self.assertFalse(robots_rules(special, 'Collector/1.0', 'https://example.org/rss')[0])
        client = NewsHTTPClient(self.settings)
        url = SOURCES['cbr'].feed_url
        with patch.object(client, '_request', return_value=Response(200, b'User-agent: *\nDisallow: /rss/', {}, url)) as request:
            with self.assertRaisesRegex(CollectionError, 'ROBOTS_DENIED'):
                client.get(url, SOURCES['cbr'], feed=True)
            request.assert_called_once()
        blocked = Mock(spec=NewsHTTPClient)
        blocked.get.side_effect = [Response(200, fixture('fns.xml'), {}, 'unused'), CollectionError('HTTP_STATUS', 429, '30')]
        result = collect(['fns'], self.settings, client=blocked, dry_run=True, now=NOW)['sources'][0]
        self.assertEqual(result['errors'][0]['retry_after'], '30')

    def test_url_redirect_and_dns_restrictions(self):
        for url in ['https://127.0.0.1/rss', 'https://www.cbr.ru.evil.test/rss/RssPress', 'https://a:b@www.cbr.ru/press/PR/', 'https://www.cbr.ru:8443/press/PR/', 'https://www.cbr.ru/search/']:
            with self.assertRaises(CollectionError):
                SOURCES['cbr'].url(url)
        with patch('socket.getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaisesRegex(CollectionError, 'PRIVATE_ADDRESS'):
                public_addresses('www.cbr.ru')
        client = NewsHTTPClient(self.settings)
        with patch.object(client, '_check_robots'), patch.object(client, '_request', return_value=Response(302, b'', {'location': 'https://localhost/private'}, 'unused')) as request:
            with self.assertRaises(CollectionError):
                client.get(SOURCES['cbr'].feed_url, SOURCES['cbr'], feed=True)
            request.assert_called_once()

    def test_transport_enforces_size_timeout_and_retry_after(self):
        client = NewsHTTPClient(self.settings)
        url = SOURCES['cbr'].feed_url
        conn = Mock()
        response = conn.getresponse.return_value
        response.status = 200
        response.getheaders.return_value = [('Content-Length', '9999999')]
        with patch('app.parsers.http_client.public_addresses', return_value=['93.184.216.34']), patch('http.client.HTTPSConnection', return_value=conn):
            with self.assertRaisesRegex(CollectionError, 'RESPONSE_TOO_LARGE'):
                client._request(url, 1000)
            response.getheaders.return_value = []
            response.read1.side_effect = [b'x' * 1001]
            with self.assertRaisesRegex(CollectionError, 'RESPONSE_TOO_LARGE'):
                client._request(url, 1000)
            conn.request.side_effect = TimeoutError()
            with self.assertRaisesRegex(CollectionError, 'TIMEOUT'):
                client._request(url, 1000)
        with patch.object(client, '_check_robots'), patch.object(client, '_request', return_value=Response(429, b'', {'retry-after': '120'}, url)):
            with self.assertRaises(CollectionError) as caught:
                client.get(url, SOURCES['cbr'], feed=True)
            self.assertEqual(caught.exception.retry_after, '120')


if __name__ == '__main__':
    main()
