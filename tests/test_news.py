"""
Tests for the news fetching and storage system.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.news.fetcher import NewsItem, ESPNFetcher, NFLComFetcher, RedditFetcher, NewsFetcher
from src.news.storage import NewsStorage


class TestNewsItem:
    """Test the NewsItem dataclass."""

    def test_create_news_item(self):
        """Test creating a basic news item."""
        item = NewsItem(
            id="test_123",
            title="Test Article",
            content="This is test content",
            source="espn",
            url="https://espn.com/test",
            published_at="2024-01-15T10:00:00",
        )

        assert item.id == "test_123"
        assert item.title == "Test Article"
        assert item.source == "espn"
        assert item.tags == []  # Default empty list

    def test_news_item_with_optional_fields(self):
        """Test news item with optional fields populated."""
        item = NewsItem(
            id="test_456",
            title="Chiefs Win",
            content="Kansas City wins again",
            source="reddit",
            url="https://reddit.com/r/nfl/123",
            published_at="2024-01-15T10:00:00",
            author="u/nfl_fan",
            team="KC",
            tags=["chiefs", "KC", "playoffs"],
        )

        assert item.author == "u/nfl_fan"
        assert item.team == "KC"
        assert "chiefs" in item.tags

    def test_news_item_to_dict(self):
        """Test converting news item to dictionary."""
        item = NewsItem(
            id="test_789",
            title="Test",
            content="Content",
            source="nfl.com",
            url="https://nfl.com/test",
            published_at="2024-01-15T10:00:00",
        )

        d = item.to_dict()
        assert d["id"] == "test_789"
        assert d["source"] == "nfl.com"

    def test_news_item_from_dict(self):
        """Test creating news item from dictionary."""
        data = {
            "id": "test_from_dict",
            "title": "From Dict",
            "content": "Loaded from dict",
            "source": "espn",
            "url": "https://espn.com/from-dict",
            "published_at": "2024-01-15T10:00:00",
            "author": None,
            "team": None,
            "tags": ["test"],
        }

        item = NewsItem.from_dict(data)
        assert item.id == "test_from_dict"
        assert item.title == "From Dict"


class TestESPNFetcher:
    """Test ESPN RSS fetcher."""

    def test_fetcher_initialization(self):
        """Test ESPN fetcher initializes with correct headers."""
        fetcher = ESPNFetcher()
        assert "User-Agent" in fetcher.session.headers

    @patch("requests.Session.get")
    def test_fetch_rss_success(self, mock_get):
        """Test successful RSS fetch and parse."""
        mock_response = Mock()
        mock_response.content = b"""
        <?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test NFL Story</title>
                    <link>https://espn.com/story1</link>
                    <description>Test description</description>
                    <pubDate>Mon, 15 Jan 2024 10:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = ESPNFetcher()
        items = fetcher.fetch_rss("https://espn.com/test-feed")

        assert len(items) == 1
        assert items[0].title == "Test NFL Story"
        assert items[0].source == "espn"

    @patch("requests.Session.get")
    def test_fetch_rss_error_handling(self, mock_get):
        """Test RSS fetch handles errors gracefully."""
        mock_get.side_effect = Exception("Connection error")

        fetcher = ESPNFetcher()
        items = fetcher.fetch_rss("https://espn.com/bad-feed")

        assert items == []  # Should return empty list on error


