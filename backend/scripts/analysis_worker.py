"""Process analyses explicitly requested through the API.

Failed analyses stay failed until an operator explicitly retries them.
"""

import logging
import sys
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories.analysis_repository import queued_ids
from app.services.analysis_service import process_analysis
from app.services.errors import ServiceError
from app.services.ml_gateway import configured
from app.settings import Settings


logger = logging.getLogger("analysis_worker")
POLL_SECONDS = 3
BATCH_SIZE = 5


def run_once():
    settings = Settings()
    if not configured():
        return
    for analysis_id in queued_ids(settings.company_ids(), BATCH_SIZE):
        try:
            process_analysis(analysis_id)
            logger.info("Analysis %s completed", analysis_id)
        except ServiceError as error:
            # process_analysis persists the failed state; never retry automatically.
            logger.warning("Analysis %s: %s", analysis_id, error.code)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Analysis worker started")
    stop = Event()
    while not stop.is_set():
        try:
            run_once()
        except Exception as error:
            # Database outages and unexpected errors must not stop the worker.
            # The exception text may contain connection credentials, so log only its type.
            logger.error("Worker cycle failed: %s", type(error).__name__)
        stop.wait(POLL_SECONDS)


if __name__ == "__main__":
    main()
