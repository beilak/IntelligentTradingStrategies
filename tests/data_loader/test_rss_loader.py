from datetime import UTC, datetime

from its.data_loader.rss_loader import (
    DEFAULT_RSS_URLS,
    RSSFeedItem,
    deduplicate_rss_items,
    get_default_rss_sources,
    parse_rss_items,
)


def test_parse_rss_items_cleans_html_and_normalizes_source() -> None:
    content = """
    <rss version="2.0">
      <channel>
        <item>
          <title> Test title </title>
          <description><![CDATA[<p>First&nbsp;text</p><br><b>second</b>]]></description>
          <pubDate>Thu, 21 May 2026 09:10:11 +0300</pubDate>
        </item>
      </channel>
    </rss>
    """

    items = parse_rss_items(content, "https://www.finam.ru/analysis/conews/rsspoint/")

    assert len(items) == 1
    assert items[0].source == "finam.ru"
    assert items[0].title == "Test title"
    assert items[0].text == "First text second"
    assert items[0].pub_date == datetime(2026, 5, 21, 6, 10, 11, tzinfo=UTC)


def test_parse_atom_entries() -> None:
    content = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Atom title</title>
        <summary><![CDATA[<p>Atom text</p>]]></summary>
        <updated>2026-05-21T09:10:11+03:00</updated>
      </entry>
    </feed>
    """

    items = parse_rss_items(content, "https://example.com/feed")

    assert len(items) == 1
    assert items[0].source == "example.com"
    assert items[0].title == "Atom title"
    assert items[0].text == "Atom text"
    assert items[0].pub_date == datetime(2026, 5, 21, 6, 10, 11, tzinfo=UTC)


def test_default_rss_urls_include_added_sources() -> None:
    assert "https://www.cnbc.com/id/20409666/device/rss/rss.html" in DEFAULT_RSS_URLS
    assert "https://www.investing.com/rss/news_25.rss" in DEFAULT_RSS_URLS
    assert "https://ru.investing.com/rss/news_25.rss" in DEFAULT_RSS_URLS
    assert "https://www.moex.com/export/news.aspx?cat=102" in DEFAULT_RSS_URLS
    assert "https://www.cbr.ru/rss/RssPress" in DEFAULT_RSS_URLS


def test_default_rss_sources_are_built_from_urls() -> None:
    assert get_default_rss_sources() == [
        "bfm.ru",
        "cbr.ru",
        "cnbc.com",
        "finam.ru",
        "investing.com",
        "moex.com",
        "ru.investing.com",
    ]


def test_deduplicate_rss_items_uses_database_key() -> None:
    pub_date = datetime(2026, 5, 21, 6, 10, 11, tzinfo=UTC)
    items = [
        RSSFeedItem(
            pub_date=pub_date,
            title="Same title",
            text="old text",
            source="moex.com",
        ),
        RSSFeedItem(
            pub_date=pub_date,
            title="Same title",
            text="new text",
            source="moex.com",
        ),
        RSSFeedItem(
            pub_date=pub_date,
            title="Same title",
            text="another source text",
            source="cbr.ru",
        ),
    ]

    deduplicated = deduplicate_rss_items(items)

    assert len(deduplicated) == 2
    assert deduplicated[0].text == "new text"
    assert deduplicated[1].text == "another source text"