class TestNFLComFetcher:
    """Test NFL.com RSS fetcher."""

    def test_fetcher_initialization(self):
        """Test NFL.com fetcher initializes correctly."""
        fetcher = NFLComFetcher()
        assert "User-Agent" in fetcher.session.headers

    @patch("requests.Session.get")
    def test_fetch_rss_success(self, mock_get):
        """Test successful RSS fetch from NFL.com."""
        mock_response = Mock()
        mock_response.content = b"""
        <?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Official NFL News</title>
                    <link>https://nfl.com/news/123</link>
                    <description>Official news content</description>
                    <pubDate>Mon, 15 Jan 2024 10:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = NFLComFetcher()
        items = fetcher.fetch_rss("https://nfl.com/test-feed")

        assert len(items) == 1
        assert items[0].source == "nfl.com"
        assert "official" in items[0].tags


class TestRedditFetcher:
    """Test Reddit JSON API fetcher."""

    def test_fetcher_initialization(self):
        """Test Reddit fetcher initializes with correct user agent."""
        fetcher = RedditFetcher()
        assert "User-Agent" in fetcher.session.headers
        assert "NFL-RAG-App" in fetcher.session.headers["User-Agent"]

    @patch("requests.Session.get")
    def test_fetch_subreddit_success(self, mock_get):
        """Test successful subreddit fetch."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Mahomes throws 5 TDs",
                            "selftext": "Great game by Mahomes",
                            "permalink": "/r/nfl/comments/abc123",
                            "author": "nfl_fan",
                            "created_utc": 1705312800,
                            "score": 500,
                            "stickied": False,
                        }
                    }
                ]
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = RedditFetcher()
        items = fetcher.fetch_subreddit("r/nfl")

        assert len(items) == 1
        assert items[0].source == "reddit"
        assert "Mahomes" in items[0].title

    @patch("requests.Session.get")
    def test_skips_stickied_posts(self, mock_get):
        """Test that stickied posts are skipped."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "stickied",
                            "title": "Weekly Thread",
                            "selftext": "",
                            "permalink": "/r/nfl/comments/stickied",
                            "author": "mod",
                            "created_utc": 1705312800,
                            "score": 1000,
                            "stickied": True,
                        }
                    },
                    {
                        "data": {
                            "id": "regular",
                            "title": "Regular Post",
                            "selftext": "Content",
                            "permalink": "/r/nfl/comments/regular",
                            "author": "user",
                            "created_utc": 1705312800,
                            "score": 100,
                            "stickied": False,
                        }
                    },
                ]
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = RedditFetcher()
        items = fetcher.fetch_subreddit("r/nfl")

        assert len(items) == 1
        assert items[0].title == "Regular Post"

    @patch("requests.Session.get")
    def test_skips_low_score_posts(self, mock_get):
        """Test that low-score posts are filtered out."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "lowscore",
                            "title": "Low Score Post",
                            "selftext": "",
                            "permalink": "/r/nfl/comments/lowscore",
                            "author": "user",
                            "created_utc": 1705312800,
                            "score": 5,  # Below threshold of 10
                            "stickied": False,
                        }
                    },
                ]
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = RedditFetcher()
        items = fetcher.fetch_subreddit("r/nfl")

        assert len(items) == 0


class TestNewsFetcher:
    """Test combined news fetcher."""

    def test_initialization(self):
        """Test NewsFetcher initializes all source fetchers."""
        fetcher = NewsFetcher()
        assert fetcher.espn is not None
        assert fetcher.nfl is not None
        assert fetcher.reddit is not None


