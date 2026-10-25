"""One bounded collection run. --dry-run performs no database operations."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from app.parsers.collector import collect
from app.parsers.sources import SOURCES, CollectionError
from app.settings import Settings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=[*SOURCES, "all"], default=None)
    parser.add_argument("--limit", type=int, help="RSS items inspected per source, 1..100")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keywords", help="Comma-separated substrings, OR; default from env")
    parser.add_argument("--max-age-days", type=int, help="0 disables age filter; default 30")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        enabled = [s.strip() for s in settings.news_sources.split(",") if s.strip()]
        if not enabled or any(s not in SOURCES for s in enabled):
            raise CollectionError("INVALID_NEWS_SOURCES")
        codes = enabled if args.source in (None, "all") else [args.source]
        if any(code not in enabled for code in codes):
            raise CollectionError("SOURCE_DISABLED")
        words = settings.news_keywords if args.keywords is None else args.keywords
        report = collect(
            list(dict.fromkeys(codes)), settings, limit=args.limit, dry_run=args.dry_run,
            keywords=tuple(w.strip() for w in words.split(",") if w.strip()),
            max_age_days=args.max_age_days,
        )
    except (ValidationError, CollectionError):
        print(json.dumps({"error": "INVALID_COLLECTOR_CONFIG"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if any(s["errors"] for s in report["sources"]) else 0


if __name__ == "__main__":
    sys.exit(main())
