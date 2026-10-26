import os
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import news_worker


class NewsWorkerTests(TestCase):
    def test_limited_batch_uses_existing_collector(self):
        report={'database_error':False,'sources':[]}
        with patch.dict(os.environ,{'NEWS_SOURCES':'cbr,government','NEWS_LIMIT':'100'}),patch.object(news_worker,'collect',return_value=report) as collect:
            self.assertEqual(news_worker.run_once(),report)
        self.assertEqual(collect.call_args.args[0],['cbr','government'])
        self.assertEqual(collect.call_args.kwargs['limit'],5)

    def test_invalid_configuration_does_not_collect(self):
        with patch.dict(os.environ,{'NEWS_SOURCES':'unknown'}),patch.object(news_worker,'collect') as collect:
            with self.assertRaises(ValueError):news_worker.run_once()
        collect.assert_not_called()
