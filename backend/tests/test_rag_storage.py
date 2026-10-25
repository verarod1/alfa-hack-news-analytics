"""Реальная Chroma/PDF в отдельном каталоге; embedding тестовый, сети и OCR нет."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase, skipUnless

AVAILABLE = all(importlib.util.find_spec(name) for name in ('chromadb', 'pymupdf'))

# Новый процесс имитирует пересоздание контейнера с теми же каталогами состояния.
CHILD = '''
import json
from unittest.mock import patch
import chromadb
from chromadb.api.types import EmbeddingFunction
from app.services import rag

class TestEmbedding(EmbeddingFunction):
    def __call__(self, input):
        return [[1.0, 0.0, 0.0] for _ in input]
    @staticmethod
    def name():
        return "offline-test-embedding"
    def get_config(self):
        return {}
    @staticmethod
    def build_from_config(config):
        return TestEmbedding()

client = chromadb.PersistentClient(path=str(rag.local_path(rag.Settings().chroma_db_dir)))
collection = client.get_or_create_collection("test_bank_pages", embedding_function=TestEmbedding())
with patch.object(rag, 'get_collection', return_value=collection), patch.object(
    rag, 'extract_with_qwen_vl', side_effect=AssertionError('Paid OCR forbidden')):
    result = rag.process_pdfs()
    result['chunks'] = collection.count()
    result['pages'] = sorted(set(item['page'] for item in collection.get()['metadatas']))
    print(json.dumps(result))
'''


@skipUnless(AVAILABLE, 'Нужны ML-зависимости: запускать также внутри собранного backend Docker')
class RAGStorageTests(TestCase):
    def test_new_process_preserves_chroma_and_cached_pages_and_adds_pdf(self):
        import pymupdf
        with tempfile.TemporaryDirectory(prefix='alfa-rag-isolated-') as directory:
            root = Path(directory)
            pdfs = root / 'pdf'
            pdfs.mkdir()
            with pymupdf.open() as doc:
                for number in (1, 2):
                    doc.new_page().insert_text((72, 72), f'TEST ONLY. Fixture page {number}. Not bank analytics.')
                doc.save(pdfs / 'one.pdf')
            env = dict(os.environ, BANK_PDF_DIR=str(pdfs), CHROMA_DB_DIR=str(root / 'chroma'),
                       OCR_CACHE_DIR=str(root / 'ocr'), BANK_MATERIALS_PATH='',
                       LLM_API_KEY='', HF_HUB_OFFLINE='1', ANONYMIZED_TELEMETRY='False', PYTHONDONTWRITEBYTECODE='1',
                       PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            def run():
                result = subprocess.run([sys.executable, '-B', '-c', CHILD], env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            first = run()
            self.assertEqual(first['chunks'], 2)
            self.assertEqual(first['pages'], [1, 2])
            original = {p.name: p.read_bytes() for p in (root / 'ocr').glob('*.json') if p.name != 'bank_materials.json'}
            second = run()
            self.assertEqual(second['indexed'], [])
            self.assertEqual(second['chunks'], 2)
            self.assertTrue(all((root / 'ocr' / name).read_bytes() == data for name, data in original.items()))
            with pymupdf.open() as doc:
                doc.new_page().insert_text((72, 72), 'TEST ONLY. New document, not real bank analytics.')
                doc.save(pdfs / 'two.pdf')
            third = run()
            self.assertEqual(third['indexed'], ['two.pdf'])
            self.assertEqual(third['documents'], 2)
            self.assertEqual(third['chunks'], 3)