class TestNewsStorage:
    """Test ChromaDB news storage."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create a temporary news storage for testing."""
        return NewsStorage(persist_directory=tmp_path / "test_news_db")

    def test_storage_initialization(self, temp_storage):
        """Test storage initializes correctly."""
        assert temp_storage.collection is not None
        assert temp_storage.count() == 0

    def test_add_items(self, temp_storage):
        """Test adding news items to storage."""
        items = [
            NewsItem(
                id="test_1",
                title="Test Article 1",
                content="Content about the Chiefs winning",
                source="espn",
                url="https://espn.com/1",
                published_at="2024-01-15T10:00:00",
                team="KC",
                tags=["chiefs", "KC"],
            ),
            NewsItem(
                id="test_2",
                title="Test Article 2",
                content="Content about the Bills playoff run",
                source="reddit",
                url="https://reddit.com/2",
                published_at="2024-01-15T11:00:00",
                team="BUF",
                tags=["bills", "BUF"],
            ),
        ]

        added = temp_storage.add_items(items)
        assert added == 2
        assert temp_storage.count() == 2

    def test_add_duplicate_items(self, temp_storage):
        """Test that duplicate items are not added."""
        item = NewsItem(
            id="dup_test",
            title="Duplicate Test",
            content="Content",
            source="espn",
            url="https://espn.com/dup",
            published_at="2024-01-15T10:00:00",
        )

        # Add twice
        added1 = temp_storage.add_items([item])
        added2 = temp_storage.add_items([item])

        assert added1 == 1
        assert added2 == 0
        assert temp_storage.count() == 1

    def test_search(self, temp_storage):
        """Test semantic search on news."""
        items = [
            NewsItem(
                id="search_1",
                title="Patrick Mahomes MVP Performance",
                content="Mahomes throws for 400 yards in dominant win",
                source="espn",
                url="https://espn.com/mahomes",
                published_at="2024-01-15T10:00:00",
                team="KC",
            ),
            NewsItem(
                id="search_2",
                title="Josh Allen Leads Bills to Victory",
                content="Allen's rushing ability proves decisive",
                source="nfl.com",
                url="https://nfl.com/allen",
                published_at="2024-01-15T11:00:00",
                team="BUF",
            ),
        ]

        temp_storage.add_items(items)

        # Search for Mahomes-related content
        results = temp_storage.search("Mahomes quarterback performance")

        assert len(results) > 0
        # The Mahomes article should be more relevant
        assert any("Mahomes" in r["title"] for r in results)

    def test_search_with_source_filter(self, temp_storage):
        """Test search filtered by source."""
        items = [
            NewsItem(
                id="filter_1",
                title="ESPN Story",
                content="Content from ESPN",
                source="espn",
                url="https://espn.com/story",
                published_at="2024-01-15T10:00:00",
            ),
            NewsItem(
                id="filter_2",
                title="Reddit Post",
                content="Content from Reddit",
                source="reddit",
                url="https://reddit.com/post",
                published_at="2024-01-15T11:00:00",
            ),
        ]

        temp_storage.add_items(items)

        # Search only ESPN
        results = temp_storage.search("content", source="espn")

        assert len(results) == 1
        assert results[0]["source"] == "espn"

    def test_search_with_team_filter(self, temp_storage):
        """Test search filtered by team."""
        items = [
            NewsItem(
                id="team_1",
                title="Chiefs News",
                content="Content about Kansas City",
                source="espn",
                url="https://espn.com/kc",
                published_at="2024-01-15T10:00:00",
                team="KC",
            ),
            NewsItem(
                id="team_2",
                title="Bills News",
                content="Content about Buffalo",
                source="espn",
                url="https://espn.com/buf",
                published_at="2024-01-15T11:00:00",
                team="BUF",
            ),
        ]

        temp_storage.add_items(items)

        # Search only KC
        results = temp_storage.search("news", team="KC")

        assert len(results) == 1
        assert results[0]["team"] == "KC"

    def test_get_recent(self, temp_storage):
        """Test getting recent news items."""
        items = [
            NewsItem(
                id="recent_1",
                title="Older Story",
                content="Content",
                source="espn",
                url="https://espn.com/old",
                published_at="2024-01-10T10:00:00",
            ),
            NewsItem(
                id="recent_2",
                title="Newer Story",
                content="Content",
                source="espn",
                url="https://espn.com/new",
                published_at="2024-01-15T10:00:00",
            ),
        ]

        temp_storage.add_items(items)

        recent = temp_storage.get_recent(limit=2)

        assert len(recent) == 2
        # Should be sorted by date, newest first
        assert recent[0]["published_at"] > recent[1]["published_at"]

    def test_stats(self, temp_storage):
        """Test getting storage statistics."""
        items = [
            NewsItem(
                id="stat_1",
                title="ESPN Story",
                content="Content",
                source="espn",
                url="https://espn.com/1",
                published_at="2024-01-15T10:00:00",
            ),
            NewsItem(
                id="stat_2",
                title="Reddit Post",
                content="Content",
                source="reddit",
                url="https://reddit.com/1",
                published_at="2024-01-15T10:00:00",
            ),
        ]

        temp_storage.add_items(items)

        stats = temp_storage.stats()

        assert stats["total"] == 2
        assert stats["by_source"]["espn"] == 1
        assert stats["by_source"]["reddit"] == 1

    def test_clear(self, temp_storage):
        """Test clearing all news items."""
        items = [
            NewsItem(
                id="clear_1",
                title="Test",
                content="Content",
                source="espn",
                url="https://espn.com/clear",
                published_at="2024-01-15T10:00:00",
            ),
        ]

        temp_storage.add_items(items)
        assert temp_storage.count() == 1

        temp_storage.clear()
        assert temp_storage.count() == 0
