"""Без сети, платных вызовов и рабочей PostgreSQL."""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import llm_client, ranker, rag


class MLIntegrationTests(TestCase):
    def test_ranker_requires_real_fields_and_valid_context(self):
        company = {"id": "U_test", "industry": {"code": "62.01"}}
        news = {"id": "news_test", "title": "[ТЕСТ] Налоги"}
        with patch.object(ranker, "call_llm", return_value='{}'), patch('app.services.news_service.save_relevance') as save:
            with self.assertRaises(KeyError):
                ranker.rank_news(company, 'cfo', news)
            save.assert_not_called()
        with patch.object(ranker, "call_llm", return_value=json.dumps({
            "relevance_score": .8, "relevance_reasons": ["[ТЕСТ] Финансовый контекст"],
        })), patch('app.services.news_service.save_relevance') as save:
            result = ranker.rank_news(company, 'cfo', news)
            self.assertEqual(result['relevance_score'], .8)
            save.assert_called_once()
            self.assertEqual(save.call_args.args[0].company_id, 'U_test')

    def test_llm_configuration_and_failures_are_not_fake_success(self):
        with patch.dict(os.environ, {'LLM_MODEL': 'GLM-5.3-Flash', 'LLM_RANK_MODEL': '',
                                     'LLM_MAX_TOKENS': '321', 'LLM_API_KEY': '', 'LLM_BASE_URL': ''}):
            create = Mock()
            client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
            create.return_value = SimpleNamespace(choices=[SimpleNamespace(
                finish_reason='stop', message=SimpleNamespace(content='{"ok": true}'))], usage=None)
            with patch.object(llm_client, 'get_client', return_value=client):
                self.assertEqual(json.loads(llm_client.call_llm('rank', 'test', force_json=True)), {'ok': True})
                self.assertEqual(create.call_args.kwargs['model'], 'z-ai/glm-5.3-flash')
                self.assertEqual(create.call_args.kwargs['max_tokens'], 321)
                create.side_effect = TimeoutError('test only')
                with self.assertRaises(TimeoutError):
                    llm_client.call_llm('generate', 'test')
            with patch.dict(os.environ, {'LLM_RANK_MODEL': 'unapproved'}):
                with self.assertRaises(ValueError):
                    llm_client.model_name('rank')

    def test_rag_incremental_pages_cache_and_new_pdf(self):
        # PDF/OCR/эмбеддинги имитируются; проверяются порядок и постоянные файлы кэша.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {'BANK_PDF_DIR': str(root / 'pdf'), 'CHROMA_DB_DIR': str(root / 'chroma'),
                   'OCR_CACHE_DIR': str(root / 'ocr'), 'BANK_MATERIALS_PATH': ''}
            (root / 'pdf').mkdir()
            (root / 'pdf' / 'one.pdf').write_bytes(b'not-real-pdf-test-one')
            document = Mock()
            document.__enter__ = Mock(return_value=[Mock(get_text=Mock(return_value='[ТЕСТ] Первая страница PDF')), Mock(get_text=Mock(return_value=''))])
            document.__exit__ = Mock(return_value=False)
            collection = Mock()
            with patch.dict(os.environ, env), patch.dict(sys.modules, {'pymupdf': SimpleNamespace(open=Mock(return_value=document))}), patch.object(rag, 'get_collection', return_value=collection), patch.object(rag, 'extract_with_qwen_vl', return_value='[ТЕСТ] Текст первой страницы') as ocr:
                self.assertEqual(rag.process_pdfs()['pending'], ['one.pdf'])
                ocr.assert_not_called()
                self.assertEqual(rag.process_pdfs(allow_ocr=True)['indexed'], ['one.pdf'])
                self.assertEqual(rag.process_pdfs(allow_ocr=True)['indexed'], [])
                self.assertEqual(ocr.call_count, 1)
                (root / 'pdf' / 'two.pdf').write_bytes(b'not-real-pdf-test-two')
                self.assertEqual(rag.process_pdfs(allow_ocr=True)['indexed'], ['two.pdf'])
                self.assertEqual(ocr.call_count, 2)
                manifest = json.loads(rag.manifest_path().read_text())
                self.assertEqual(len(manifest), 2)
                self.assertEqual([p['page'] for p in manifest[0]['pages']], [1, 2])
                self.assertNotEqual(manifest[0]['document_id'], manifest[1]['document_id'])
                self.assertEqual(collection.upsert.call_count, 4)

    def test_chat_uses_history_and_rejects_invented_sources(self):
        from team_ml import adapter
        context = {'company': {'id': 'U_test'}, 'role': 'cfo', 'news': {},
                   'history': [{'content': '[ТЕСТ] Предыдущий вопрос'}], 'message': 'Почему?',
                   'result': {'sources': [{'id': 'e_test'}]}}
        value = {'answer': '[ТЕСТ] Ответ', 'evidence_ids': ['e_test'],
                 'statement_type': 'model_inference', 'bank_opinion': None}
        with patch.object(adapter, 'call_llm', return_value=json.dumps(value)) as call:
            self.assertEqual(adapter.chat(context)['answer'], '[ТЕСТ] Ответ')
            self.assertIn('Предыдущий вопрос', call.call_args.args[1])
        value['evidence_ids'] = ['invented']
        with patch.object(adapter, 'call_llm', return_value=json.dumps(value)):
            with self.assertRaises(ValueError):
                adapter.chat(context)

    def test_analysis_accepts_only_confirmed_bank_page_quote(self):
        from datetime import datetime, timezone
        from team_ml import adapter
        from app.services.company_mapper import map_company
        from app.schemas.ml import AnalysisContext
        from ml_test_adapter import analyze
        context = AnalysisContext(
            analysis_id='test', role='cfo',
            company=map_company({'SYNTHETIC_U': 'U_test', 'CL_TYPE': 'CLIENT'}),
            news={'id': 'test_news', 'title': '[ТЕСТ] Ставка', 'source': {'url': None},
                  'is_synthetic': True, 'created_at': datetime.now(timezone.utc)},
            relations={'company_id': 'U_test', 'relations': {}, 'limit': 1, 'truncated': {}},
            bank_materials=[{'document_id': 'bank_test', 'title': '[ТЕСТ] Документ', 'url': None,
                             'pages': [{'page': 2, 'text': '[ТЕСТ] Проверяемая цитата банка.'}]}],
        ).model_dump(mode='json')
        output = analyze(context)
        output.pop('relevance')
        output['result']['sources'].append({
            'id': 'bank_e', 'type': 'bank_analytics', 'document_id': 'bank_test',
            'page': 2, 'quote': 'Проверяемая цитата банка.', 'url': None,
        })
        opinion = {'text': '[ТЕСТ] Позиция', 'document_id': 'bank_test', 'page': 2,
                   'quote': 'Проверяемая цитата банка.', 'evidence_ids': ['bank_e']}
        output['result']['bank_opinion'] = opinion
        chunks = [{'document_id': 'bank_test', 'document_title': '[ТЕСТ] Документ',
                   'page': 2, 'text': '[ТЕСТ] Проверяемая цитата банка.'}]
        with patch.object(adapter, 'retrieve_analytics', return_value=chunks), patch.object(adapter, 'call_llm', side_effect=lambda *a, **k: json.dumps(output)):
            self.assertEqual(adapter.analyze(context)['result']['bank_opinion']['page'], 2)
            # Одинаковая выдуманная цитата в opinion/source проходит ссылки DTO,
            # но должна быть отклонена проверкой фактического текста страницы.
            opinion['quote'] = 'Несуществующая цитата'
            output['result']['sources'][-1]['quote'] = opinion['quote']
            with self.assertRaises(ValueError):
                adapter.analyze(context)

    def test_chunking_has_no_infinite_loop(self):
        self.assertEqual(rag.chunk_text('12345678', 5, 1), ['12345', '5678'])
        with self.assertRaises(ValueError):
            rag.chunk_text('text', 5, 5)
