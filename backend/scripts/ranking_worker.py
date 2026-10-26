"""Opt-in ranking of persisted real news for configured companies and roles."""
import argparse
import logging
from pathlib import Path
import signal
import sys
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_connection
from app.repositories.news_repository import list_unranked_news
from app.services import ml_gateway
from app.services.client_context import require_demo_company
from app.services.profile_service import ROLES
from app.settings import Settings
from scripts.rank_news import rank_rows

logger = logging.getLogger("news_ranker")


def run_once():
    settings = Settings()
    report = {"saved": [], "failed": [], "skipped": None}
    if not settings.news_rank_enabled or not ml_gateway.configured():
        report["skipped"] = "RANKING_DISABLED"
        return report
    # Session lock prevents duplicate LLM calls from concurrent workers.
    with get_connection() as lock:
        if not lock.execute("SELECT pg_try_advisory_lock(72611026)").fetchone()[0]:
            report["skipped"] = "WORKER_BUSY"
            return report
        try:
            for company_id in settings.company_ids():
                try:
                    company = require_demo_company(company_id)
                    for role in ROLES:
                        rows = list_unranked_news(company_id, role["code"],
                                                  settings.news_rank_limit,
                                                  settings.news_max_age_days)
                        result = rank_rows(company, role["code"], rows)
                        for key in ("saved", "failed"):
                            report[key].extend(result[key])
                except Exception as error:
                    logger.error("company=%s ranking_failed=%s", company_id, type(error).__name__)
                    report["failed"].append(company_id)
        finally:
            lock.execute("SELECT pg_advisory_unlock(72611026)")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    interval = 600
    while not stop.is_set():
        try:
            interval = Settings().news_rank_poll_seconds
            report = run_once()
            logger.info("saved=%s failed=%s skipped=%s", len(report["saved"]),
                        len(report["failed"]), report["skipped"])
            if args.once:
                return int(bool(report["failed"]) or report["skipped"] == "RANKING_DISABLED")
        except Exception as error:
            logger.error("Ranking failed: %s", type(error).__name__)
            if args.once:
                return 1
        stop.wait(interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
