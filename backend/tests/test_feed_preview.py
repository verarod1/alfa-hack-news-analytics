"""A news card preview must stay factual before personalized analysis."""

import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import news_service


class FeedPreviewTests(TestCase):
    def test_archive_notice_is_labeled_and_not_used_as_excerpt(self):
        excerpt, archived = news_service.news_excerpt(
            news_service.ARCHIVE_NOTICE + "\n\nНалоговая служба рассказала о личном кабинете."
        )
        self.assertTrue(archived)
        self.assertEqual(excerpt, "Налоговая служба рассказала о личном кабинете.")

    def test_feed_uses_source_text_without_inventing_impact(self):
        row = {
            "id": "news_test", "title": "Банк России сохранил ключевую ставку",
            "text": "Совет директоров Банка России сохранил ключевую ставку на уровне 14%.",
            "published_at": None, "created_at": "2026-10-25T00:00:00+00:00",
            "source_id": "cbr", "source_name": "Банк России",
            "source_url": "https://www.cbr.ru/news/", "is_synthetic": False,
            "result": None, "score": None, "reasons": [], "analysis_id": None,
        }
        with patch.object(news_service, "require_client_company"), patch.object(
            news_service.news_repository, "get_feed", return_value=([row], 1, 0)
        ):
            feed = news_service.get_feed("U_44564", "cfo", None, 20, 0)
        item = feed["items"][0]
        self.assertEqual(item["topic_label"], "Ключевая ставка")
        self.assertIn("14%", item["excerpt"])
        self.assertIsNone(item["impact_type"])
        self.assertIsNone(item["short_insight"])
