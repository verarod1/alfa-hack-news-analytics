"""Only the three official sources reviewed for this MVP. No arbitrary URL input."""

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


class CollectionError(ValueError):
    def __init__(self, code, status=None, retry_after=None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class Source:
    code: str
    name: str
    feed_url: str
    hosts: tuple[str, ...]
    article_pattern: str

    def url(self, value, *, feed=False):
        try:
            parsed = urlsplit(value.strip())
            if (
                len(value) > 4096
                or parsed.scheme not in ("http", "https")
                or parsed.hostname not in self.hosts
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443 if parsed.scheme == "https" else 80)
                or any(c.isspace() or ord(c) < 32 for c in value)
                or "\\" in value
            ):
                raise ValueError
            if feed:
                expected = urlsplit(self.feed_url)
                if (parsed.path, parsed.query) != (expected.path, expected.query):
                    raise ValueError
            elif not re.fullmatch(self.article_pattern, parsed.path):
                raise ValueError
            # Known official hosts support HTTPS. Never follow a downgrade redirect.
            return urlunsplit(("https", parsed.hostname, parsed.path or "/", parsed.query, ""))
        except (ValueError, AttributeError):
            raise CollectionError("URL_NOT_ALLOWED") from None

    def news_id(self, url):
        # The publication URL, not its title/date/GUID, defines update identity.
        parsed = urlsplit(self.url(url))
        identity = self.code + parsed.path + ("?" + parsed.query if parsed.query else "")
        return "news_" + self.code + "_" + hashlib.sha256(identity.encode()).hexdigest()[:32]


SOURCES = {
    "cbr": Source(
        "cbr", "Банк России", "https://www.cbr.ru/rss/RssPress",
        ("www.cbr.ru", "cbr.ru"), r"/press/(?:PR|pr|event)/?",
    ),
    "minfin": Source(
        "minfin", "Минфин России", "https://minfin.gov.ru/rss_news?mod=news&lim=50",
        ("minfin.gov.ru",), r"/ru/press-center/",
    ),
    "fns": Source(
        "fns", "ФНС России", "https://www.nalog.gov.ru/rn77/rss/",
        ("www.nalog.gov.ru", "nalog.gov.ru"), r"/rn\d{2}/news/[^/]+/\d+/?",
    ),
}
