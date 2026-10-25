"""Manual ingestion into the existing news service; never invokes ML or migrations."""

from datetime import datetime, timedelta, timezone

import psycopg

from app.database import DatabaseConfigError
from app.parsers.article_extractor import extract_article, substantive
from app.parsers.http_client import NewsHTTPClient
from app.parsers.rss_parser import rss_items, parse_item
from app.parsers.sources import SOURCES, CollectionError
from app.services import news_service
from app.services.errors import ServiceError


def collect(source_codes, settings, *, limit=None, dry_run=False, keywords=(), max_age_days=None,
            client=None, now=None):
    client = client or NewsHTTPClient(settings)
    now = now or datetime.now(timezone.utc)
    limit = settings.news_limit if limit is None else limit
    max_age_days = settings.news_max_age_days if max_age_days is None else max_age_days
    if not 1 <= limit <= 100 or not 0 <= max_age_days <= 3650:
        raise CollectionError("INVALID_OPTIONS")
    report = {"dry_run": dry_run, "sources": [], "database_error": False}
    for code in source_codes:
        source = SOURCES[code]
        result = {"source": code, "inspected": 0, "filtered": 0, "accepted": 0,
                  "stored_or_existing": 0, "conflicts": 0, "errors": [], "warnings": [], "items": []}
        report["sources"].append(result)
        if not source.collection_allowed:
            result["errors"].append({"code": "SOURCE_RIGHTS_REQUIRED", "http_status": None, "retry_after": None})
            result["warnings"].append("RSS availability does not grant storage/republication rights; source skipped")
            continue
        try:
            feed_url = getattr(settings, "news_" + code + "_rss_url")
            response = client.get(feed_url, source, feed=True)
            entries = rss_items(response.body)
            result["rss_total"] = len(entries)
            result["rss_http_status"] = response.status
            if not entries:
                result["warnings"].append("EMPTY_FEED")
            items = entries[:limit]
        except CollectionError as error:
            result["errors"].append(error_data(error))
            continue
        for item in items:
            result["inspected"] += 1
            try:
                news = parse_item(item, source)
                if news.published_at is None:
                    result["warnings"].append("PUBLICATION_DATE_MISSING")
                if news.published_at and (
                    news.published_at > now + timedelta(days=1)
                    or (max_age_days and news.published_at < now - timedelta(days=max_age_days))
                ):
                    result["filtered"] += 1
                    continue
                if code != "cbr":
                    article = client.get(news.source_url, source)
                    text = extract_article(article.body, code, news.title, settings.news_min_text_chars)
                    news = news.model_copy(update={"text": text})
                if not substantive(news.text or "", settings.news_min_text_chars):
                    raise CollectionError("ARTICLE_TEXT_MISSING")
                if keywords and not any(k.casefold() in (news.title + " " + news.text).casefold() for k in keywords):
                    result["filtered"] += 1
                    continue
                result["accepted"] += 1
                if not dry_run:
                    saved = news_service.save_news(news)
                    result["stored_or_existing"] += 1
                    saved_id = saved.id
                else:
                    saved_id = news.id
                result["items"].append({
                    "id": saved_id, "title": news.title, "url": news.source_url,
                    "published_at": news.published_at.isoformat() if news.published_at else None,
                    "text_chars": len(news.text), "is_synthetic": False,
                })
            except CollectionError as error:
                result["errors"].append(error_data(error))
                # Access/rate restrictions stop this source; no retry of another article.
                if (
                    error.status in (401, 403, 429)
                    or (error.status is not None and error.status >= 500)
                    or error.code.startswith("ROBOTS")
                    or error.code in ("TIMEOUT", "TLS_ERROR", "DNS_ERROR", "HTTP_PROTOCOL_ERROR")
                ):
                    break
            except ServiceError as error:
                if error.code == "NEWS_CONFLICT":
                    result["conflicts"] += 1
                    result["errors"].append({"code": "NEWS_CONFLICT"})
                else:
                    result["errors"].append({"code": error.code})
            except (psycopg.Error, DatabaseConfigError):
                result["errors"].append({"code": "DATABASE_UNAVAILABLE"})
                report["database_error"] = True
                return report
    return report


def error_data(error):
    # Never log raw exceptions, connection strings or complete HTML responses.
    return {"code": error.code, "http_status": error.status, "retry_after": error.retry_after}
