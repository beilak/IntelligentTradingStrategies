from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from its.db.models import RSSItem

FINAM_RSS_URLS = (
    "https://www.finam.ru/analysis/conews/rsspoint/",
    "https://www.finam.ru/analysis/nslent/rsspoint/",
    "https://www.finam.ru/analysis/forecasts/rsspoint/",
    "https://www.finam.ru/international/advanced/rsspoint/",
)

MOEX_RSS_URLS = (
    "https://www.moex.com/export/news.aspx?cat=100",
    "https://www.moex.com/export/news.aspx?cat=101",
    "https://www.moex.com/export/news.aspx?cat=102",
    "https://www.moex.com/export/news.aspx?cat=104",
    "https://www.moex.com/export/news.aspx?cat=122",
    "https://www.moex.com/export/news.aspx?cat=300",
)

CBR_RSS_URLS = (
    "https://www.cbr.ru/rss/RssNews",
    "https://www.cbr.ru/rss/eventrss",
    "https://www.cbr.ru/rss/RssPress",
    "https://www.cbr.ru/rss/RssCurrency",
    "https://www.cbr.ru/rss/nregimr2",
)

BFM_RSS_URLS = (
    "https://www.bfm.ru/news.rss?rubric=28",
)

CNBC_RSS_URLS = (
    "https://www.cnbc.com/id/20409666/device/rss/rss.html",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://www.cnbc.com/id/19832390/device/rss/rss.html",
)

INVESTING_RSS_URLS = (
    "https://www.investing.com/rss/news_25.rss",
    "https://ru.investing.com/rss/news_25.rss",
)

DEFAULT_RSS_URLS = (
    *FINAM_RSS_URLS,
    *MOEX_RSS_URLS,
    *CBR_RSS_URLS,
    *BFM_RSS_URLS,
    *CNBC_RSS_URLS,
    *INVESTING_RSS_URLS,
)


def get_default_rss_sources() -> list[str]:
    return sorted({normalize_source(feed_url) for feed_url in DEFAULT_RSS_URLS})


@dataclass(frozen=True)
class RSSFeedItem:
    pub_date: datetime
    title: str
    text: str
    source: str


@dataclass
class RSSLoadResult:
    feeds: list[str] = field(default_factory=list)
    parsed_items: int = 0
    saved_items: int = 0
    errors: list[str] = field(default_factory=list)


def load_rss_items_to_db(
    session: Session,
    feed_urls: list[str] | tuple[str, ...] = DEFAULT_RSS_URLS,
) -> RSSLoadResult:
    result = RSSLoadResult(feeds=list(feed_urls))
    items: list[RSSFeedItem] = []

    with httpx.Client(
        follow_redirects=True,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    ) as client:
        for feed_url in feed_urls:
            try:
                response = client.get(feed_url)
                response.raise_for_status()
                parsed_items = parse_rss_items(response.content, feed_url)
                result.parsed_items += len(parsed_items)
                items.extend(parsed_items)
            except (httpx.HTTPError, ElementTree.ParseError, ValueError) as error:
                result.errors.append(f"{feed_url}: {error}")

    result.saved_items = upsert_rss_items(session, items)
    return result


def parse_rss_items(content: bytes | str, source_url: str) -> list[RSSFeedItem]:
    root = ElementTree.fromstring(content)
    source = normalize_source(source_url)
    items: list[RSSFeedItem] = []

    for element in find_feed_entries(root):
        title = clean_text(find_child_text(element, "title"))
        text = clean_text(
            find_child_text(element, "description")
            or find_child_text(element, "encoded")
            or find_child_text(element, "full-text")
            or find_child_text(element, "content")
            or find_child_text(element, "summary")
        )
        pub_date = parse_pub_date(
            find_child_text(element, "pubDate")
            or find_child_text(element, "published")
            or find_child_text(element, "updated")
            or find_child_text(element, "date")
        )

        if not title:
            continue

        items.append(
            RSSFeedItem(
                pub_date=pub_date,
                title=title,
                text=text,
                source=source,
            )
        )

    return items


def find_feed_entries(root: ElementTree.Element) -> list[ElementTree.Element]:
    entries = find_elements(root, "item")
    if entries:
        return entries
    return find_elements(root, "entry")


def upsert_rss_items(session: Session, items: list[RSSFeedItem]) -> int:
    items = deduplicate_rss_items(items)
    if not items:
        return 0

    values = [
        {
            "pub_date": item.pub_date,
            "title": item.title,
            "text": item.text,
            "source": item.source,
        }
        for item in items
    ]
    statement = insert(RSSItem).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[
            RSSItem.pub_date,
            RSSItem.title,
            RSSItem.source,
        ],
        set_={"text": statement.excluded.text},
    )
    try:
        result = session.execute(statement)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return result.rowcount or 0


def deduplicate_rss_items(items: list[RSSFeedItem]) -> list[RSSFeedItem]:
    deduplicated: dict[tuple[datetime, str, str], RSSFeedItem] = {}
    for item in items:
        deduplicated[(item.pub_date, item.title, item.source)] = item
    return list(deduplicated.values())


def find_elements(root: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [element for element in root.iter() if local_name(element.tag) == name]


def find_child_text(element: ElementTree.Element, name: str) -> str:
    for child in element:
        if local_name(child.tag) == name:
            return child.text or ""
    return ""


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":", 1)[-1]


def normalize_source(source_url: str) -> str:
    host = urlparse(source_url).netloc.lower()
    return host.removeprefix("www.")


def parse_pub_date(raw_value: str) -> datetime:
    if not raw_value.strip():
        return datetime.now(UTC)

    try:
        parsed = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def clean_text(raw_value: str) -> str:
    if not raw_value:
        return ""

    unescaped = unescape(raw_value)
    text = BeautifulSoup(unescaped, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()
