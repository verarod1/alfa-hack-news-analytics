"""Настоящий OpenAI SDK и subprocess gateway, только локальный HTTP stub вместо LLM."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest import TestCase, skipUnless
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import ml_gateway
from app.services.company_mapper import map_company
from app.schemas.ml import AnalysisContext
from app.schemas.chat import AgentChatReply
from app.schemas.news import RelevanceAssessment
from datetime import datetime, timezone
import ml_test_adapter


class StubLLM(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        context = json.loads(request['messages'][-1]['content'])
        if 'message' in context:
            value = ml_test_adapter.chat(context)
        elif 'relations' in context:
            value = ml_test_adapter.analyze(context)
            value.pop('relevance')
        else:
            value = {'relevance_score': .82, 'relevance_reasons': ['HTTP stub test, not model output']}
        body = json.dumps({'id': 'test-completion', 'object': 'chat.completion', 'created': 1,
                           'model': request['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                           'message': {'role': 'assistant', 'content': json.dumps(value)}}],
                           'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@skipUnless(importlib.util.find_spec('openai'), 'OpenAI SDK проверяется также внутри backend Docker')
class MLHTTPTests(TestCase):
    def test_real_sdk_gateway_rank_analysis_and_chat_without_paid_service(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), StubLLM)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(lambda: (server.shutdown(), thread.join(timeout=5)))
        with patch.dict(os.environ, {'ML_ADAPTER_MODULE': 'team_ml.adapter',
                                    'LLM_BASE_URL': f'http://127.0.0.1:{server.server_port}/v1',
                                    'LLM_API_KEY': 'offline-test-not-a-real-key',
                                    'LLM_MODEL': 'Gemma-4-26B-A4B', 'LLM_RANK_MODEL': '',
                                    'LLM_CHAT_MODEL': '', 'LLM_TIMEOUT_SECONDS': '15'}):
            context = AnalysisContext(
                analysis_id='http-test', role='cfo',
                company=map_company({'SYNTHETIC_U': 'U_test', 'CL_TYPE': 'CLIENT'}),
                news={'id': 'test_news', 'title': '[TEST] News', 'source': {'url': None},
                      'is_synthetic': True, 'created_at': datetime.now(timezone.utc)},
                relations={'company_id': 'U_test', 'relations': {}, 'limit': 1, 'truncated': {}},
            ).model_dump(mode='json')
            rank = RelevanceAssessment.model_validate(ml_gateway.rank(context))
            self.assertEqual(rank.relevance_score, .82)
            result = ml_gateway.analyze(context)['result']
            self.assertEqual(result['analyzed_news_ids'], ['test_news'])
            chat = AgentChatReply.model_validate(ml_gateway.chat({**context, 'result': result,
                                                                 'message': '[TEST] Why?', 'history': []}))
            self.assertEqual(chat.evidence_ids, ['e_test'])
