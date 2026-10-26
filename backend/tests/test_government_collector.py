"""HTTP допустим только для проверенного официального канала Правительства."""
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.parsers.sources import SOURCES,CollectionError
from app.parsers.http_client import NewsHTTPClient,Response
from app.parsers.collector import collect
from app.settings import Settings

TITLE='[ТЕСТ] Инфраструктурный проект'
XML=f'<rss><channel><item><title>{TITLE}</title><link>http://government.ru/news/123/</link><pubDate>Sun, 25 Oct 2026 09:30:00 +0300</pubDate></item></channel></rss>'.encode()
HTML=('<h1>Новости</h1><h3 class="reader_article_headline">'+TITLE+'</h3><div class="reader_article_body"><p>'+('[ТЕСТ] Государственный инфраструктурный проект и условия финансирования. '*4)+'</p></div><footer>НЕ ТЕКСТ</footer>').encode()


class GovernmentCollectorTests(TestCase):
    def test_rss_text_service_and_timezone(self):
        source=SOURCES['government'];client=Mock()
        client.get.side_effect=[Response(200,XML,{},source.feed_url),Response(200,HTML,{},'article')]
        with patch('app.parsers.collector.news_service.save_news') as save:
            save.side_effect=lambda value:value
            result=collect(['government'],Settings(_env_file=None),client=client)
        row=result['sources'][0]
        self.assertFalse(row['errors']);self.assertEqual(row['stored_or_existing'],1)
        news=save.call_args.args[0]
        self.assertEqual(news.published_at.hour,6)
        self.assertNotIn('НЕ ТЕКСТ',news.text)
        self.assertTrue(news.source_url.startswith('http://government.ru/'))

    def test_http_exception_does_not_allow_cbr_downgrade_or_other_hosts(self):
        client=NewsHTTPClient(Settings(_env_file=None))
        with patch.object(client,'_check_robots'),patch.object(client,'_request',return_value=Response(302,b'',{'location':'http://www.cbr.ru/press/PR/'},'unused')):
            with self.assertRaises(CollectionError):client.get('https://www.cbr.ru/press/PR/',SOURCES['cbr'])
        for url in ['http://localhost/news/123/','http://government.ru:8080/news/123/','http://government.ru/private']:
            with self.assertRaises(CollectionError):SOURCES['government'].url(url)

    def test_http_uses_public_dns_port80_and_checks_robots(self):
        client=NewsHTTPClient(Settings(_env_file=None))
        response=Mock(status=200)
        response.getheaders.return_value=[]
        response.read1.side_effect=[b'body',b'']
        conn=Mock();conn.getresponse.return_value=response
        with patch('app.parsers.http_client.public_addresses',return_value=['93.184.216.34']) as dns,patch('http.client.HTTPConnection',return_value=conn) as http:
            self.assertEqual(client._request('http://government.ru/news/123/',1000).body,b'body')
        dns.assert_called_once_with('government.ru',80)
        http.assert_called_once_with('government.ru',timeout=20)
        with patch.object(client,'_request',return_value=Response(503,b'',{},'robots')) as request:
            with self.assertRaises(CollectionError):client.get(SOURCES['government'].feed_url,SOURCES['government'],feed=True)
            self.assertEqual(request.call_count,1)
