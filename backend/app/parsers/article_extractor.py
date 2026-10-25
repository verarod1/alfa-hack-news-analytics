"""Source-specific HTML extraction. Never use the whole page as article text."""

from bs4 import BeautifulSoup

from app.parsers.sources import CollectionError


SELECTORS = {
    "interfax": ("[itemprop=articleBody]", "article"),
    "finmarket": ("[itemprop=articleBody]", ".newsbody", "article"),
    "minfin": (
        "[itemprop='articleBody']", ".news_detail", ".news-detail",
        ".news-detail-text", ".document-page", ".content_body", "article",
    ),
    "fns": (
        ".page-content__center .text_block",
        "[itemprop='articleBody']", ".news_text", ".news-text",
        ".news__text", ".news-detail", "article",
    ),
}
TECHNICAL = (
    "access denied", "checking your browser", "just a moment", "verify you are human",
    "доступ ограничен", "доступ запрещен", "страница не найдена", "404 not found",
    "подтвердите, что вы не робот",
)


def clean_text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    for node in soup.select("script, style, nav, header, footer, aside, form, noscript, iframe, svg"):
        node.decompose()
    lines = [" ".join(line.split()) for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


def substantive(text, minimum):
    if len(text) < minimum or sum(c.isalpha() for c in text) < minimum // 2:
        return False
    return not any(marker in text.casefold() for marker in TECHNICAL)


def extract_article(body, source_code, expected_title, minimum=120):
    encoding = None
    if source_code == "finmarket" and isinstance(body, bytes):
        encoding = "utf-8" if b"utf-8" in body[:4096].lower() or body.startswith(b"\xef\xbb\xbf") else "windows-1251"
    soup = BeautifulSoup(body, "html.parser", from_encoding=encoding)
    heading = soup.find("h1")
    actual_title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
    expected = " ".join(expected_title.split()).casefold()
    if (
        not actual_title
        or any(marker in actual_title.casefold() for marker in TECHNICAL)
        or expected not in actual_title.casefold()
    ):
        raise CollectionError("ARTICLE_TITLE_MISMATCH")
    for selector in SELECTORS[source_code]:
        for root in soup.select(selector):
            # Mutate a copy: a rejected broad candidate must not affect the next selector.
            root = BeautifulSoup(str(root), "html.parser")
            for node in root.select("h1, script, style, nav, header, footer, aside, form, .share, .social, .subscribe"):
                node.decompose()
            # Some official HTML contains nested <p>. Do not duplicate an entire
            # article once as the parent paragraph and again as its children.
            paragraphs = [
                clean_text(str(node)) for node in root.select("p, li, h2, h3")
                if node.find(["p", "li", "h2", "h3"]) is None
            ]
            text = "\n\n".join(dict.fromkeys(p for p in paragraphs if p))
            if substantive(text, minimum):
                return text
    raise CollectionError("ARTICLE_TEXT_MISSING")
