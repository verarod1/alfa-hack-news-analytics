"""Strict bounded RSS parsing without DTD/entities or naive publication times."""

import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

from app.parsers.article_extractor import clean_text
from app.parsers.sources import CollectionError
from app.schemas.news import NewsInput


def rss_items(body):
    if len(body) > 5_000_000:
        raise CollectionError("RESPONSE_TOO_LARGE")
    # XML supports UTF-16/32: remove NUL bytes for declaration detection as well.
    declarations = body.replace(b"\0", b"").lower()
    if b"<!doctype" in declarations or b"<!entity" in declarations:
        raise CollectionError("UNSAFE_XML")
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, ValueError):
        raise CollectionError("INVALID_XML") from None
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    if root.tag != "rss" or root.find("channel") is None:
        raise CollectionError("NOT_RSS")
    return root.findall("./channel/item")


def parse_item(item, source):
    title = clean_text(item.findtext("title") or "")
    url = source.url(item.findtext("link") or "")
    if not title:
        raise CollectionError("EMPTY_TITLE")
    date_text = item.findtext("pubDate")
    date = None
    if date_text and date_text.strip():
        try:
            date = parsedate_to_datetime(date_text.strip())
            if date.tzinfo is None or date.utcoffset() is None:
                raise ValueError
            date = date.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError):
            raise CollectionError("INVALID_DATE") from None
    text = clean_text(item.findtext("encoded") or item.findtext("description") or "")
    return NewsInput(
        id=source.news_id(url), title=title, text=text or None,
        published_at=date, source_id=source.code, source_name=source.name,
        source_url=url, is_synthetic=False,
    )
