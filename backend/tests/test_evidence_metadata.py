"""Подписи ссылок берутся из проверенных серверных данных, не придумываются моделью."""
import sys
from pathlib import Path
from unittest import TestCase
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.evidence_service import verify_sources
from app.schemas.analysis import Evidence
from app.schemas.ml import BankDocument
from app.schemas.news import NewsResponse


class EvidenceMetadataTests(TestCase):
    def test_confirmed_titles_and_local_pdf_without_fake_url(self):
        news=NewsResponse(id='n_test',title='[ТЕСТ] Фактический заголовок',source={'url':'https://example.org/news'},is_synthetic=True,created_at='2026-10-26T00:00:00Z')
        doc=BankDocument(document_id='d_test',title='[ТЕСТ] Документ банка',pages=[{'page':2,'text':'[ТЕСТ] Проверяемая цитата.'}])
        sources=[Evidence(id='e_news',type='news',news_id=news.id,url=news.source.url,title='Неверный заголовок'),Evidence(id='e_bank',type='bank_analytics',document_id=doc.document_id,page=2,quote='Проверяемая цитата.',title='Неверный документ')]
        verify_sources(sources,news,[doc])
        self.assertEqual(sources[0].title,news.title)
        self.assertEqual(sources[1].document_title,doc.title)
        self.assertEqual(sources[1].title,doc.title)
        self.assertIsNone(sources[1].url)

    def test_made_up_document_url_is_rejected(self):
        news=NewsResponse(id='n',title='[ТЕСТ]',source={},is_synthetic=True,created_at='2026-10-26T00:00:00Z')
        doc=BankDocument(document_id='d',title='[ТЕСТ]',pages=[{'page':1,'text':'цитата'}])
        source=Evidence(id='e',type='bank_analytics',document_id='d',page=1,quote='цитата',url='https://example.org/invented.pdf')
        with self.assertRaises(ValueError):verify_sources([source],news,[doc])
