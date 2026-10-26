"""Ограниченный периодический RSS-сбор, без ML, миграций и очистки данных."""
import argparse
import logging
from pathlib import Path
import signal
import sys
from threading import Event
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.parsers.collector import collect
from app.parsers.sources import SOURCES
from app.settings import Settings

logger=logging.getLogger('news_collector')


def run_once():
    settings=Settings()
    codes=list(dict.fromkeys(code.strip() for code in settings.news_sources.split(',') if code.strip()))
    if not codes or any(code not in SOURCES for code in codes):
        raise ValueError('Invalid NEWS_SOURCES')
    report=collect(codes,settings,limit=min(settings.news_limit,5))
    for row in report['sources']:
        logger.info('source=%s stored_or_existing=%s errors=%s',row['source'],row['stored_or_existing'],[error['code'] for error in row['errors']])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    stop=Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    interval=1800
    while not stop.is_set():
        try:
            interval=Settings().news_poll_seconds
            result=run_once()
            if args.once:return int(result['database_error'] or any(row['errors'] for row in result['sources']))
        except Exception as error:
            # Не выводим исключения, содержащие DSN/пароли или HTML.
            logger.error('Collection failed: %s',type(error).__name__)
            if args.once:return 1
        stop.wait(interval)
    return 0


if __name__=='__main__':
    sys.exit(main())
